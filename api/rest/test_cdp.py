import uuid
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from api.logger import logger
from api import browser

#   ___       __  ___       __        __   __       ___  ___
#  |__   /\  /__`  |   /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |  /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()  # JWT-protected (POST /start)


class StartStreamRequest(BaseModel):
  url: str = "https://example.com"


@router.post("/cdp/start")
async def start_stream(req: StartStreamRequest):
  """Launch a headless Chromium page, navigate to the given URL,
  start a CDP screencast, and return a session_id for the WebSocket stream."""
  session_id = str(uuid.uuid4())
  try:
    context, page = await browser.new_page(req.url)
    cdp_session = await page.context.new_cdp_session(page)
    # screencast is started when the WebSocket connects (not here)
    # to avoid losing initial frames before the listener is attached
    browser.sessions[session_id] = {
      "context": context,
      "page": page,
      "cdp_session": cdp_session,
    }
    logger.info(f"Initiated CDP screencast session {session_id} for URL: {req.url}")
    return {
      "session_id": session_id,
      "url": req.url,
      "endpoint": f"/ws/session/{session_id}?token=<jwt>",
    }
  except Exception as e:
    logger.error(f"Failed to start screencast: {e}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start browser session: {str(e)}"
    )
