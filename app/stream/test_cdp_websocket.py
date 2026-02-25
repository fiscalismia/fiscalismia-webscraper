
from fastapi import APIRouter
from app.logging.logger import logger
#   ___       __  ___       __        __   __       ___  ___
#  |__   /\  /__`  |   /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |  /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()

@router.post("/test_cdp_websocket")
async def health_check():
    """todo
    """
    return {
        "stream": "available",
    }