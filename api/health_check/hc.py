from fastapi import APIRouter
from datetime import datetime
from zoneinfo import ZoneInfo
import math
import socket
import os
from api.logging.logger import logger

#   ___       __  ___       __        __   __       ___  ___
#  |__   /\  /__`  |   /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |  /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()

APP_START_TIME = datetime.now(tz=ZoneInfo("Europe/Berlin"))

app_version = os.environ.get("APP_VERSION", "local-development")

@router.get("/hc")
async def health_check():
    """Responds with status 200 to GET requests.
    Also outputs human readable information.
    """
    uptime = datetime.now(tz=ZoneInfo("Europe/Berlin")) - APP_START_TIME
    uptime_seconds = math.floor(uptime.total_seconds())
    uptime_hours = round(uptime.total_seconds()/3600,2)
    return {
        "status": "healthy",
        "app_version": app_version,
        "service": "fiscalismia-webscraper",
        "purpose" : "Unix Backend REST API for Live Webscraping",
        "timestamp": datetime.now(tz=ZoneInfo("Europe/Berlin")),
        "hostname" : socket.gethostname(),
        "uptime_hours" : uptime_hours,
        "uptime_seconds" : uptime_seconds,
    }
@router.get("/")
async def root_info():
    """Responds with status 200 to GET requests and a message to instead query the /hc route
    """
    return {
        "message": "Hit /hc route instead for a proper health check.",
    }