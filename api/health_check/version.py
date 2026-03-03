import os
from fastapi import APIRouter

# Read the build version from the environment variable
# Provide a default value for local development
app_version = os.environ.get("APP_VERSION", "local-development")

#   ___       __  ___       __        __   __       ___  ___
#  |__   /\  /__`  |   /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |  /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()


@router.get("/version")
async def get_version():
  """Returns the application's build version."""
  return {"app_version": app_version}
