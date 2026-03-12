from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import Page, CDPSession, TimeoutError as PlaywrightTimeoutError
from api.logger import logger
from api.config import ALDI_COOKIE_BANNER_SELECTOR, ALDI_COOKIE_BANNER_TIMEOUT_MS
from api.scraping import ScrapeResult, get_current_week_pattern


async def scrape_aldi_prospekt(page: Page, cdp_session: CDPSession, session_id: str, url: str) -> ScrapeResult:
  """Navigate the Aldi prospekt page, dismiss cookies, and find the current week's prospekt link."""
  timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()

  # 1. Dismiss cookie banner
  try:
    cookie_btn = await page.wait_for_selector(ALDI_COOKIE_BANNER_SELECTOR, timeout=ALDI_COOKIE_BANNER_TIMEOUT_MS)
    await cookie_btn.click()
    logger.info(f"[{session_id}] Cookie banner dismissed.")
  except PlaywrightTimeoutError:
    logger.warning(f"[{session_id}] Cookie banner not found within timeout, continuing.")

  # 2. Wait for stable state
  await page.wait_for_load_state("networkidle")

  # 3. Find prospekt link for current week
  pattern = get_current_week_pattern()
  logger.info(f"[{session_id}] Looking for prospekt link matching pattern: {pattern}")
  try:
    link = await page.wait_for_selector(f'a[href*="{pattern}"]', timeout=10000)
  except PlaywrightTimeoutError:
    logger.error(f"[{session_id}] No prospekt link found for pattern: {pattern}")
    return ScrapeResult(
      status="error",
      session_id=session_id,
      target_url=url,
      timestamp=timestamp,
      data={"error": f"No prospekt link found matching '{pattern}'"},
    )

  # 4. Remove target="_blank" and click to stay in same tab (preserves CDP screencast)
  await page.evaluate(f'document.querySelector(\'a[href*="{pattern}"]\').removeAttribute("target")')
  await link.click()
  await page.wait_for_load_state("networkidle")
  logger.success(f"[{session_id}] Navigated to prospekt: {page.url}")

  # 5. Return success
  return ScrapeResult(
    status="success",
    session_id=session_id,
    target_url=url,
    prospekt_url=page.url,
    timestamp=timestamp,
  )
