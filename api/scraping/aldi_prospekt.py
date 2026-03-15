from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import random
from playwright.async_api import Page, CDPSession, TimeoutError as PlaywrightTimeoutError
from api.logger import logger
from api.config import ALDI_COOKIE_BANNER_SELECTOR, TIMEOUT_SEC_SHORT, TIMEOUT_SEC_DEFAULT, TIMEOUT_SEC_LONG
from api.scraping import ScrapeResult, get_current_week_pattern, build_prospekt_page_urls, respond_with_error

NETWORK_IDLE = "networkidle"  # DISCOURAGED: can be unreliable when injected analytics/tracking send persistent queries
LOADED = "domcontentloaded"
prospekt_page_urls: list[str] = []
prospekt_images_alt_text_dict: dict[str, str] = {}
prospekt_images_alt_text_set: set[str] = set()


async def parse_img_alt_text(page: Page, url: str):
  """Parses all alt text (for screen readers) of prospekt images and adds it to a set for later processing"""
  logger.debug(f"Extracting images in pages {url}")
  query_selector = 'img.left, img.right, img[src*="prospekt.aldi-sued"]'
  await page.wait_for_selector(query_selector, timeout=TIMEOUT_SEC_SHORT)
  images = await page.query_selector_all(query_selector)
  logger.debug(f"Found {len(images)} image elements")
  for img in images:
    alt = await img.get_attribute("alt")
    src = await img.get_attribute("src")
    prospekt_images_alt_text_dict[src] = alt
    prospekt_images_alt_text_set.add(alt)


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

  # 6. Navigate in a loop to next page until the end has been reached - rate limit self to avoid spam
  build_prospekt_page_urls(current_url, 1, total_pages, prospekt_page_urls)
  for prospekt_page in prospekt_page_urls:
    if "2-3" in prospekt_page:
      logger.debug("Skipping pages 2-3 because they only contain an overview")
      continue
    try:
      await asyncio.sleep(random.triangular(0.50, 0.875, 1.25))
      logger.debug(f"[{session_id}] Going to page {prospekt_page}")
      await page.goto(prospekt_page, timeout=TIMEOUT_SEC_DEFAULT, wait_until=LOADED)
      await asyncio.sleep(random.triangular(0.50, 0.875, 1.25))
      logger.success(f"[{session_id}] Successfully navigated to page {page.url}")
      await parse_img_alt_text(page, prospekt_page)
    except PlaywrightTimeoutError:
      logger.warning(f"[{session_id}] Next page navigation timed out. Continue...")
      break

  # 7. Log scraping stats
  missing_alt = {src: src for src, alt in prospekt_images_alt_text_dict.items() if not alt}
  logger.info(
    f"[{session_id}] Scraping complete — "
    f"Total pages: [{total_pages}], "
    f"Total images: [{len(prospekt_images_alt_text_dict)}], "
    f"Unique alt texts: [{len(prospekt_images_alt_text_set)}], "
    f"Missing alt text: [{len(missing_alt)}]"
  )
  if missing_alt:
    for src in missing_alt:
      logger.warning(f"[{session_id}] Missing alt text for: {src}")

  return ScrapeResult(
    status="success",
    session_id=session_id,
    target_url=url,
    prospekt_url=page.url,
    timestamp=timestamp,
    data={
      "img_alt_texts": prospekt_images_alt_text_set,
    },
  )
