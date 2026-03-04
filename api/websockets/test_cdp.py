import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from api.logger import logger
from api.security import decode_jwt
from api import browser
import base64
from api.config import (
  CDP_SCREENCAST_FORMAT,
  CDP_SCREENCAST_QUALITY,
  CDP_SCREENCAST_MAX_WIDTH,
  CDP_SCREENCAST_MAX_HEIGHT,
  CDP_SCREENCAST_EVERY_NTH_FRAME,
)

########## Chrome Developer Protocol ###################################
# See https://chromedevtools.github.io/devtools-protocol/
# We use CDP sessions via Playwright's CDPSession API:
#   cdp = await page.context.new_cdp_session(page)
#   cdp.send("Domain.method", {params})   — call a CDP method
#   cdp.on("Domain.event", handler)        — subscribe to a CDP event
# ┌────────────────────────────────────────────────────────────────────┐
# │  Page.startScreencast     → begin capturing frames (format/quality)│
# │  Page.screencastFrame     → event: frame emitted (base64 data)     │
# │  Page.screencastFrameAck  → acknowledge frame to receive next one  │
# │  Page.stopScreencast      → stop capturing frames                  │
# ├────────────────────────────────────────────────────────────────────┤
# │  Page.navigate            → navigate to a URL                      │
# │  Page.reload              → reload the current page                │
# │  Page.captureScreenshot   → single screenshot (base64 PNG/JPEG)    │
# │  Page.getLayoutMetrics    → page dimensions and scroll offsets     │
# ├────────────────────────────────────────────────────────────────────┤
# │  Input.dispatchMouseEvent → click, move, scroll                    │
# │  Input.dispatchKeyEvent   → keypress, keydown, keyup               │
# │  Input.dispatchTouchEvent → touch gestures                         │
# ├────────────────────────────────────────────────────────────────────┤
# │  Runtime.evaluate         → run JS expression, return result       │
# ├────────────────────────────────────────────────────────────────────┤
# │  Network.enable           → start tracking network activity        │
# │  Network.requestWillBeSent→ event: outgoing request                │
# │  Network.responseReceived → event: response arrived                │
# ├────────────────────────────────────────────────────────────────────┤
# │  DOM.getDocument          → get the root DOM node                  │
# │  DOM.querySelector        → find element by CSS selector           │
# └────────────────────────────────────────────────────────────────────┘

#   ___       __  ___       __        __   __       ___  ___
#  |__   /\  /__`  |   /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |  /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()  # unprotected (WebSocket needs custom auth)


class StartStreamRequest(BaseModel):
  url: str = "https://example.com"


@router.websocket("/session/{session_id}")
async def stream_websocket(websocket: WebSocket, session_id: str, token: str = Query(default=None)):
  """Stream CDP screencast frames (base64 JPEG) over WebSocket.
  Auth via query param: ws://host/stream/{session_id}/ws?token=<jwt>
  Each frame is sent as a text message. The endpoint acknowledges each frame
  via Page.screencastFrameAck to request the next one."""
  # validate JWT from query parameter
  if not token:
    await websocket.close(code=4001, reason="Missing token query parameter")
    return
  jwt_result = decode_jwt(token)
  if jwt_result["http_status"] != 200:
    await websocket.close(code=4003, reason=jwt_result.get("error_message", "Invalid token"))
    return

  session = browser.sessions.get(session_id)
  if not session:
    await websocket.close(code=4004, reason="Session not found")
    return

  await websocket.accept()
  cdp_session = session["cdp_session"]
  frame_queue: asyncio.Queue = asyncio.Queue()

  def on_screencast_frame(params):
    frame_queue.put_nowait(params)

  cdp_session.on("Page.screencastFrame", on_screencast_frame)
  logger.info(f"WebSocket client connected to session {session_id}")

  # start the screencast now that the frame listener is attached
  await cdp_session.send(
    "Page.startScreencast",
    {
      "format": CDP_SCREENCAST_FORMAT,
      "quality": CDP_SCREENCAST_QUALITY,
      "maxWidth": CDP_SCREENCAST_MAX_WIDTH,
      "maxHeight": CDP_SCREENCAST_MAX_HEIGHT,
      "everyNthFrame": CDP_SCREENCAST_EVERY_NTH_FRAME,
    },
  )
  logger.info(f"CDP screencast started for session {session_id}")

  # force an initial repaint so the compositor emits at least one frame
  page = session["page"]
  await page.evaluate("window.scrollTo(0, 1)")
  await page.evaluate("window.scrollTo(0, 0)")

  try:
    while True:
      # wait for the next frame from CDP (with timeout to detect stale sessions)
      try:
        params = await asyncio.wait_for(frame_queue.get(), timeout=10.0)
      except asyncio.TimeoutError:
        # send a keepalive ping; if client is gone, this will raise
        await websocket.send_json({"type": "keepalive"})
        logger.debug(f"CDP session {session_id} keepalive sent to client.")
        continue

      session_id_frame = params.get("sessionId", 0)

      # TODO encode metadata into initial bytes and add an offset
      # metadata = params.get("metadata", {})
      raw_bytes = base64.b64decode(params.get("data", ""))
      await websocket.send_bytes(raw_bytes)

      # send frame as JSON with base64 image data
      # frame_data = params.get("data", "")
      # metadata = params.get("metadata", {})
      # await websocket.send_json(
      #   {
      #     "type": "frame",
      #     "data": frame_data,
      #     "metadata": metadata,
      #   }
      # )

      # acknowledge frame to receive the next one
      await cdp_session.send(
        "Page.screencastFrameAck",
        {
          "sessionId": session_id_frame,
        },
      )
  except WebSocketDisconnect:
    logger.warning(f"WebSocket client disconnected from session {session_id}")
  except Exception as e:
    logger.error(f"WebSocket error in session {session_id}: {e}")
  finally:
    await browser.cleanup_session(session_id)
