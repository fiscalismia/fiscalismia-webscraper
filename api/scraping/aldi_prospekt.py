from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import random
from playwright.async_api import Page, CDPSession, TimeoutError as PlaywrightTimeoutError
from api.logger import logger
from api.config import ALDI_COOKIE_BANNER_SELECTOR, TIMEOUT_SEC_SHORT, TIMEOUT_SEC_DEFAULT, TIMEOUT_SEC_LONG
from api.scraping import ScrapeResult, get_current_week_pattern


def respond_with_error(session_id: str, url: str, error_msg: str):
  """Returns error Object for logging to output file"""
  timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()
  logger.error(f"[{session_id}] ${error_msg}")
  return ScrapeResult(
    status="error",
    session_id=session_id,
    target_url=url,
    timestamp=timestamp,
    data={"error": error_msg},
  )


async def scrape_aldi_prospekt(page: Page, cdp_session: CDPSession, session_id: str, url: str) -> ScrapeResult:
  """Navigate the Aldi prospekt page, dismiss cookies, and find the current week's prospekt link."""
  timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()

  # 1. Dismiss cookie banner
  try:
    cookie_btn = await page.wait_for_selector(ALDI_COOKIE_BANNER_SELECTOR, timeout=TIMEOUT_SEC_LONG)
    await cookie_btn.click()
    logger.success(f"[{session_id}] Cookie banner dismissed.")
  except PlaywrightTimeoutError:
    logger.warning(f"[{session_id}] Cookie banner not found within timeout, Continue...")

  # 2. Wait for stable state
  await page.wait_for_load_state("networkidle")

  # 3. Find prospekt link for current week
  pattern = get_current_week_pattern()
  logger.info(f"[{session_id}] Looking for prospekt link matching pattern: {pattern}")
  try:
    link = await page.wait_for_selector(f'a[href*="{pattern}"]', timeout=TIMEOUT_SEC_DEFAULT)
  except PlaywrightTimeoutError:
    return respond_with_error(session_id, url, f"No prospekt link found matching '{pattern}'")

  # 4. Remove target="_blank" and click to stay in same tab (preserves CDP screencast)
  await page.evaluate(f'document.querySelector(\'a[href*="{pattern}"]\').removeAttribute("target")')
  await link.click()
  await page.wait_for_load_state("networkidle")
  logger.success(f"[{session_id}] Navigated to prospekt: {page.url}")

  # 5. Navigate in a loop to next page until the end has been reached - rate limit self to avoid spam
  while True:
    try:
      logger.debug("Looking for next page link to click.")
      # select either by link id OR by aria-label, that's what colon does in css selectors
      link = await page.wait_for_selector('#next_slide, [aria-label="Nächste Seite"]', timeout=TIMEOUT_SEC_DEFAULT)
      await link.click()
      await page.wait_for_load_state("networkidle", timeout=TIMEOUT_SEC_DEFAULT)
      await asyncio.sleep(random.triangular(0.25, 0.75, 1.25))
      logger.debug(f"Successfully naviagted to page {page.url}")
    except PlaywrightTimeoutError:
      logger.warning(f"[{session_id}] No next page found. Continue...")
      break

  return ScrapeResult(
    status="success",
    session_id=session_id,
    target_url=url,
    prospekt_url=page.url,
    timestamp=timestamp,
  )
