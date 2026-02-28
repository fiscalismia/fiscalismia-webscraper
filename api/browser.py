from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from api.logging.logger import logger

# Shared Playwright state
_playwright = None
_browser: Browser | None = None
# Active CDP sessions: session_id -> { page, cdp_session, context }
sessions: dict[str, dict] = {}

CHROMIUM_ARGS = [
  "--ignore-certificate-errors",  # bypass TLS cert validation for local/self-signed targets
  "--autoplay-policy=no-user-gesture-required",  # allow media autoplay without user interaction
  "--disable-background-timer-throttling",  # prevent timers throttling to 1Hz in background tabs
  "--disable-backgrounding-occluded-windows",  # keep rendering when window is not visible
  "--disable-renderer-backgrounding",  # prevent OS from deprioritizing the renderer process
  "--disable-popup-blocking",  # allow programmatic popups without suppression
  "--no-first-run",  # skip first-run profile setup and welcome dialog
  "--disable-infobars",  # suppress "Chrome is being controlled" info bar
  "--disable-features=PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies",  # disable media engagement heuristics that block autoplay
  "--disable-gpu-vsync",  # don't wait for vsync, uncaps frame production
  "--disable-frame-rate-limit",  # removes the 60fps cap on compositing
  "--run-all-compositor-stages-before-draw",  # forces full pipeline per frame
  "--disable-checker-imaging",  # disables async image decode (avoids partial frames)
  "--force-color-profile=srgb",  # consistent encoding, avoids color-space conversion overhead
]


async def startup():
  """Launch a single headless Chromium instance at application startup."""
  global _playwright, _browser
  logger.info("Starting Playwright and launching headless Chromium...")
  _playwright = await async_playwright().start()
  _browser = await _playwright.chromium.launch(headless=True, args=CHROMIUM_ARGS)
  logger.info("Chromium browser launched successfully.")


async def shutdown():
  """Close the browser and stop Playwright on app shutdown."""
  global _playwright, _browser
  # clean up any lingering sessions
  for sid in list(sessions.keys()):
    await cleanup_session(sid)
  if _browser:
    await _browser.close()
    logger.info("Chromium browser closed.")
  if _playwright:
    await _playwright.stop()
    logger.info("Playwright stopped.")
  _browser = None
  _playwright = None


async def new_page(url: str | None = None) -> tuple[BrowserContext, Page]:
  """Create a new browser context and page from the shared Chromium instance."""
  if not _browser:
    raise RuntimeError("Browser not initialized. Ensure app lifespan started.")
  context = await _browser.new_context(viewport={"width": 1280, "height": 720})
  page = await context.new_page()
  if url:
    await page.goto(url, wait_until="domcontentloaded")
  return context, page


async def cleanup_session(session_id: str):
  """Clean up a CDP session, closing page and context."""
  session = sessions.pop(session_id, None)
  if not session:
    return
  try:
    cdp = session.get("cdp_session")
    if cdp:
      try:
        await cdp.send("Page.stopScreencast")
        logger.debug(f"Stopped screencast for session {session_id}")
      except Exception:
        pass  # session may already be detached
      await cdp.detach()
      logger.debug(f"Detached Chrome Developer Protocol session {session_id}")
  except Exception as e:
    logger.error(f"Error detaching CDP session {session_id}: {e}")
  try:
    page = session.get("page")
    if page:
      await page.close()
      logger.debug(f"Closed Browser page for session {session_id}")
  except Exception as e:
    logger.error(f"Error closing page for session {session_id}: {e}")
  try:
    context = session.get("context")
    if context:
      await context.close()
      logger.debug(f"Closed Context for session {session_id}")
  except Exception as e:
    logger.error(f"Error closing context for session {session_id}: {e}")
  logger.success(f"Cleaned up session {session_id} successfully.")
