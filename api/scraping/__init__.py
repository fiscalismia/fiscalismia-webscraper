from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from api.logger import logger


class ScrapeResult(BaseModel):
  status: str
  session_id: str
  target_url: str
  prospekt_url: str | None = None
  timestamp: str
  data: dict | None = None


def get_current_week_pattern() -> str:
  """Return the current calendar week pattern, e.g. 'kw11-26' for KW 11 of 2026.
  Uses ISO year from isocalendar() to handle year-boundary edge cases.
  Modulo 100:02d on yr gives 2 digit year and zero-pads to 2 digits
  From Saturday to Sunday night after midnight Aldi switches to a new prospekt"""
  now = datetime.now(ZoneInfo("Europe/Berlin"))
  iso = now.isocalendar()
  if now.weekday() == 6:
    return f"kw{iso.week + 1}-{iso.year % 100:02d}"
  return f"kw{iso.week}-{iso.year % 100:02d}"


def build_prospekt_page_urls(prospekt_url: str, start_page: int, total_pages: int, prospekt_page_urls: list[str]):
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
