"""Unit tests for mouse interpolation, timing, and path generation."""

import math
from api.mouse.interpolation import bezier_point, ease_in_out, interpolate_path
from api.mouse.timing import movement_delay, micro_pause_chance


class TestEaseInOut:
  def test_boundaries(self):
    assert ease_in_out(0.0) == 0.0
    assert ease_in_out(1.0) == 1.0

  def test_midpoint(self):
    assert ease_in_out(0.5) == 0.5

  def test_monotonic(self):
    values = [ease_in_out(t / 100) for t in range(101)]
    for i in range(len(values) - 1):
      assert values[i] <= values[i + 1]


class TestBezierPoint:
  def test_endpoints(self):
    p0 = (0.0, 0.0)
    p1 = (10.0, 20.0)
    p2 = (30.0, 20.0)
    p3 = (40.0, 0.0)
    start = bezier_point(0.0, p0, p1, p2, p3)
    end = bezier_point(1.0, p0, p1, p2, p3)
    assert abs(start[0] - p0[0]) < 1e-9
    assert abs(start[1] - p0[1]) < 1e-9
    assert abs(end[0] - p3[0]) < 1e-9
    assert abs(end[1] - p3[1]) < 1e-9


class TestInterpolatePath:
  def test_short_distance_few_points(self):
    path = interpolate_path((100, 100), (110, 105))
    assert len(path) <= 5

  def test_medium_distance(self):
    path = interpolate_path((0, 0), (200, 150))
    assert len(path) >= 4

  def test_long_distance_many_points(self):
    path = interpolate_path((0, 0), (800, 600))
    assert len(path) >= 6

  def test_overshoot_long_distance(self):
    """Paths >500px should have more points due to overshoot correction."""
    path = interpolate_path((0, 0), (600, 0))
    # overshoot adds correction points, total should be more than base
    assert len(path) >= 8

  def test_ends_at_target(self):
    target = (500, 300)
    path = interpolate_path((0, 0), target)
    assert path[-1] == target

  def test_starts_near_origin(self):
    start = (100, 200)
    end = (400, 500)
    path = interpolate_path(start, end)
    # first point should be near start (within jitter)
    dx = abs(path[0][0] - start[0])
    dy = abs(path[0][1] - start[1])
    assert dx < 10 and dy < 10

  def test_within_bounding_box(self):
    start = (100, 100)
    end = (300, 300)
    path = interpolate_path(start, end)
    for x, y in path:
      # generous bounding box accounting for curve and jitter
      assert 50 <= x <= 350, f"x={x} out of bounds"
      assert 50 <= y <= 350, f"y={y} out of bounds"

  def test_zero_distance(self):
    path = interpolate_path((100, 100), (100, 100))
    assert len(path) == 1
    assert path[0] == (100, 100)

  def test_very_short_distance(self):
    path = interpolate_path((100, 100), (101, 100))
    assert len(path) >= 1
    assert path[-1] == (101, 100)

  def test_diagonal_movement(self):
    path = interpolate_path((0, 0), (500, 500))
    assert len(path) >= 4
    assert path[-1] == (500, 500)

  def test_integer_coordinates(self):
    path = interpolate_path((0, 0), (300, 200))
    for x, y in path:
      assert isinstance(x, int)
      assert isinstance(y, int)

  def test_no_identical_consecutive_for_long_paths(self):
    """Micro-jitter should prevent long runs of identical points."""
    path = interpolate_path((0, 0), (500, 400))
    if len(path) > 3:
      identical_count = sum(1 for i in range(len(path) - 1) if path[i] == path[i + 1])
      # allow some but not all identical
      assert identical_count < len(path) - 1


class TestMovementDelay:
  def test_delay_range(self):
    for _ in range(100):
      d = movement_delay()
      assert d >= 0.004  # min 4ms
      assert d < 0.050   # reasonable upper bound

  def test_returns_float(self):
    assert isinstance(movement_delay(), float)


class TestMicroPause:
  def test_returns_none_or_float(self):
    results = [micro_pause_chance() for _ in range(200)]
    nones = [r for r in results if r is None]
    pauses = [r for r in results if r is not None]
    # should get some of each
    assert len(nones) > 0
    assert len(pauses) > 0
    for p in pauses:
      assert 0.020 <= p <= 0.050
