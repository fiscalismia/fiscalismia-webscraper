from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import random
from playwright.async_api import Page, CDPSession, TimeoutError as PlaywrightTimeoutError
from api.logger import logger
import os
from api.config import (
  ALDI_COOKIE_BANNER_SELECTOR,
  TIMEOUT_SEC_SHORT,
  TIMEOUT_SEC_DEFAULT,
  TIMEOUT_SEC_LONG,
  SCRAPE_RESULTS_DIR,
  TIMEOUT_SEC_MAX,
)
from api.scraping import (
  ScrapeResult,
  get_current_week_pattern,
  construct_prospekt_page_urls,
  respond_with_error,
  PLAYWRIGHT_STATE_LOADED,
)

prospekt_page_urls: list[str] = []
prospekt_images_src_alt_dict: dict[str, str] = {}
prospekt_images_alt_text_set: set[str] = set()
prospekt_image_url_set: set[str] = set()


async def parse_image_alt_src(page: Page, url: str):
  """Parses all alt text (for screen readers) of prospekt images and adds it to a set for later processing
  Parses all img src urls within given prospekt page and adds it to a set for later processing"""
  logger.debug(f"Extracting image src and alt text in page(s) {url}")
  query_selector = 'img.left, img.right, img[src*="prospekt.aldi-sued"]'
  await page.wait_for_selector(query_selector, timeout=TIMEOUT_SEC_SHORT)
  images = await page.query_selector_all(query_selector)
  logger.debug(f"Found {len(images)} image elements")
  for img in images:
    alt = await img.get_attribute("alt")
    src = await img.get_attribute("src")
    prospekt_images_src_alt_dict[src] = alt
    prospekt_images_alt_text_set.add(alt)
    prospekt_image_url_set.add(src)


async def download_prospekt_pdf(page: Page, session_id: str) -> str | None:
  """Download the prospekt PDF from the current page.

  Returns the filepath on success, or None on failure.
  Callers should check the return value before relying on the file.
  """
  logger.debug("PDF Download logic initiated. Scraping for URL...")
  try:
    pdf_download_link = await page.wait_for_selector("#downloadAsPdf", timeout=TIMEOUT_SEC_SHORT)
  except PlaywrightTimeoutError:
    logger.warning(f"[{session_id}] PDF download button not found within timeout.")
    return None

  pdf_download_url = await pdf_download_link.get_attribute("href")
  if not pdf_download_url or ".pdf" not in pdf_download_url:
    logger.error(f"[{session_id}] PDF download URL could not be extracted: {pdf_download_url}")
    return None

  logger.debug(f"[{session_id}] Downloading PDF via URL {pdf_download_url}")
  try:
    async with page.expect_download(timeout=TIMEOUT_SEC_MAX) as download_info:
      await pdf_download_link.click()
    pdf = await download_info.value
  except PlaywrightTimeoutError:
    logger.error(f"[{session_id}] PDF download timed out.")
    return None

  filename = f"aldi_prospekt_{session_id}.pdf"
  filepath = os.path.join(SCRAPE_RESULTS_DIR, filename)
  await pdf.save_as(filepath)

  if not os.path.isfile(filepath):
    logger.error(f"[{session_id}] PDF could not be persisted to tmpfs at {filepath}")
    return None

  logger.debug(f"[{session_id}] PDF {filename} saved to RAM in tmpfs path {SCRAPE_RESULTS_DIR}")
  stat_info = os.stat(filepath)
  stat_info.st_size  # File size in bytes (same as getsize)
  stat_info.st_mode  # File permissions + type bits
  stat_info.st_mtime  # Last modification time (epoch float)
  stat_info.st_uid  # Owner user ID
  stat_info.st_gid  # Owner group ID
  stat_info.st_ino  # Inode number
  stat_info.st_dev  # Device ID (identifies the filesystem)
  logger.debug(f"[{session_id}] PDF stats: {stat_info}")

  # Validate the PDF magic bytes
  with open(filepath, "rb") as f:
    header = f.read(8)
    if not header.startswith(b"%PDF"):
      logger.error(f"[{session_id}] File at {filepath} is not a valid PDF (bad magic bytes).")
      return None
    version = header.decode("ascii", errors="replace").strip()
    logger.success(f"[{session_id}] Valid PDF: {version} read from {filepath}")

  return filepath


async def scrape_aldi_prospekt(
  page: Page,
  cdp_session: CDPSession,
  session_id: str,
  url: str,
  download_pdf: bool = False,
) -> ScrapeResult:
  """Navigate the Aldi prospekt page, dismiss cookies, and find the current week's prospekt link.
  Loop through pages with a random delay as rate limit, extract alt texts and collect prospekt img urls
  Optionally download the prospekt PDF into memory for later text extraction and OCR reading"""
  timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()

  # 1. Dismiss cookie banner
  try:
    cookie_btn = await page.wait_for_selector(ALDI_COOKIE_BANNER_SELECTOR, timeout=TIMEOUT_SEC_LONG)
    await cookie_btn.click()
    logger.success(f"[{session_id}] Cookie banner dismissed.")
  except PlaywrightTimeoutError:
    logger.warning(f"[{session_id}] Cookie banner not found within timeout, Continue...")

  # 2. Wait for stable state
  await page.wait_for_load_state(PLAYWRIGHT_STATE_LOADED, timeout=TIMEOUT_SEC_DEFAULT)

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
  await page.wait_for_load_state(PLAYWRIGHT_STATE_LOADED, timeout=TIMEOUT_SEC_DEFAULT)
  await asyncio.sleep(1)

  # 5. Extract total pagecount of prospekt to limit
  try:
    current_page_parent = await page.wait_for_selector(".current-page", timeout=TIMEOUT_SEC_DEFAULT)
    page_num_span = await page.wait_for_selector(".current-page > .page-numbers", timeout=TIMEOUT_SEC_DEFAULT)
    total_page_span = await page.wait_for_selector(".current-page > .total", timeout=TIMEOUT_SEC_DEFAULT)
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
    return respond_with_error(session_id, page.url, "Error retrieving total page count. Timeout.")
  except ValueError:
    return respond_with_error(session_id, page.url, f"total_pages {total_pages} could not be converted to a number'")
  except LookupError:
    return respond_with_error(
      session_id, page.url, f"current_page_str {current_page_str} total_page_str {total_page_str}'"
    )
  current_url = page.url
  logger.success(f"[{session_id}] Navigated to prospekt: {current_url}")

  # 6. extract alt text and img urls and add to module level variables - NOTE: this limits concurrency to 1
  # Extract data from initial page
  await parse_image_alt_src(page, page.url)
  # Navigate in a loop to next page until the end has been reached - rate limit self to avoid spam
  construct_prospekt_page_urls(current_url, total_pages, prospekt_page_urls)
  for prospekt_page in prospekt_page_urls:
    if prospekt_page.endswith("/10-11"):
      logger.debug("Ending early during test and development")
      break
    try:
      await asyncio.sleep(random.triangular(0.75, 1.25, 1.75))
      logger.debug(f"[{session_id}] Going to page {prospekt_page}")
      await page.goto(prospekt_page, timeout=TIMEOUT_SEC_DEFAULT, wait_until=PLAYWRIGHT_STATE_LOADED)
      await asyncio.sleep(random.triangular(0.50, 1.00, 1.50))
      logger.success(f"[{session_id}] Successfully navigated to page {page.url}")
      # Extract relevant information from pages to module level data structures
      await parse_image_alt_src(page, prospekt_page)
    except PlaywrightTimeoutError:
      logger.warning(f"[{session_id}] Next page navigation timed out. Continue...")
      break

  # 7. Log scraping statistics
  missing_alt = {src: src for src, alt in prospekt_images_src_alt_dict.items() if not alt}
  logger.info(
    f"[{session_id}] Scraping complete — "
    f"Total pages: [{total_pages}], "
    f"Unique images: [{len(prospekt_image_url_set)}], "
    f"Unique alt texts: [{len(prospekt_images_alt_text_set)}], "
    f"Missing alt text: [{len(missing_alt)}]"
  )
  if len(prospekt_images_alt_text_set) > len(prospekt_image_url_set):
    logger.warning("More alt texts extracted than src images found. Continue")
  if missing_alt:
    for src in missing_alt:
      logger.warning(f"[{session_id}] Missing alt text for: {src}")

  # 8. Optionally download prospekt PDF (≈70 MB) for text extraction / OCR reading
  optional_pdf_filepath: str | None = None
  if download_pdf:
    optional_pdf_filepath = await download_prospekt_pdf(page, session_id)
    if optional_pdf_filepath is None:
      return respond_with_error(session_id, page.url, "PDF download was requested but failed.")

  return ScrapeResult(
    status="success",
    session_id=session_id,
    target_url=url,
    prospekt_url=page.url,
    timestamp=timestamp,
    data={
      "prospekt_images_src_alt_dict": prospekt_images_src_alt_dict,
      "optional_pdf_filepath": optional_pdf_filepath,
    },
  )
