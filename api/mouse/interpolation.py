import math
import random
from api.config import (
  MOUSE_JITTER_SIGMA_PX,
  MOUSE_CONTROL_POINT_SPREAD,
  MOUSE_OVERSHOOT_THRESHOLD_PX,
)


def bezier_point(t: float, p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> tuple[float, float]:
  """Evaluate cubic Bezier curve at parameter t in [0, 1]."""
  u = 1.0 - t
  uu = u * u
  uuu = uu * u
  tt = t * t
  ttt = tt * t
  x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
  y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
  return (x, y)


def ease_in_out(t: float) -> float:
  """Smoothstep easing: 3t^2 - 2t^3 for natural acceleration/deceleration."""
  return 3 * t * t - 2 * t * t * t


def generate_control_points(
  start: tuple, end: tuple
) -> tuple[tuple[float, float], tuple[float, float]]:
  """Generate two control points for a cubic Bezier curve.
  Creates a single-arc trajectory with perpendicular offset."""
  dx = end[0] - start[0]
  dy = end[1] - start[1]
  dist = math.hypot(dx, dy)
  if dist < 1.0:
    return (start, end)

  # perpendicular direction (pick one side randomly)
  sign = random.choice([-1, 1])
  px = -dy / dist * sign
  py = dx / dist * sign

  # offset magnitude: 10-30% of distance
  spread = random.uniform(0.10, 0.30) * MOUSE_CONTROL_POINT_SPREAD / 0.15 * dist

  # control points at 1/3 and 2/3 along the line, offset perpendicularly
  cp1 = (
    start[0] + dx * 0.33 + px * spread,
    start[1] + dy * 0.33 + py * spread,
  )
  cp2 = (
    start[0] + dx * 0.66 + px * spread * 0.6,
    start[1] + dy * 0.66 + py * spread * 0.6,
  )
  return (cp1, cp2)


def _point_count_for_distance(dist: float) -> int:
  """Scale point count with movement distance."""
  if dist < 30:
    return random.randint(2, 3)
  elif dist < 100:
    return random.randint(4, 6)
  elif dist < 300:
    return random.randint(6, 8)
  else:
    return random.randint(8, 12)


def interpolate_path(
  start: tuple[float, float], end: tuple[float, float]
) -> list[tuple[int, int]]:
  """Generate a humanized mouse path from start to end using cubic Bezier interpolation.
  Returns a list of (x, y) integer coordinate pairs."""
  dx = end[0] - start[0]
  dy = end[1] - start[1]
  dist = math.hypot(dx, dy)

  # trivial case: no movement or sub-pixel
  if dist < 2.0:
    return [(round(end[0]), round(end[1]))]

  # determine if overshoot is needed
  overshoot = dist > MOUSE_OVERSHOOT_THRESHOLD_PX
  if overshoot:
    # overshoot target by 5-15px past the endpoint
    overshoot_dist = random.uniform(5.0, 15.0)
    angle = math.atan2(dy, dx)
    overshoot_target = (
      end[0] + math.cos(angle) * overshoot_dist,
      end[1] + math.sin(angle) * overshoot_dist,
    )
  else:
    overshoot_target = None

  # main curve to target (or overshoot point)
  main_end = overshoot_target if overshoot else end
  num_points = _point_count_for_distance(dist)
  cp1, cp2 = generate_control_points(start, main_end)

  path = []
  for i in range(num_points):
    t_linear = i / max(num_points - 1, 1)
    t = ease_in_out(t_linear)
    px, py = bezier_point(t, start, cp1, cp2, main_end)
    # add micro-jitter
    px += random.gauss(0, MOUSE_JITTER_SIGMA_PX)
    py += random.gauss(0, MOUSE_JITTER_SIGMA_PX)
    path.append((round(px), round(py)))

  # corrective curve back from overshoot to actual target
  if overshoot and overshoot_target:
    correction_points = random.randint(2, 4)
    cp1_c, cp2_c = generate_control_points(overshoot_target, end)
    for i in range(1, correction_points + 1):
      t_linear = i / correction_points
      t = ease_in_out(t_linear)
      px, py = bezier_point(t, overshoot_target, cp1_c, cp2_c, end)
      px += random.gauss(0, MOUSE_JITTER_SIGMA_PX)
      py += random.gauss(0, MOUSE_JITTER_SIGMA_PX)
      path.append((round(px), round(py)))

  # ensure final point is exactly the target
  path[-1] = (round(end[0]), round(end[1]))
  return path
