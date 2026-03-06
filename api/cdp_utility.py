import random
from api.logger import logger


def human_click_delay() -> float:
  """
  Returns a realistic mousedown→mouseup delay in seconds.
  Uses triangular distribution: fast clicks are possible but rare,
  most clicks cluster around 100-150ms, slow clicks tail off to ~350ms.
  """
  # triangular(low, high, mode) — mode is the most probable value
  delay = random.triangular(0.05, 0.35, 0.12)
  wait_delay = round(delay, 4)
  logger.debug(f"Waiting {wait_delay}s between mouseEvent to emulate humman behavior.")
  return round(delay, 4)
