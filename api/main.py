import api.config
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from api.health_check.root_info import router as root_info_router
from api.health_check.hc import router as health_check_router
from api.health_check.version import router as version_router
from api.security import JWTBearer
from api.stream.test_cdp_websocket import router as test_cdp_rest_router
from api.stream.test_cdp_websocket import ws_router as test_cdp_websocket_router
from api.logging.logger import set_global_log_level as log_level
from api import browser

app_version = os.environ.get("APP_VERSION", "local-development")
decoding_secret = os.environ.get("JWT_SECRET", None)


@asynccontextmanager
async def lifespan(app: FastAPI):
  """Manage Playwright browser lifecycle: launch on startup, close on shutdown."""
  await browser.startup()
  yield
  await browser.shutdown()


# Create FastAPI app instance
fastapi = FastAPI(
  title="Fiscalismia Webscraper FastAPI",
  version=app_version,
  timeout=api.config.FASTAPI_GLOBAL_TIMEOUT_SECONDS,
  lifespan=lifespan,
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
  test_cdp_rest_router,
  dependencies=[Depends(JWTBearer())],
  prefix=f"{api.config.BASE_ROUTE}{api.config.STREAM_ENDPOINT}",
)
# WebSocket router: JWT validated via query param inside the handler (HTTPBearer doesn't support WebSocket)
fastapi.include_router(test_cdp_websocket_router, prefix=f"{api.config.BASE_ROUTE}{api.config.STREAM_ENDPOINT}")

# Set Log Level for Backend Logs (replacing print statements to stdout)
log_level(logging.DEBUG)
