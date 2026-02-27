from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.logging.logger import logger

# Shared Playwright state
_playwright = None
_browser: Browser | None = None
# Active CDP sessions: session_id -> { page, cdp_session, context }
sessions: dict[str, dict] = {}

async def startup():
    """Launch a single headless Chromium instance at application startup."""
    global _playwright, _browser
    logger.info("Starting Playwright and launching headless Chromium...")
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=["--ignore-certificate-errors"]
    )
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
    logger.info(f"Cleaned up session {session_id} successfully.")
