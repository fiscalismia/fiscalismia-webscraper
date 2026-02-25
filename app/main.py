import app.config
import logging
import os
from fastapi import FastAPI, Depends
from app.auth.request_session_token import router as auth_request_session_token_router
from app.health_check.hc import router as health_check_router
from app.health_check.version import router as version_router
from app.security import JWTBearer
from app.stream.test_cdp_websocket import router as test_cdp_websocket_router
from app.logging.logger import set_global_log_level as log_level
app_version = os.environ.get("APP_VERSION", "local-development")

# Create FastAPI app instance
api = FastAPI(title = "Fiscalismia Webscraper FastAPI",
              version = app_version,
              timeout = app.config.FASTAPI_GLOBAL_TIMEOUT_SECONDS )

# unprotected route for health checks at root path, hit from e.g. AWS resources
api.include_router(health_check_router)
api.include_router(version_router)

# unprotected route used for initial authentication - responds with jwt session token
api.include_router(auth_request_session_token_router, prefix = app.config.FASTAPI_AUTH_ENDPOINT)

#   __   __   __  ___  ___  __  ___  ___  __      __   __       ___  ___  __
#  |__) |__) /  \  |  |__  /  `  |  |__  |  \    |__) /  \ |  |  |  |__  /__`
#  |    |  \ \__/  |  |___ \__,  |  |___ |__/    |  \ \__/ \__/  |  |___ .__/
# see https://testdriven.io/blog/fastapi-jwt-auth/
api.include_router(test_cdp_websocket_router, dependencies=[Depends(JWTBearer())], prefix = app.config.FASTAPI_STREAM_ENDPOINT)

# Set Log Level for Backend Logs (replacing print statements to stdout)
log_level(logging.DEBUG)