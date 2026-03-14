from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import random
from playwright.async_api import Page, CDPSession, TimeoutError as PlaywrightTimeoutError
from api.logger import logger
from api.config import ALDI_COOKIE_BANNER_SELECTOR, TIMEOUT_SEC_SHORT, TIMEOUT_SEC_DEFAULT, TIMEOUT_SEC_LONG
from api.scraping import ScrapeResult, get_current_week_pattern

NETWORK_IDLE = "networkidle"  # DISCOURAGED: can be unreliable when injected analytics/tracking send persistent queries
LOADED = "domcontentloaded"
prospekt_page_urls: list[str] = []


def build_prospekt_page_urls(prospekt_url: str, start_page: int, total_pages: int):
  """Builds a collection of urls to navigate, since clicking the next button is error-prone"""
  increment_by = 2
  slice_str = "/page/"
  slice_idx = prospekt_url.index(slice_str)
  target_url_base = f"{prospekt_url[:slice_idx]}{slice_str}"
  for x in range(start_page, total_pages, increment_by):
    next_page_str = f"{str(x + 1)}-{str(x + 2)}"
    next_prospekt_url = f"{target_url_base}{next_page_str}"
    prospekt_page_urls.append(next_prospekt_url)


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
  await page.wait_for_load_state(LOADED, timeout=TIMEOUT_SEC_DEFAULT)

  # 3. Find prospekt link for current week
  pattern = get_current_week_pattern()
  query_selector = f'a[href*="{pattern}"]'
  logger.info(f"[{session_id}] Looking for prospekt link matching pattern: {pattern}")
  try:
    link = await page.wait_for_selector(query_selector, timeout=TIMEOUT_SEC_DEFAULT)
  except PlaywrightTimeoutError:
    return respond_with_error(session_id, page.url, f"No prospekt link found matching '{pattern}'")

  # 4. Remove target="_blank" and click to stay in same tab (preserves CDP screencast)
  await page.evaluate(f"document.querySelector('{query_selector}').removeAttribute(\"target\")")
  await link.click()
  await page.wait_for_load_state(LOADED, timeout=TIMEOUT_SEC_DEFAULT)
  await asyncio.sleep(1)

  # 5. Extract total pagecount of prospekt
  try:
    current_page_parent = await page.wait_for_selector(".current-page", timeout=TIMEOUT_SEC_SHORT)
    page_num_span = await page.wait_for_selector(".current-page > .page-numbers", timeout=TIMEOUT_SEC_SHORT)
    total_page_span = await page.wait_for_selector(".current-page > .total", timeout=TIMEOUT_SEC_SHORT)
    pages_label = await current_page_parent.get_attribute("aria-label")
    current_page_str = await page_num_span.inner_text()
    total_page_str = await total_page_span.inner_text()
    if not current_page_str or not total_page_str:
      logger.debug(f"[{session_id}] Label is {pages_label}")
      raise LookupError
    total_pages = int(total_page_str)
    current_page = int(current_page_str)
    logger.info(f"Current page(s) = [{current_page}] and total pages = [{total_pages}]")
  except PlaywrightTimeoutError:
    logger.warning(f"[{session_id}] Error retrieving total page count. Continue...")
  except ValueError:
    return respond_with_error(session_id, page.url, f"total_pages {total_pages} could not be converted to a number'")
  except LookupError:
    return respond_with_error(
      session_id, page.url, f"current_page_str {current_page_str} total_page_str {total_page_str}'"
    )
  current_url = page.url
  logger.success(f"[{session_id}] Navigated to prospekt: {current_url}")

  build_prospekt_page_urls(current_url, 1, total_pages)

  # 6. Navigate in a loop to next page until the end has been reached - rate limit self to avoid spam
  for prospekt_page in prospekt_page_urls:
    try:
      await asyncio.sleep(random.triangular(0.50, 0.875, 1.25))
      logger.debug(f"[{session_id}] Going to page {prospekt_page}")
      await page.goto(prospekt_page, timeout=TIMEOUT_SEC_DEFAULT, wait_until=LOADED)
      await asyncio.sleep(random.triangular(0.50, 0.875, 1.25))
      logger.success(f"[{session_id}] Successfully navigated to page {page.url}")
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
