import jwt
import os
import app.config
from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.logging.logger import logger

def encode_jwt(username: str) -> str:
    """Create and encode a JWT session token for a user.
    Generates a JWT token containing user identification and session metadata.
    The token is signed with the configured secret key and expires after 1 hour.

    Args:
        username (str): The user's unique identifier/vkey to embed in the token

    Returns:
        str: Encoded JWT token string containing:
            - exp: Expiration timestamp (1 hour from creation)
            - iat: Issued at timestamp (current time)
            - type: Session token type from app configuration
            - user: The provided user vkey
    """
    now = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    expiration = now + timedelta(hours=app.config.SESSION_TOKEN_DURATION_HOURS)

    encoding_secret = os.environ.get("JWT_ENCODING_SECRET", None)

    payload = {
        "exp": expiration,
        "iat": datetime.now(tz=ZoneInfo("Europe/Berlin")),
        "type": app.config.SESSION_TOKEN_TYPE,
        "username": username
    }
    logger.debug(f"Returning JWT Session Token with duration {app.config.SESSION_TOKEN_DURATION_HOURS * 60} minutes for user {username}.", username=username)
    return jwt.encode(payload, encoding_secret, algorithm="HS256")

#   ___       __  ___          __        __   __       ___  ___
#  |__   /\  /__`  |      /\  |__) |    |__) /  \ |  |  |  |__
#  |    /~~\ .__/  |     /~~\ |    |    |  \ \__/ \__/  |  |___
router = APIRouter()

@router.get("/request_session_token/{username}")
async def request_session_token( username: str ):
    """
    Args:
        username: Requesting User's Generali ID
    Returns:
        JWT Token including the encoded payload
    """
    try:
        return {encode_jwt(username)}
    except HTTPException:
        # Re-raise HTTP exceptions from create_s3_read_access_jwt
        raise
    except Exception as e:
        logger.error(f'=== REQUEST_SESSION_TOKEN ===\n'
                    f'Error type: {type(e).__name__}\n'
                    f'Error message:  {str(e)}', username=username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{type(e).__name__}: Unexpected error requesting session token: {str(e)}"
        )
