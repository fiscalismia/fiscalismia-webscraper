from fastapi import APIRouter
import api.config

#   ___       __  ___       __        __   __       ___  ___
#  |__   /\  /__`  |   /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |  /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()


@router.get("/")
async def root_info():
  """Responds with status 200 to GET requests and a message to instead query the /hc routes"""
  return {
    "info": "This is a Python FastAPI",
    "endpoint": f"{api.config.BASE_ROUTE}",
    "health": f"{api.config.BASE_ROUTE}/hc",
    "version": f"{api.config.BASE_ROUTE}/version",
  }
