import api.config
import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from api.health_check.root_info import router as root_info_router
from api.health_check.hc import router as health_check_router
from api.health_check.version import router as version_router
from api.security import JWTBearer
from api.rest.start_cdp import router as start_cdp_rest_router
from api.rest.scrape_supermarkets import router as scrape_supermarkets_router
from api.websockets.stream_cdp import router as stream_cdp_websocket_router
from api.logger import set_global_log_level as log_level
from api.config import SCRAPE_RESULTS_DIR, SCRAPE_RESULTS_TTL_SECONDS
from api.logger import logger
from api import browser
from dotenv import load_dotenv
from pathlib import Path

_secrets_path = Path("/run/secrets/.env")
if _secrets_path.is_file():
  load_dotenv(_secrets_path)
  logger.debug("env file successfully loaded from volume mount.")
else:
  logger.critical(".env file could not be loaded from volume mount.")

app_version = os.environ.get("APP_VERSION", "local-development")
decoding_secret = os.environ.get("JWT_SECRET", None)
IS_PRODUCTION = False


def cleanup_scrape_results(max_age_seconds: int = SCRAPE_RESULTS_TTL_SECONDS):
  """Remove stale scrape result files. Pass max_age_seconds=0 to remove all."""
  if not os.path.isdir(SCRAPE_RESULTS_DIR):
    return
  now = time.time()
  for f in os.listdir(SCRAPE_RESULTS_DIR):
    filepath = os.path.join(SCRAPE_RESULTS_DIR, f)
    if os.path.isfile(filepath):
      if max_age_seconds == 0 or (now - os.path.getmtime(filepath)) > max_age_seconds:
        os.remove(filepath)


@asynccontextmanager
async def lifespan(app: FastAPI):
  """Manage Playwright browser lifecycle: launch on startup, close on shutdown.
  Yield marks application execution in the asynchronous lifecycle context, where code
  is run between initial startup and graceful shutdown via e.g. SIGTERM or SIGINT.
  SIGKILL would skip browser shutdown and cleanup, but since they live in container memory,
  this is a non issue."""
  os.makedirs(SCRAPE_RESULTS_DIR, exist_ok=True)
  await browser.startup()
  yield
  await browser.shutdown()
  cleanup_scrape_results(max_age_seconds=0)


# Create FastAPI app instance
fastapi = FastAPI(
  title="Fiscalismia Webscraper FastAPI",
  version=app_version,
  timeout=api.config.FASTAPI_GLOBAL_TIMEOUT_SECONDS,
  lifespan=lifespan,
  docs_url=None if IS_PRODUCTION else "/docs",
  redoc_url=None if IS_PRODUCTION else "/redoc",
  openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# CORS middleware allowing specific origins only
fastapi.add_middleware(
  CORSMiddleware,
  allow_origins=[
    "http://127.0.0.1:3001",  # local development
    "http://127.0.0.1:4173",  # local vite preview
    "https://fiscalismia.com",  # production frontend
    "https://demo.fiscalismia.com",  # demo frontend
  ],
  allow_methods=["GET", "POST", "OPTIONS"],
  allow_headers=["Content-Type", "Authorization", "Accept"],
)

# unprotected route for health checks at root path, hit from e.g. AWS resources
fastapi.include_router(root_info_router)
fastapi.include_router(health_check_router, prefix=f"{api.config.BASE_ROUTE}")
fastapi.include_router(version_router, prefix=f"{api.config.BASE_ROUTE}")

#   __   __   __  ___  ___  __  ___  ___  __      __   __       ___  ___  __
#  |__) |__) /  \  |  |__  /  `  |  |__  |  \    |__) /  \ |  |  |  |__  /__`
#  |    |  \ \__/  |  |___ \__,  |  |___ |__/    |  \ \__/ \__/  |  |___ .__/
# see https://testdriven.io/blog/fastapi-jwt-auth/
fastapi.include_router(
  start_cdp_rest_router,
  dependencies=[Depends(JWTBearer())],
  prefix=f"{api.config.BASE_ROUTE}{api.config.REST_ENDPOINT}",
)
fastapi.include_router(
  scrape_supermarkets_router,
  dependencies=[Depends(JWTBearer())],
  prefix=f"{api.config.BASE_ROUTE}{api.config.REST_ENDPOINT}",
)
# WebSocket router: JWT validated via query param inside the handler (HTTPBearer doesn't support WebSocket)
fastapi.include_router(stream_cdp_websocket_router, prefix=f"{api.config.BASE_ROUTE}{api.config.WEBSOCKET_ENDPOINT}")

# Set Log Level for Backend Logs (replacing print statements to stdout)
log_level(logging.DEBUG)
