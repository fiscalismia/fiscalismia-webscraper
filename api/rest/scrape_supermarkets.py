import asyncio
import json
import os
import uuid
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from api.logger import logger
from api import browser
from datetime import datetime
from zoneinfo import ZoneInfo
from api.scraping import ScrapeResult
from api.stealth import apply_stealth
from api.config import BROWSER_VIEWPORT_WIDTH, BROWSER_VIEWPORT_HEIGHT, SCRAPE_RESULTS_DIR, BASE_ROUTE, REST_ENDPOINT
from api.scraping.scrape_aldi_prospekt import scrape_aldi_prospekt
from api.scraping.etl_aldi_prospekt import etl_aldi_prospekt

from api.scraping import (
  validate_filepath,
)

router = APIRouter()

# prevent GC of background scraping tasks
_running_tasks: dict[str, asyncio.Task] = {}


class StartWebscrapeRequest(BaseModel):
  url: str = "https://aldi-sued.de"


async def _run_scrape(session_id: str, url: str):
  """Background coroutine: wait for WebSocket to connect, then run the scraping automation."""
  try:
    # give frontend time to connect WebSocket and attach frame listener
    await asyncio.sleep(2)
    session = browser.sessions.get(session_id)
    if not session:
      logger.error(f"[{session_id}] Session not found during launch process.")
      return
    page = session["page"]
    cdp_session = session["cdp_session"]
    result = await scrape_aldi_prospekt(page, cdp_session, session_id, url, download_pdf=False)
  except Exception as e:
    logger.error(f"[{session_id}] Scraping failed with exception: {e}")
    result = ScrapeResult(
      status="error",
      session_id=session_id,
      target_url=url,
      timestamp=datetime.now(ZoneInfo("Europe/Berlin")).isoformat(),
      data={"error": str(e)},
    )
  finally:
    _running_tasks.pop(session_id, None)

  # WRITE RESULT TO FILE IN MEMORY
  filepath = os.path.join(SCRAPE_RESULTS_DIR, f"aldi_prospekt_{session_id}.json")
  with open(filepath, "w") as f:
    f.write(result.model_dump_json(indent=2))
  logger.header(f"[{session_id}] Scrape result written to {filepath}")

  # CLEANUP BROWSER CDP SESSION & WRITE RESULT TO MEMORY
  await browser.cleanup_session(session_id)


@router.post("/cdp/scrape/supermarket/aldi_prospekt")
async def scrape_aldi(req: StartWebscrapeRequest):
  """Launch a headless browser, navigate to Aldi prospekt page, and start automated scraping."""
  logger.debug(f"POST route {BASE_ROUTE}{REST_ENDPOINT}/cdp/scrape/supermarket/aldi_prospekt received a query")
  session_id = str(uuid.uuid4())
  try:
    context, page = await browser.new_page(req.url)
    cdp_session = await page.context.new_cdp_session(page)
    await apply_stealth(page, cdp_session)
    browser.sessions[session_id] = {
      "context": context,
      "page": page,
      "cdp_session": cdp_session,
      "cursor_x": BROWSER_VIEWPORT_WIDTH // 2,
      "cursor_y": BROWSER_VIEWPORT_HEIGHT // 2,
    }
    logger.info(f"Initiated scraping session {session_id} for URL: {req.url}")

    # launch scraping in background
    task = asyncio.create_task(_run_scrape(session_id, req.url))
    _running_tasks[session_id] = task

    return {
      "session_id": session_id,
      "url": req.url,
      "results_url": f"/cdp/scrape/results/{session_id}",
    }
  except Exception as e:
    logger.error(f"Failed to start scraping session: {e}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Failed to start scraping session: {str(e)}",
    )


@router.get("/cdp/scrape/results/{session_id}")
async def get_scrape_results(session_id: str):
  """Retrieve scraping results for a given session."""
  logger.debug(f"GET route {BASE_ROUTE}{REST_ENDPOINT}/cdp/scrape/results/{session_id} received a query")
  filepath = os.path.join(SCRAPE_RESULTS_DIR, f"aldi_prospekt_{session_id}.json")
  if os.path.isfile(filepath):
    with open(filepath, "r") as f:
      return json.load(f)
  if session_id in browser.sessions:
    raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Scraping in progress")
  raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.post("/cdp/scrape/etl/aldi/{session_id}")
async def start_etl_on_aldi_results(session_id: str):
  """Use scraping results as input for running sanitization and transformations for a given session."""
  logger.debug(f"POST route {BASE_ROUTE}{REST_ENDPOINT}/cdp/scrape/etl/aldi/{session_id} received a query")
  try:
    filepath = validate_filepath(os.path.join(SCRAPE_RESULTS_DIR, f"aldi_prospekt_{session_id}.json"))
  except Exception as e:
    logger.error(f"Filepath validation failed: {e}")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Filepath not validated: {str(e)}")
  if session_id in browser.sessions:
    raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Scraping in progress")
  try:
    etl_result = await etl_aldi_prospekt(session_id, filepath)
  except Exception as e:
    logger.error(f"ETL Aldi Prospekt failed: {e}")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"ETL Aldi Prospekt failed: {str(e)}")
  return etl_result


# TODO: Remove
@router.post("/cdp/scrape/etl/alditest")
async def test_etl():
  """Use scraping results as input for running sanitization and transformations for a given session."""
  logger.debug(f"POST route {BASE_ROUTE}{REST_ENDPOINT}/cdp/scrape/etl/alditest received a query")
  try:
    etl_result = await etl_aldi_prospekt("test", "test", False)
  except Exception as e:
    logger.error(f"ETL Aldi Prospekt failed: {e}")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"ETL Aldi Prospekt failed: {str(e)}")
  return etl_result
