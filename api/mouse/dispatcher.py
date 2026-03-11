import asyncio
import random
from api.mouse.interpolation import interpolate_path
from api.mouse.timing import movement_delay, micro_pause_chance
from api.cdp_utility import human_click_delay
from api.logger import logger


async def dispatch_mouse_move(
  cdp_session,
  from_point: tuple[int, int],
  to_point: tuple[int, int],
) -> None:
  """Dispatch a humanized mouse movement from from_point to to_point via CDP."""
  path = interpolate_path(from_point, to_point)
  logger.debug(f"Mouse move: ({from_point}) -> ({to_point}), {len(path)} interpolation points")

  for x, y in path:
    await cdp_session.send(
      "Input.dispatchMouseEvent",
      {"type": "mouseMoved", "x": x, "y": y, "pointerType": "mouse"},
    )
    await asyncio.sleep(movement_delay())
    pause = micro_pause_chance()
    if pause:
      await asyncio.sleep(pause)


async def dispatch_mouse_click(
  cdp_session,
  target_point: tuple[int, int],
  from_point: tuple[int, int],
  button: str = "left",
  element_bbox: dict | None = None,
) -> None:
  """Move to target with humanized path, then perform click with realistic timing."""
  # randomize click position within element bounds if provided
  click_x, click_y = target_point
  if element_bbox:
    cx = element_bbox.get("x", click_x)
    cy = element_bbox.get("y", click_y)
    w = element_bbox.get("width", 0)
    h = element_bbox.get("height", 0)
    if w > 0 and h > 0:
      click_x = round(cx + w * random.uniform(0.35, 0.65))
      click_y = round(cy + h * random.uniform(0.35, 0.65))

  # move to click target
  await dispatch_mouse_move(cdp_session, from_point, (click_x, click_y))

  # press
  await cdp_session.send(
    "Input.dispatchMouseEvent",
    {
      "type": "mousePressed",
      "x": click_x,
      "y": click_y,
      "button": button,
      "clickCount": 1,
      "pointerType": "mouse",
    },
  )

  # human hold duration
  hold_delay = human_click_delay()
  await asyncio.sleep(hold_delay)

  # release
  await cdp_session.send(
    "Input.dispatchMouseEvent",
    {
      "type": "mouseReleased",
      "x": click_x,
      "y": click_y,
      "button": button,
      "clickCount": 1,
      "pointerType": "mouse",
    },
  )
  logger.debug(f"Mouse click at ({click_x}, {click_y}) button={button} hold={hold_delay:.4f}s")
