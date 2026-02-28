import jwt
import os
import traceback
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api.logging.logger import logger


#            ___    ___  __        ___       __
#     | |  |  |      |  /  \ |__/ |__  |\ | /__`
#  \__/ |/\|  |      |  \__/ |  \ |___ | \| .__/
def decode_jwt(token: str) -> dict:
  """Decode and validate a JWT token.

  Attempts to decode a JWT token using the configured secret key and HS256 algorithm.
  Returns a dictionary containing the HTTP status, decoded payload, and any error messages.

  Args:
      token (str): The JWT token string to decode

  Returns:
      dict: Dictionary containing:
          - http_status (int): HTTP status code (200 for success, 401/403/500 for errors)
          - payload (dict|None): Decoded JWT payload if successful, None if failed
          - error_message (str|None): Error message if decoding failed, None if successful
  """
  try:
    decoding_secret = os.environ.get("JWT_SECRET", None)
    decoded_dict = {
      "http_status": status.HTTP_200_OK,
      "payload": jwt.decode(token, decoding_secret, algorithms=["HS256"], options={"verify_signature": True}),
      "error_message": None,
    }
    return decoded_dict
  except HTTPException:
    # allow e.g. the Not Found exceptions to bubble up
    raise
  except jwt.ExpiredSignatureError as e:
    logger.error(f"=== JWT DECODE FAILED ===\nExpiredSignatureError: {str(e)}\nToken that failed: {token}")
    return {"http_status": status.HTTP_401_UNAUTHORIZED, "payload": None, "error_message": str(e)}
  except jwt.InvalidSignatureError as e:
    logger.error(f"=== JWT DECODE FAILED ===\nInvalidSignatureError: {str(e)}\nToken that failed: {token}")
    return {"http_status": status.HTTP_403_FORBIDDEN, "payload": None, "error_message": str(e)}
  except Exception as e:
    logger.error(
      f"=== JWT DECODE FAILED ===\n"
      f"Error type: {type(e).__name__}\n"
      f"Error message: {str(e)}\n"
      f"Token that failed: {token}\n"
      f"{traceback.print_exc()}"
    )
    return {"http_status": status.HTTP_500_INTERNAL_SERVER_ERROR, "payload": None, "error_message": str(e)}


class JWTBearer(HTTPBearer):
  def __init__(self, auto_error: bool = True):
    super(JWTBearer, self).__init__(auto_error=auto_error)

  async def __call__(self, request: Request):
    """Handle incoming requests and validate JWT tokens.

    Extracts the Bearer token from the Authorization header, validates it,
    and raises appropriate HTTP exceptions if validation fails.

    Args:
        request (Request): The incoming FastAPI request object

    Returns:
        str: The validated JWT token string if authentication succeeds

    Raises:
        HTTPException:
            - 403 if Bearer scheme is missing or invalid
            - 401/403/500 if JWT validation fails (based on decode_jwt response)
    """
    credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
    if credentials:
      if not credentials.scheme == "Bearer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bearer authentication header missing.")
      # decode and verify jwt with signature and expiration time
      verification_status = self.verify_jwt(credentials.credentials)
      if not verification_status["http_status"] == status.HTTP_200_OK:
        raise HTTPException(status_code=verification_status["http_status"], detail=verification_status["error_message"])
      if not verification_status["payload"]:
        raise HTTPException(
          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="JWT Payload could not be extracted."
        )
      return credentials.credentials
    else:
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authorization code.")

  def verify_jwt(self, jwtoken: str) -> bool:
    """Internal helper function with Exception Fallback. See decode_jwt for verification logic"""
    try:
      decoded_dict = decode_jwt(jwtoken)
      payload = decoded_dict["payload"]
      http_status = decoded_dict["http_status"]
      error_message = decoded_dict["error_message"]
    except Exception as e:
      logger.error(f"=== JWT VERIFY FAILED ===\nError type: {type(e).__name__}\nError message:  {str(e)}")
      return {"http_status": status.HTTP_400_BAD_REQUEST, "payload": None, "error_message": str(e)}
    return {"http_status": http_status, "payload": payload, "error_message": error_message}
