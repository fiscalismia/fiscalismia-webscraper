import random
from api.config import (
  MOUSE_BASE_INTERVAL_MS,
  MOUSE_TIMING_JITTER_SIGMA,
  MOUSE_MIN_INTERVAL_MS,
)


def movement_delay() -> float:
  """Return a humanized inter-point delay in seconds.
  Base ~10ms with Gaussian jitter, clamped to min 4ms."""
  delay_ms = MOUSE_BASE_INTERVAL_MS + random.gauss(0, MOUSE_TIMING_JITTER_SIGMA)
  delay_ms = max(delay_ms, MOUSE_MIN_INTERVAL_MS)
  return delay_ms / 1000.0


def micro_pause_chance() -> float | None:
  """5% chance of a micro-pause (20-50ms). Returns pause in seconds or None."""
  if random.random() < 0.05:
    return random.uniform(0.020, 0.050)
  return None
