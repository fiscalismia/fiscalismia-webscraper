"""
Scraping module — base interface and shared models.

Scraping function contract:
    async def scrape(page, cdp_session, session_id) -> ScrapeResult

Each scraping function receives a Playwright page with an active CDP session
and returns a ScrapeResult describing the outcome. The page is already navigated
to the target URL before the function is called.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel


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
  Modulo 100:02d on yr gives 2 digit year and zero-pads to 2 digits"""
  now = datetime.now(ZoneInfo("Europe/Berlin"))
  iso = now.isocalendar()
  return f"kw{iso.week}-{iso.year % 100:02d}"
