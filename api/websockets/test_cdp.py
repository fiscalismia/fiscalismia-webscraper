import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from api.logger import logger
from api.security import decode_jwt
from api import browser
from api.mouse import dispatch_mouse_move, dispatch_mouse_click
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


async def handle_mouse(cdp_session, action, user_input, session):
  x = user_input["x"]
  y = user_input["y"]
  button = user_input["button"]
  from_point = (session.get("cursor_x", x), session.get("cursor_y", y))
  to_point = (x, y)
  logger.debug(f"Mouse {action}: from {from_point} to {to_point}")

  if action == "mouseMoved":
    await dispatch_mouse_move(cdp_session, from_point, to_point)
    session["cursor_x"] = x
    session["cursor_y"] = y
  elif action == "custom_mouse_click":
    element_bbox = user_input.get("element_bbox", None)
    await dispatch_mouse_click(cdp_session, to_point, from_point, button, element_bbox)
    session["cursor_x"] = x
    session["cursor_y"] = y
  elif action == "mouseWheel":
    deltaX = user_input.get("deltaX", 0)
    deltaY = user_input.get("deltaY", 0)
    await cdp_session.send(
      "Input.dispatchMouseEvent",
      {"type": "mouseWheel", "x": x, "y": y, "deltaX": deltaX, "deltaY": deltaY, "button": button, "pointerType": "mouse"},
    )


@router.websocket("/session/{session_id}")
async def stream_websocket(websocket: WebSocket, session_id: str, token: str = Query(default=None)):
  """Stream CDP screencast frames (base64 JPEG) over WebSocket.
  Auth via query param: ws://host/stream/{session_id}/ws?token=<jwt>
  Each frame is sent as a text message. The endpoint acknowledges each frame
  via Page.screencastFrameAck to request the next one."""
  ### VALIDATE JWT
  validated_jwt = asyncio.Event()
  await websocket.accept()
  try:
    token = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
  except asyncio.TimeoutError:
    await logger.ws_error_close(websocket, "Token not received in time.", 1008)
    return
  if not token:
    # for websocket codes see https://websocket.org/reference/close-codes/
    await logger.ws_error_close(websocket, "Missing token websocket text payload.", 1008)
    return
  jwt_result = decode_jwt(token)
  if jwt_result["http_status"] == 200:
    validated_jwt.set()
    logger.debug("Successfully validated initial token received via websocket.receive_text().")
  if not validated_jwt.is_set():
    await logger.ws_error_close(
      websocket, jwt_result.get("error_message", "Websocket Connection could not validate JWT Session Token"), 1008
    )
    return

  session = browser.sessions.get(session_id)
  if not session:
    await logger.ws_error_close(websocket, "Session not found", 1008)
    return

  stop_event = asyncio.Event()
  frame_queue = asyncio.Queue()
  cdp_session = session["cdp_session"]

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

  page = session["page"]
  logger.info(f"Starting streaming CDP screencast session {session_id} for url {page.url}")
  # force an initial repaint so the compositor emits at least one frame
  await page.evaluate("window.scrollTo(0, 1)")
  await page.evaluate("window.scrollTo(0, 0)")

  async def send_frames():
    while not stop_event.is_set():
      try:
        # wait for the next frame from CDP (with timeout to detect stale sessions)
        params = await asyncio.wait_for(frame_queue.get(), timeout=10.0)
      except asyncio.TimeoutError:
        # send a keepalive ping; if client is gone, this will raise
        await websocket.send_json({"type": "keepalive"})
        logger.debug(f"CDP session {session_id} keepalive sent to client.")
        continue

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

      # acknowledge frame server side in the event loop to receive the next one
      await cdp_session.send(
        "Page.screencastFrameAck",
        {
          "sessionId": params.get("sessionId", 0),
        },
      )

  async def receive_input():
    while not stop_event.is_set():
      try:
        client_message = await websocket.receive_json()
      except ValueError:
        logger.warning(f"Session {session_id}: received malformed JSON message, discarding")
        continue
      message_type = client_message.get("type", None)
      if not message_type:
        await logger.ws_error_close(websocket, "Input requires a type key to be set.")
        return
      x = client_message.get("x", None)
      y = client_message.get("y", None)
      if x is None or y is None:
        await logger.ws_error_close(websocket, "JSON input requires x and y coordinates be set as keys.")
        return
      if message_type in ["custom_mouse_click", "mouseWheel", "mouseMoved"]:
        mouse_btn = client_message.get("button", None)
        if not mouse_btn:
          await logger.ws_error_close(websocket, "Mouse events requires the button property to be set.")
          return
        await handle_mouse(cdp_session, message_type, client_message, session)

  try:
    await asyncio.gather(send_frames(), receive_input())
  except WebSocketDisconnect:
    logger.warning(f"WebSocket client disconnected from session {session_id}")
  except Exception as e:
    logger.error(f"WebSocket error in session {session_id}: {e}")
  finally:
    logger.debug("Cleaning up CDP session after CDP route invocation.")
    stop_event.set()
    await browser.cleanup_session(session_id)
