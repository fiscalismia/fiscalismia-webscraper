# Claude Code Agent Prompt: CDP Stealth & Human Mouse Simulation

## Objective

Extend the Fiscalismia Webscraper — a FastAPI + Playwright CDP screencast application — with two new capabilities:

1. **Human mouse movement simulation** via server-side Bezier curve interpolation of sparse client coordinates
2. **Playwright CDP session stealth hardening** to reduce bot detection signals from Cloudflare and similar systems

The implementation must integrate cleanly with the existing architecture, follow existing project conventions, and be production-ready for containerized deployment.

---

## Existing Project Context

Read `CLAUDE.md` in the project root for the full architecture overview. Key facts:

- **Stack:** Python 3.13+, FastAPI, Uvicorn + uvloop, Playwright (headless Chromium), PyJWT auth
- **Entry point:** `main.py` → loads `api.main:fastapi`
- **Browser lifecycle:** `api/browser.py` — singleton shared Chromium via FastAPI `lifespan` context manager
- **CDP session flow:** `POST /rest/cdp/start` creates a page + navigates → returns `session_id` → client connects `WS /ws/session/{id}?token=<jwt>` → server streams CDP screencast frames (base64 JPEG) over WebSocket
- **Current mouse input path:** Client sends mouse coordinates over WebSocket at ~64ms intervals → server dispatches them directly to CDP via `Input.dispatchMouseEvent` as discrete jumps
- **Config:** `api/config.py` holds constants (route prefixes, CDP screencast params: JPEG quality 50, 1280×720, every frame)
- **Auth:** JWT Bearer at router level for REST, query param `?token=<jwt>` for WebSocket
- **Logging:** Custom `ColoredLogger` singleton from `api.logger` — use this, not stdlib `logging`
- **Deployment:** Podman container, Supervisor managing Nginx (port 8444 SSL, PROXY protocol v2) + Uvicorn (port 3003 internal)

### Conventions to Follow

- Organize new code as FastAPI `APIRouter` instances in subpackages under `api/`
- JWT protection via `dependencies=[Depends(JWTBearer())]` at router level for REST endpoints
- WebSocket auth via `?token=<jwt>` query parameter validated inside the handler with `decode_jwt()`
- Use `api.logger.ColoredLogger` for all logging
- Keep config constants in `api/config.py`
- All async code runs on uvloop automatically — no special imports needed
- Follow the existing file/module naming patterns

---

## Part 1: Human Mouse Movement Simulation

### Problem

The client (browser canvas frontend) captures real user mouse coordinates and sends them over WebSocket at ~64ms intervals (limited by `requestAnimationFrame` or throttling). When the server dispatches these directly to CDP via `Input.dispatchMouseEvent`, the resulting mouse trajectory consists of discrete coordinate jumps at constant 64ms intervals. This is a high-priority bot detection signal because:

- Real mice report at 8–10ms intervals (125Hz USB) and browsers fire `mousemove` at ~16.67ms (60Hz refresh)
- Real mouse paths follow smooth curves, not point-to-point teleportation
- Constant inter-event timing is a dead giveaway for automation
- Cloudflare actively analyzes mouse trajectory entropy

### Solution: Server-Side Bezier Interpolation Pipeline

Build a server-side interpolation engine that sits between the WebSocket input handler and the CDP dispatch layer:

```
Client Canvas (64ms sparse coords) → WebSocket → Server Interpolation Engine → CDP Dispatcher (8-12ms variable timing)
```

### Implementation Requirements

#### 1. Create `api/mouse/interpolation.py` — Bezier Curve Path Generator

Implement a cubic Bezier interpolation function that:

- Takes two points (previous position, new position) and generates 2–12 intermediate points
- Scales point count with distance:
  - `<30px` → 2–3 intermediate points
  - `30–100px` → 4–6 points
  - `100–300px` → 6–8 points
  - `>300px` → 8–12 points, with overshoot-and-correct behavior
- Uses the cubic Bezier formula: `B(t) = (1-t)³·P₀ + 3(1-t)²·t·P₁ + 3(1-t)·t²·P₂ + t³·P₃`
- Places control points on **one side** of the direct path (not S-shaped oscillation) — humans produce single-arc trajectories during fast movements
- Control point perpendicular deviation: **10–30% of total displacement distance**, randomized
- Applies a **cubic ease-in-out** function on the Bezier parameter `t` for natural velocity profiling (acceleration in first 15–25%, cruise in middle 50–70%, deceleration in final 15–25%)
- Adds **Gaussian micro-jitter** of ±0.5–2px to each generated coordinate (`x += gauss(0, 0.5)`, `y += gauss(0, 0.5)`)
- For movements >500px: generates a primary Bezier path that **overshoots** the target by 5–15px, followed by a short corrective Bezier curve back to the actual target (Fitts's Law behavior)
- Returns a list of `(x: float, y: float)` tuples

**Optionally** consider layering Perlin noise for more organic micro-variation: `x += perlin_1d(t * 0.1) * 1.5`. The `vnoise` package (`pip install vnoise`) provides vectorized Perlin noise. This is a nice-to-have enhancement.

**Library options to evaluate** (pick one or implement from scratch — document the decision):

| Library | Install | Notes |
|---------|---------|-------|
| `python_ghost_cursor` | `pip install python_ghost_cursor` | Port of ghost-cursor (62K+ weekly npm downloads). Returns coordinate arrays. Bezier-based with overshoot. |
| `OxyMouse` | `pip install oxymouse` | By Oxylabs. Supports Bezier, Gaussian, Perlin, custom algorithms. Clean `generate_coordinates()` API. |
| `windmouse` | `pip install windmouse` | Physics-based WindMouse algorithm — gravity + wind forces create organic wandering. More varied than pure Bezier. |
| Custom implementation | — | Full control, no dependency. Use numpy for the math. |

**Decision criteria:** Prefer a library that returns raw coordinate arrays without browser dependency (so it's usable with any CDP client). If using a library, wrap it in a thin adapter so the interpolation engine is swappable. If implementing from scratch, use `numpy` for vectorized math.

#### 2. Create `api/mouse/timing.py` — Variable Timing Generator

Generate realistic inter-event timing for dispatching interpolated points:

- **Base interval:** 8–12ms (matching real 125Hz USB mouse → 60Hz browser coalescing)
- **Gaussian jitter on every interval:** `interval = base_interval + gauss(0, 2.5)`, clamped to minimum 4ms
- **Never dispatch at constant intervals** — this is the single most detectable timing signal
- Include occasional **micro-pauses of 20–50ms** (probability ~5% per movement segment) simulating brief human hesitation
- The total time budget per segment is approximately the original 64ms gap divided among N interpolated points

#### 3. Create `api/mouse/dispatcher.py` — CDP Mouse Event Dispatcher

An async dispatcher that consumes interpolated coordinate + timing pairs and sends them to CDP:

- Uses `Input.dispatchMouseEvent` with type `mouseMoved` for each intermediate point
- For click actions: dispatches the full Bezier path of `mouseMoved` events leading to the click target, then dispatches `mousePressed` + `mouseReleased` at the final position
- **Never click at element centers** — randomize the click position within the element's bounding box (offset from center by random ±30% of width/height)
- Sends `pointerType: "mouse"` on all events
- Respects the variable timing from the timing generator via `asyncio.sleep()` between dispatches
- Tracks the current cursor position state so subsequent movements start from the correct location
- Handles the `mouseDown`/`mouseUp` timing: realistic gap of 50–150ms between press and release (randomized)

#### 4. Create `api/mouse/__init__.py` — Module Facade

Export a clean async interface:

```python
async def dispatch_mouse_move(cdp_session, from_point: tuple, to_point: tuple) -> None:
    """Interpolate and dispatch a humanized mouse movement between two points."""

async def dispatch_mouse_click(cdp_session, target_point: tuple, from_point: tuple, element_bbox: dict | None = None) -> None:
    """Move to target with humanized path, then click with realistic timing."""
```

#### 5. Integrate into `api/websockets/stream_cdp.py`

Modify the WebSocket handler to:

- Buffer incoming mouse coordinates from the client
- Track the last known cursor position
- On each new coordinate received: call the interpolation pipeline instead of dispatching directly
- The interpolated dispatch should run as an async task so it doesn't block frame streaming

#### 6. Add config constants to `api/config.py`

```python
# Mouse interpolation settings
MOUSE_BASE_INTERVAL_MS = 10       # Base inter-event timing (ms)
MOUSE_TIMING_JITTER_SIGMA = 2.5   # Gaussian jitter standard deviation (ms)
MOUSE_MIN_INTERVAL_MS = 4         # Minimum dispatch interval (ms)
MOUSE_JITTER_SIGMA_PX = 0.5       # Coordinate micro-jitter (px)
MOUSE_CONTROL_POINT_SPREAD = 0.15 # Bezier control point deviation (fraction of distance)
MOUSE_OVERSHOOT_THRESHOLD_PX = 500 # Distance threshold for overshoot behavior
MOUSE_CLICK_HOLD_MIN_MS = 50      # Min press-to-release gap (ms)
MOUSE_CLICK_HOLD_MAX_MS = 150     # Max press-to-release gap (ms)
```

---

## Part 2: CDP Session Stealth Hardening

### Problem

Even with perfect mouse simulation, Cloudflare and similar bot detection systems catch automation through:

1. **CDP protocol-level leaks** — `Runtime.Enable` side effects detectable via `console` object inspection
2. **JavaScript environment inconsistencies** — `navigator.webdriver`, missing `window.chrome.runtime`, empty `navigator.plugins`
3. **Browser launch fingerprints** — "Chrome for Testing" binary, automation infobar, non-standard viewport
4. **Cross-domain iframe `screenX`/`screenY` bug** (Chromium #40280325) — CDP clicks inside cross-origin iframes (like Cloudflare Turnstile) produce iframe-relative coordinates instead of screen-relative, yielding suspiciously small values

### Implementation Requirements

#### 1. Create `api/stealth/__init__.py` — Stealth Configuration Module

Central module that orchestrates all stealth measures. Export:

```python
async def apply_stealth(page, cdp_session) -> None:
    """Apply all stealth patches to a page/CDP session before navigation."""

def get_stealth_browser_args() -> list[str]:
    """Return Chrome launch arguments for stealth mode."""
```

#### 2. Create `api/stealth/browser_args.py` — Chrome Launch Arguments

Return a list of stealth-oriented Chrome launch flags:

```python
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",  # Prevents navigator.webdriver=true and automation infobar
    "--no-first-run",
    "--no-default-browser-check",
    "--no-service-autorun",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--window-size=1600,900",  # Realistic viewport — non-standard sizes are flagged
]
```

**Important notes to document in code comments:**

- `--disable-blink-features=AutomationControlled` is the simplest fix for `navigator.webdriver` — it prevents Chrome from setting it to `true` and suppresses the "Chrome is being controlled by automated software" infobar
- `--window-size=1600,900` should match the most common desktop resolution. Non-standard sizes (like Playwright's default 1280×720) are a fingerprinting signal. **Update `api/config.py` CDP screencast dimensions to match.**
- For headless mode: use `--headless=new` (Chrome 112+) which produces near-authentic fingerprints including `window.chrome`, realistic `navigator.plugins`, and proper user agent. Better yet, document the Xvfb alternative for maximum stealth.
- Avoid "Chrome for Testing" binary — use system-installed Chrome via Playwright's `channel='chrome'` option. The testing binary has a different fingerprint that anti-bot systems recognize.

#### 3. Create `api/stealth/js_patches.py` — JavaScript Stealth Injections

A collection of JavaScript snippets to inject via `Page.addScriptToEvaluateOnNewDocument` **before any page loads**. Each patch should be a named string constant with a docstring explaining what detection vector it addresses:

**Required patches:**

| Patch | Purpose | Detection Vector |
|-------|---------|-----------------|
| `PATCH_WEBDRIVER` | Delete/redefine `navigator.webdriver` to `undefined` | Basic automation detection (fallback if `--disable-blink-features` is insufficient) |
| `PATCH_CHROME_RUNTIME` | Define `window.chrome.runtime` with realistic `connect()` and `sendMessage()` methods | Missing Chrome extension API detection |
| `PATCH_PLUGINS` | Populate `navigator.plugins` with Chrome PDF Plugin, Chrome PDF Viewer, Native Client | Empty plugin array detection (headless giveaway) |
| `PATCH_PERMISSIONS` | Override `navigator.permissions.query()` to return realistic results for `{name: 'notifications'}` | Permissions API anomaly detection |
| `PATCH_WEBGL_VENDOR` | Spoof WebGL vendor/renderer strings to realistic values, avoid SwiftShader signatures | GPU fingerprint detection |
| `PATCH_SCREEN_XY` | Fix CDP cross-origin iframe `screenX`/`screenY` bug — intercept MouseEvent constructor to correct coordinates for events inside cross-origin iframes | Cloudflare Turnstile iframe detection (Chromium bug #40280325) |

**Implementation approach:**

```python
# Each patch is a standalone JS string
PATCH_WEBDRIVER = """
// Fallback: redefine navigator.webdriver as undefined
// Primary defense is --disable-blink-features=AutomationControlled launch flag
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});
"""

# Compose all patches into a single injection
ALL_PATCHES = "\n".join([
    PATCH_WEBDRIVER,
    PATCH_CHROME_RUNTIME,
    PATCH_PLUGINS,
    PATCH_PERMISSIONS,
    PATCH_WEBGL_VENDOR,
    PATCH_SCREEN_XY,
])
```

**For the `screenX`/`screenY` iframe patch:** Reference the CDP-bug-MouseEvent-screenX-screenY-patcher project on GitHub (`TheFalloutOf76/CDP-bug-MouseEvent-.screenX-.screenY-patcher`). The core idea is to intercept MouseEvent creation and adjust coordinates when the event target is inside a cross-origin iframe. Until Chrome stable fully merges the fix (Chromium issue #40280325, patched September 2025 but rollout to stable may be incomplete), this JS patch is necessary. **Add a code comment noting this patch can be removed once the Chrome fix is confirmed in the stable channel used by the project.**

**Critical implementation note:** All patches must be injected via CDP `Page.addScriptToEvaluateOnNewDocument`, which runs the script in every frame (including iframes) before any page JavaScript executes. This is more reliable than `page.evaluate()` which runs after page load.

#### 4. Create `api/stealth/cdp_patches.py` — CDP Protocol-Level Patches

Address `Runtime.Enable` detection — the most critical CDP-level leak:

- **Problem:** Every automation library (Puppeteer, Playwright, Selenium) automatically sends `Runtime.Enable`, which creates detectable side effects in the `console` object that page scripts can observe. This is the single most reliable detection signal used by Cloudflare and DataDome.
- **Solution options (document all, implement the most appropriate for our raw CDP session):**

  1. **For raw CDP sessions (our case):** Avoid calling `Runtime.Enable`. Use `Runtime.evaluate` with `contextId` targeting an isolated execution context instead. Create helper functions that wrap common `Runtime.evaluate` patterns.
  2. **For Playwright users:** Consider `Patchright` (a Playwright fork that patches `Runtime.Enable` at source level) or `rebrowser-patches` (disables automatic `Runtime.Enable` and runs evaluated scripts in isolated execution contexts).
  3. **Document both approaches** with code comments explaining when each is appropriate.

```python
async def setup_isolated_context(cdp_session) -> int:
    """Create an isolated execution context that avoids Runtime.Enable detection.
    
    Returns the contextId for use with Runtime.evaluate.
    """

async def safe_evaluate(cdp_session, expression: str, context_id: int) -> any:
    """Evaluate JS in an isolated context without triggering Runtime.Enable side effects."""
```

**Also address `sourceURL` leaks:** When Playwright/Puppeteer evaluate scripts, they often append `//# sourceURL=...` comments that contain identifiable strings. Strip or replace these.

#### 5. Modify `api/browser.py` — Integrate Stealth into Browser Lifecycle

Update the browser launch in the `lifespan` context manager:

- Pass stealth Chrome launch arguments from `api/stealth/browser_args.py`
- Use `channel='chrome'` to prefer system-installed Chrome over "Chrome for Testing"
- After creating each new page (in `new_page()`), automatically apply stealth patches via `api/stealth/apply_stealth()`
- **Document the Xvfb alternative:** For maximum stealth on Linux, running headful Chrome inside Xvfb (X Virtual Framebuffer) is indistinguishable from a real desktop session. Add a code comment with the Xvfb setup command and a note about when to prefer this over `--headless=new`.

```python
# In browser.py, update launch to include stealth args
from api.stealth import get_stealth_browser_args

browser = await playwright.chromium.launch(
    headless=True,
    args=get_stealth_browser_args(),
    channel="chrome",  # Use system Chrome, not Chrome for Testing
)
```

#### 6. Add Stealth Config to `api/config.py`

```python
# Stealth configuration
STEALTH_VIEWPORT_WIDTH = 1600
STEALTH_VIEWPORT_HEIGHT = 900
STEALTH_USER_AGENT = None  # None = use browser default (safest). Set only if needed.
STEALTH_WEBGL_VENDOR = "Google Inc. (NVIDIA)"
STEALTH_WEBGL_RENDERER = "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)"
```

---

## Part 3: Integration & Testing

### 1. Update `api/config.py` CDP Screencast Dimensions

Change CDP screencast resolution from 1280×720 to match the stealth viewport (1600×900), or make it configurable. The viewport size and screencast dimensions should be consistent.

### 2. Create `tests/test_mouse_interpolation.py`

Unit tests for the mouse interpolation engine:

- Test that output point count scales with distance
- Test that all output points lie within a reasonable bounding box around the start→end line
- Test that timing intervals are variable (not constant)
- Test that overshoot behavior triggers for long distances
- Test that micro-jitter is applied (no two identical consecutive coordinates)
- Test edge cases: zero-distance move, very short distance (<2px), diagonal vs axis-aligned

### 3. Create `tests/test_stealth_patches.py`

Unit tests for stealth configuration:

- Test that `get_stealth_browser_args()` returns the required flags
- Test that all JS patches are valid JavaScript (syntax check)
- Test that the patches injection function calls `Page.addScriptToEvaluateOnNewDocument`

### 4. Update `requirements.txt`

Add any new dependencies (e.g., `numpy`, `vnoise`, chosen mouse library). Pin versions.

### 5. Update `CLAUDE.md`

Add a new section documenting:

- The mouse interpolation pipeline architecture
- The stealth hardening layers and what each addresses
- New modules and their responsibilities
- New config constants
- How to test the stealth measures (e.g., visit `bot.sannysoft.com` or use `rebrowser-bot-detector`)

---

## Implementation Order

Execute in this order to maintain a working system at each step:

1. **Stealth browser args** (`api/stealth/browser_args.py`) + update `api/browser.py` launch — lowest risk, immediate benefit
2. **JS stealth patches** (`api/stealth/js_patches.py`) + injection in page creation — builds on step 1
3. **CDP protocol patches** (`api/stealth/cdp_patches.py`) — most complex stealth layer
4. **Mouse interpolation engine** (`api/mouse/interpolation.py` + `timing.py`) — independent module, testable in isolation
5. **Mouse CDP dispatcher** (`api/mouse/dispatcher.py`) — connects interpolation to CDP
6. **WebSocket handler integration** — wires everything together
7. **Tests** — validate all layers
8. **Config and docs updates** — finalize

---

## Quality Requirements

- **Type hints** on all function signatures (use `tuple[float, float]` for coordinates)
- **Docstrings** on all public functions explaining purpose, parameters, and return values
- **Code comments** explaining *why* each stealth measure exists and what detection vector it counters — this codebase is a learning resource
- **Error handling** — graceful degradation if a stealth patch fails (log warning, don't crash the session)
- **No hardcoded magic numbers** — all tunable parameters in `api/config.py`
- **Async-first** — all CDP interaction must be async. The interpolation math itself can be sync (it's CPU-bound and fast)
- **Thread safety** — the mouse position state must be per-session, not global (multiple concurrent CDP sessions may exist)

---

## Security Considerations

- This is a **defensive security research tool** for understanding bot detection mechanisms. All stealth measures are applied to the project's own controlled browser instances.
- JWT authentication protects all endpoints — no changes to the auth model
- No secrets or credentials are embedded in stealth patches
- The screenX/screenY iframe patch is a workaround for a known Chromium bug, not an exploit

---

## Reference Resources

These resources informed the technical approach. Consult them for implementation details:

| Resource | URL | Relevance |
|----------|-----|-----------|
| ghost-cursor (JS) | `github.com/Xetera/ghost-cursor` | Bezier mouse movement reference implementation |
| python_ghost_cursor | `github.com/mcolella14/python_ghost_cursor` | Python port of ghost-cursor |
| OxyMouse | `github.com/oxylabs/OxyMouse` | Multi-algorithm mouse movement library |
| WindMouse algorithm | `ben.land/post/2021/04/25/windmouse-human-mouse-movement/` | Physics-based alternative to Bezier |
| rebrowser-patches | `github.com/rebrowser/rebrowser-patches` | Runtime.Enable fix, CDP stealth patches |
| rebrowser-bot-detector | `github.com/rebrowser/rebrowser-bot-detector` | Testing tool — checks for common detection vectors |
| CDP-bug-MouseEvent-screenX-screenY-patcher | `github.com/TheFalloutOf76/CDP-bug-MouseEvent-.screenX-.screenY-patcher` | Turnstile iframe coordinate fix |
| puppeteer-extra-plugin-stealth | `github.com/berstend/puppeteer-extra` | 17 evasion modules, extractable via `npx extract-stealth-evasions` |
| Patchright | Playwright fork | Drop-in Playwright replacement with Runtime.Enable patch |
| Chrome DevTools Protocol — Input domain | `chromedevtools.github.io/devtools-protocol/tot/Input/` | CDP Input.dispatchMouseEvent specification |
| Cloudflare Bot Management architecture | `developers.cloudflare.com/reference-architecture/diagrams/bots/bot-management/` | Understanding the 5 detection engines |
| Cloudflare Bot Score docs | `developers.cloudflare.com/bots/concepts/bot-score/` | How the unified bot score works |

---

## File Structure After Implementation

```
api/
├── __init__.py
├── main.py              # Updated: register new routers if needed
├── browser.py           # Updated: stealth args, channel='chrome', apply patches on page creation
├── config.py            # Updated: mouse + stealth constants, viewport dimensions
├── security.py
├── logger.py
├── colors.py
├── health_check/
│   └── ...
├── rest/
│   └── stream_cdp.py
├── websockets/
│   └── stream_cdp.py      # Updated: integrate mouse interpolation pipeline
├── mouse/
│   ├── __init__.py       # Public API: dispatch_mouse_move(), dispatch_mouse_click()
│   ├── interpolation.py  # Bezier curve path generation
│   ├── timing.py         # Variable timing generation
│   └── dispatcher.py     # CDP Input.dispatchMouseEvent async dispatcher
└── stealth/
    ├── __init__.py       # Public API: apply_stealth(), get_stealth_browser_args()
    ├── browser_args.py   # Chrome launch flags
    ├── js_patches.py     # JavaScript stealth injections
    └── cdp_patches.py    # CDP protocol-level patches (Runtime.Enable avoidance)
tests/
├── test_ws.py                    # Existing
├── test_mouse_interpolation.py   # New: unit tests for mouse engine
└── test_stealth_patches.py       # New: unit tests for stealth config
```