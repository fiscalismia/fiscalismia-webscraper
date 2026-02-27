import app.config
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from app.health_check.hc import router as health_check_router
from app.health_check.version import router as version_router
from app.security import JWTBearer
from app.stream.test_cdp_websocket import router as test_cdp_websocket_router
from app.stream.test_cdp_websocket import ws_router as test_cdp_ws_router
from app.logging.logger import set_global_log_level as log_level
from app import browser

app_version = os.environ.get("APP_VERSION", "local-development")

decoding_secret = os.environ.get("JWT_SECRET", None)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Playwright browser lifecycle: launch on startup, close on shutdown."""
    await browser.startup()
    yield
    await browser.shutdown()

# Create FastAPI app instance
api = FastAPI(title = "Fiscalismia Webscraper FastAPI",
              version = app_version,
              timeout = app.config.FASTAPI_GLOBAL_TIMEOUT_SECONDS,
              lifespan = lifespan )

# unprotected route for health checks at root path, hit from e.g. AWS resources
api.include_router(health_check_router)
api.include_router(version_router)

#   __   __   __  ___  ___  __  ___  ___  __      __   __       ___  ___  __
#  |__) |__) /  \  |  |__  /  `  |  |__  |  \    |__) /  \ |  |  |  |__  /__`
#  |    |  \ \__/  |  |___ \__,  |  |___ |__/    |  \ \__/ \__/  |  |___ .__/
# see https://testdriven.io/blog/fastapi-jwt-auth/
api.include_router(test_cdp_websocket_router, dependencies=[Depends(JWTBearer())], prefix = app.config.FASTAPI_STREAM_ENDPOINT)
# WebSocket router: JWT validated via query param inside the handler (HTTPBearer doesn't support WebSocket)
api.include_router(test_cdp_ws_router, prefix = app.config.FASTAPI_STREAM_ENDPOINT)

# Set Log Level for Backend Logs (replacing print statements to stdout)
log_level(logging.DEBUG)