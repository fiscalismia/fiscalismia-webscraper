# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fiscalismia Webscraper is a FastAPI backend for Playwright browser automation on a remote VM, exposing live browser interaction recordings via WebSocket API. Routes are protected with JWT Bearer authentication.

## Tech Stack

- **Language:** Python 3.13+
- **Framework:** FastAPI with Uvicorn (ASGI)
- **Auth:** PyJWT (HS256 Bearer tokens)
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
  --build-arg BUILD_VERSION=0.9.1 \
  -t fiscalismia-webscraper:0.9.1 "."

podman run --env-file .env --rm -it -p 3003:3003 \
  --name fiscalismia-webscraper fiscalismia-webscraper:0.9.1
```

## Architecture

**Entry point:** `main.py` → runs `uvicorn` loading `app.main:api`

**App structure (`app/`):**
- `main.py` — FastAPI app factory, registers routers with prefix/dependency injection, lifespan context manager for Playwright browser lifecycle
- `browser.py` — Playwright browser lifecycle manager. Launches a single shared headless Chromium at startup, exposes `new_page()` for creating contexts/pages, tracks active CDP sessions, and cleans up on shutdown
- `config.py` — Constants (stream endpoint prefix, global timeout)
- `security.py` — `JWTBearer` dependency class and `decode_jwt()`. Protected routes use `dependencies=[Depends(JWTBearer())]`
- `health_check/` — Unprotected `/hc` (health status, uptime, version) and `/version` endpoints
- `stream/` — CDP browser automation endpoints under `/fastapi/fiscalismia/stream`:
  - `test_cdp_websocket.py` — Two routers:
    - `router` (JWT-protected): `POST /start` — creates a headless Chromium page, navigates to a URL, returns a `session_id`
    - `ws_router` (unprotected, auth via query param): `WebSocket /{session_id}/ws?token=<jwt>` — streams CDP screencast frames (base64 JPEG) over WebSocket
- `logging/logger.py` — Singleton `ColoredLogger` with custom ANSI formatting (Europe/Berlin timezone)
- `colors.py` — ANSI escape code definitions

**Tests (`tests/`):**
- `test_ws.py` — End-to-end integration test for the CDP streaming endpoints (POST start + WebSocket frame reception)

**Container architecture:** Supervisor manages two processes:
- Nginx (port 5000, external) → reverse proxies to Uvicorn (port 3003, internal)
- WebSocket upgrade support and CORS headers for localhost origins (3001, 4173)

## Environment Variables

- `JWT_SECRET` — Required for JWT token validation (HS256)
- `SNYK_TOKEN` — For security scanning (CI pipeline)
- `FASTAPI_BUILD_VERSION` — Set via Docker `BUILD_VERSION` build arg, exposed as `APP_VERSION` to Uvicorn

## Key Patterns

- Routes are organized as FastAPI `APIRouter` instances in subpackages, included in `app/main.py`
- JWT protection is applied at the router level via `dependencies=[Depends(JWTBearer())]`, not per-endpoint
- WebSocket endpoints use a separate router without `JWTBearer` dependency (since `HTTPBearer` doesn't support WebSocket). Auth is validated via `?token=<jwt>` query parameter inside the handler using `decode_jwt()`
- Playwright browser lifecycle is managed via FastAPI's `lifespan` context manager — a single shared Chromium instance is launched at startup and closed on shutdown
- CDP screencast is started only after the WebSocket frame listener is attached, to avoid losing initial frames
- Logging uses the custom `ColoredLogger` singleton (import from `app.logging.logger`), not stdlib `logging` directly
- Version string uses `major.minor.build` format; `.replace_me` in `app/__init__.py` is substituted by CI pipeline
