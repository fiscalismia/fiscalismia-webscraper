# Agent Prompt — Automated Supermarket prospekt Scraping

## Context

You are working on `fiscalismia-webscraper`, a FastAPI + Playwright backend that exposes headless Chromium sessions over WebSocket (CDP screencast). The frontend renders the remote browser in a `<canvas>` and relays user input (clicks, scrolls, mouse moves) back over the bidirectional WebSocket.

Read `CLAUDE.md` at the project root for the full architecture, route map, tech stack, and key patterns before making any changes.

### Existing flow (interactive)

1. **Frontend** (`admin_WebscrapeSupermarkets.tsx`) passes a preset URL (`https://www.aldi-sued.de/prospekte`) to `Websocket_CDP_Canvas.tsx`.
2. `Websocket_CDP_Canvas` calls `POST /fastapi/rest/cdp/start` with the target URL → backend launches a stealth Chromium page, navigates to the URL, starts CDP screencast, returns a `session_id`.
3. Frontend opens `WS /fastapi/ws/session/{session_id}`, authenticates with a JWT token, and streams JPEG frames to canvas. User input (mouse clicks, moves, scrolls) is sent back over WebSocket as JSON and dispatched server-side via CDP.

This is a **manual, interactive** session where the user drives the remote browser through the canvas. The new feature adds **server-side automated scraping** that runs without user interaction but still streams progress to the same canvas.

---

## Task — Implement an automated scraping route for Aldi Süd weekly prospekt

### Goal

Create a new **JWT-protected REST endpoint** that automates browser interaction on the given URL `https://www.aldi-sued.de/prospekte`:

1. **Dismiss the cookie banner** by clicking the "Nur Notwendige" button:
   ```html
   <button id="onetrust-reject-all-handler">Nur Notwendige</button>
   ```
2. **Click the current week's prospekt link**, which matches this pattern:
   ```html
   <a href="https://prospekt.aldi-sued.de/kw{WEEK}-{YY}-..." class="...cms-multilayout-teaser__link" ...>
     Prospekt ansehen
   </a>
   ```
   The `href` contains a substring in the format `kw{WEEK_OF_YEAR}-{TWO_DIGIT_YEAR}`, e.g. `kw11-26` for calendar week 11 of 2026. Use this pattern to identify the correct link dynamically rather than hardcoding the full URL.
3. For now, that is the complete automation scope — navigate, dismiss cookies, click the prospekt link. The page that opens after clicking is the end state. **Do not implement further scraping logic yet.**

### Design requirements

#### New route

- Create a new router module in path: `api/rest/scrape_supermarkets.py`
- Suggested endpoint: `POST /fastapi/rest/cdp/scrape/supermarket/aldi_prospekt`
- JWT-protected at the router level via `dependencies=[Depends(JWTBearer())]`, consistent with existing patterns.
- The route should return a `session_id` (same as the existing `/cdp/start` endpoint) so the frontend can connect via the existing WebSocket to watch the automation in real time through the canvas.
- Register the new router in `api/main.py` with a prefix constant defined in `api/config.py`.

#### Automation implementation

- Reuse the existing browser lifecycle from `api/browser.py` (`new_page()` for context/page creation).
- Apply stealth hardening via `apply_stealth()` before navigating, same as the existing CDP start handler.
- Use Playwright's native selector engine for element interaction (`page.click()`, `page.wait_for_selector()`, etc.) — **not** the CDP mouse dispatcher. The humanized mouse module is for interactive sessions and testing; automated scraping should use Playwright's reliable, deterministic selectors.
- Implement proper wait strategies: wait for the cookie banner to appear before clicking, wait for navigation/network idle after dismissing it, then locate and click the prospekt link.
- Add sensible timeouts and error handling. If the cookie banner doesn't appear within a timeout, log a warning and continue (it may have been dismissed by a prior session or not shown). If the prospekt link isn't found, return a clear error response.
- After clicking the prospekt link (which opens in a new tab due to `target="_blank"`), switch context to the new page/tab so the CDP screencast follows the new page.

#### Extensibility

This is the **first of many scraping automations**. Structure the code so that:

- The scraping logic is **not inlined in the route handler**. Extract it into a separate async function (or a class/module under e.g. `api/scraping/`) that the route handler calls. This makes it easy to add new scraping workflows (other supermarkets, different data extraction steps) without bloating route files.
- The scraping function should accept the Playwright `page` (and `cdp_session` if needed for screencast) as parameters — it should not manage browser lifecycle itself.
- Consider defining a simple shared interface or base pattern (e.g. an async function signature or abstract base class) that future scraping tasks can follow: `async def scrape(page, cdp_session) -> ScrapeResult`.
- The dynamic week/year detection for the prospekt link should be a utility function that can be tested independently.

#### Scraped data delivery (temp file + REST)
The WebSocket remains a **pure binary JPEG screencast stream**. Do not add JSON messages, text frames, or mixed-type payloads to the WebSocket protocol. Scraped data is delivered separately via REST:

1. **During scraping**, the automation function writes its results to a JSON temp file on disk. File naming convention: `{route_identifier}_{session_id}.json` (e.g. `aldi_prospekt_abc123.json`). Store these in a dedicated temp directory e.g. `./tmp/scrape_results/` which is mounted as tempfs so as ram in docker compose
2. **Signaling completion**: The scraping automation endpoint's initial POST response should include a `results_url` field alongside `session_id`, pointing to a new JWT-protected GET endpoint (e.g. `GET /fastapi/rest/cdp/scrape/results/{session_id}`). The frontend fetches this URL via user button manually once the WebSocket session closes (which signals the automation finished).
3. **The results endpoint** is rest. reads the temp file, returns its contents as JSON, signals error via http status
4. **Lifecycle / cleanup**: Register a cleanup routine — either in the FastAPI lifespan shutdown handler or as a background task — that removes orphaned temp files older than a config variable TTL (e.g. 15 minutes).
5. **Data schema**: For now, define a minimal result model (e.g. `ScrapeResult` with fields like `status`, `session_id`, `target_url`, `prospekt_url`, `timestamp`, and a generic `data: dict | None` for future extracted content). Return this from the results endpoint.

### What NOT to do

- Do not modify the existing `/cdp/start` endpoint or the existing WebSocket handler's core logic. The new route should add to the system, not change existing behavior.
- Do not hardcode the full prospekt URL. Detect the current week dynamically.
- Do not use the humanized mouse dispatcher for automated scraping steps — use Playwright selectors.
- Do not implement data extraction or parsing of the prospekt content yet — that's a future task.

### Testing

- Add an integration test (in `tests/`) that validates the new endpoint returns a `session_id` and that the automation completes without errors. Follow the pattern in `tests/test_ws.py`.
- Add a unit test for the week/year detection utility function.

---

## File references

Inspect these files before starting:

- `CLAUDE.md` — Full architecture and patterns reference
- `api/main.py` — App factory, router registration, lifespan manager
- `api/config.py` — Route prefix constants, CDP/viewport config
- `api/browser.py` — Browser lifecycle, `new_page()`
- `api/security.py` — `JWTBearer` dependency
- `api/rest/stream_cdp.py` — Existing CDP start handler (pattern to follow)
- `api/websockets/stream_cdp.py` — Existing WebSocket handler
- `api/stealth/` — `apply_stealth()` usage
- Frontend: `src/components/content/admin_WebscrapeSupermarkets.tsx`
- Frontend: `src/components/minor/Websocket_CDP_Canvas.tsx`
- Frontend: `src/services/pgConnections.ts` — where `startChromiumDeveloperProtocolSession` is defined