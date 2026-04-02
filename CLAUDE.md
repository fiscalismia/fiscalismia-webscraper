# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fiscalismia Webscraper is a FastAPI backend for Playwright browser automation on a remote VM, exposing live browser interaction recordings via WebSocket API. Routes are protected with JWT Bearer authentication.

## Tech Stack

- **Language:** Python 3.13+
- **Framework:** FastAPI with Uvicorn (ASGI) + uvloop event loop
- **Auth:** PyJWT (HS256 Bearer tokens)
- **Browser Automation:** Playwright (headless Chromium, CDP screencast)
- **Deployment:** Podman/Docker, Nginx reverse proxy, Supervisor process manager
- **Config:** python-dotenv (.env file)

## Running Locally

```bash
# Venv setup (one-time)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run dev server
python main.py
# Health check: http://127.0.0.1:3003/hc
```

## Container Build & Run (Podman)

```bash
podman build --pull --no-cache --rm -f "Dockerfile" \
  --build-arg BUILD_VERSION=0.9.2 \
  -t fiscalismia-webscraper:0.9.2 "."

podman run --env-file .env --rm -it -p 3003:3003 \
  --name fiscalismia-webscraper fiscalismia-webscraper:0.9.2
```

## Architecture

**Entry point:** `main.py` → runs `uvicorn` with uvloop loading `api.main:fastapi`

**App structure (`api/`):**
- `main.py` — FastAPI app factory, registers routers with prefix/dependency injection, lifespan context manager for Playwright browser lifecycle
- `browser.py` — Playwright browser lifecycle manager. Launches a single shared headless Chromium at startup, exposes `new_page()` for creating contexts/pages, tracks active CDP sessions, and cleans up on shutdown
- `config.py` — Constants (route prefixes, global timeout, CDP screencast parameters: JPEG quality 50, 1600x900, viewport dimensions, mouse movement tuning, stealth WebGL spoofing)
- `security.py` — `JWTBearer` dependency class and `decode_jwt()`. Protected routes use `dependencies=[Depends(JWTBearer())]`
- `health_check/` — Unprotected `/hc` (health status, uptime, version) and `/version` endpoints
- `rest/stream_cdp.py` — JWT-protected REST router: `POST /cdp/start` — creates a headless Chromium page, navigates to a URL, returns a `session_id`
- `websockets/stream_cdp.py` — WebSocket router (auth via query param): `WS /session/{session_id}?token=<jwt>` — streams CDP screencast frames (base64 JPEG in JSON) over WebSocket with 10s keepalive ping
- `logger.py` — Singleton `ColoredLogger` with custom ANSI formatting (Europe/Berlin timezone)
- `colors.py` — ANSI escape code definitions
- `stealth/` — Anti-bot-detection hardening: `browser_args.py` (Chrome launch flags to disable automation signals), `js_patches.py` (JS injections for navigator.webdriver, chrome.runtime, plugins, permissions, WebGL), `cdp_patches.py` (CDP-level script injection via Page.addScriptToEvaluateOnNewDocument). `apply_stealth(page, cdp_session)` is the public API
- `mouse/` — Humanized mouse movement simulation: `interpolation.py` (cubic Bezier path generation with ease-in-out, overshoot, micro-jitter), `timing.py` (variable inter-point delays with micro-pauses), `dispatcher.py` (async CDP mouse event dispatch with humanized trajectories and click timing). `dispatch_mouse_move()` and `dispatch_mouse_click()` are the public API

**Route map (prefixes defined in `api/config.py`):**
- `GET /` — root info (unprotected)
- `GET /fastapi/fiscalismia/hc` — health check (unprotected)
- `GET /fastapi/fiscalismia/version` — version (unprotected)
- `POST /fastapi/fiscalismia/rest/cdp/start` — create CDP session (JWT-protected)
- `WS /fastapi/fiscalismia/ws/session/{id}?token=<jwt>` — screencast stream (query param auth)

**Container architecture:** Supervisor manages two processes:
- Nginx (port 8444 SSL with PROXY protocol v2) → reverse proxies to Uvicorn (port 3003, internal)
- Nginx splits traffic into three location blocks: `/fastapi/fiscalismia/ws/` (WebSocket streaming, zero-buffering, gzip off, 1h timeouts), `/fastapi/fiscalismia/rest/` (REST, buffered, gzip on), `/` (catch-all for health checks)
- External ingress: HAProxy (port 443) → Nginx (port 8444) via TLS passthrough with SNI routing and PROXY protocol v2

## Environment Variables

- `JWT_SECRET` — Required for JWT token validation (HS256)
- `SNYK_TOKEN` — For security scanning (CI pipeline)
- `FASTAPI_BUILD_VERSION` — Set via Docker `BUILD_VERSION` build arg, exposed as `APP_VERSION` to Uvicorn

## Key Patterns

- Routes are organized as FastAPI `APIRouter` instances in subpackages, included in `api/main.py`
- JWT protection is applied at the router level via `dependencies=[Depends(JWTBearer())]`, not per-endpoint
- WebSocket endpoints use a separate router without `JWTBearer` dependency (since `HTTPBearer` doesn't support WebSocket). Auth is validated via `?token=<jwt>` query parameter inside the handler using `decode_jwt()`
- Playwright browser lifecycle is managed via FastAPI's `lifespan` context manager — a single shared Chromium instance is launched at startup and closed on shutdown
- CDP screencast is started only after the WebSocket frame listener is attached, to avoid losing initial frames
- Browser viewport is 1600x900 (matching CDP screencast dimensions) — configured in `api/config.py`
- Stealth hardening is applied per-session via `apply_stealth()` in the REST `/cdp/start` handler. Stealth verification: visit `bot.sannysoft.com` via a CDP session
- Mouse movements are server-side interpolated using cubic Bezier curves with ease-in-out timing, micro-jitter, and overshoot correction for long distances. Client sends target coordinates; server generates the humanized trajectory
- Uvicorn runs with `--loop uvloop` which globally replaces the asyncio event loop. All `import asyncio` usage (Queue, wait_for, await) automatically runs on uvloop — no code changes needed
- Nginx location blocks must match the route prefixes in `api/config.py` (`REST_ENDPOINT`, `WEBSOCKET_ENDPOINT`). If route prefixes change, update `nginx.conf` accordingly
- Logging uses the custom `ColoredLogger` singleton (import from `api.logger`), not stdlib `logging` directly
- Version string uses `major.minor.build` format; `.replace_me` in `api/__init__.py` is substituted by CI pipeline
