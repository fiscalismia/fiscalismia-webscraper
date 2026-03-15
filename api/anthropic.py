import os
from anthropic import (
  AsyncAnthropic,
  DefaultAioHttpClient,
  APIConnectionError,
  RateLimitError,
  BadRequestError,
  UnprocessableEntityError,
  InternalServerError,
  APITimeoutError,
  AuthenticationError,
  PermissionDeniedError,
)
from api.config import ASNYC_MESSAGING_MODEL_DEFAULT
from api.logger import logger

# Global Client instantiated on-demand during workflows
_anthropic_client: AsyncAnthropic | None = None


async def launch_client() -> AsyncAnthropic:
  """Initialize the shared Claude client on demand during workflows."""
  global _anthropic_client
  _anthropic_client = AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
    http_client=DefaultAioHttpClient(),
  )


async def shutdown_client() -> None:
  """Release the aiohttp connection pool. Must be explicitly called during workflows finally block"""
  global _anthropic_client
  if _anthropic_client:
    await _anthropic_client.close()
    _anthropic_client = None


async def get_client() -> AsyncAnthropic:
  if not _anthropic_client:
    raise RuntimeError(
      "No anthropic client instantiated. Call anthropic.launch_client() and ensure it is closed after use."
    )
  return _anthropic_client


async def send_single_message(content: str, file_beta_tag: bool = False, file_ids: list[str] = None):
  """Simple Synchronous Message Response received by sending structured prompts"""
  llm_client = await get_client()
  logger.debug(
    f"Anthropic send_single_message {f'FILE_BETA={file_ids}' if file_beta_tag else ''} request received with content length {len(content)}"
  )
  try:
    if file_beta_tag:
      if not file_ids:
        logger.error("Missing file_ids list[str] which are required.")
        raise ValueError("Missing file_ids list[str] which are required.")
      if isinstance(file_ids, str):
        logger.warning("file_ids received as str, wrapping in list")
        file_ids = [file_ids]
      # FILE ADDED METADATA TO ENRICH THE REQUEST CONTEXT
      message = await llm_client.beta.messages.create(
        max_tokens=1024,
        betas=["files-api-2025-04-14"],
        messages=[
          {
            "role": "user",
            "content": [
              {"type": "document", "source": {"type": "file", "file_id": file_ids[0]}},
              {"type": "text", "text": content},
            ],
          }
        ],
        model=ASNYC_MESSAGING_MODEL_DEFAULT,
      )
    else:
      # BASIC RESPONSE WITH ONLY TEXT CONTENT
      message = await llm_client.messages.create(
        max_tokens=1024,
        messages=[
          {
            "role": "user",
            "content": content,
          }
        ],
        model=ASNYC_MESSAGING_MODEL_DEFAULT,
      )
    logger.debug(
      f"Model {ASNYC_MESSAGING_MODEL_DEFAULT} message {message.id}: Tokens used [{message.usage.input_tokens + message.usage.output_tokens}] "
    )
    if len(message.content) > 1:
      logger.error("LLM Response length greater than expected")
      raise ValueError("LLM Response length greater than expected")
    elif message.content[0].type == "text":
      return message.content[0].text
    return message.content
  except AuthenticationError as e:
    logger.error(f"Anthropic auth failed (401): {e.message}")
    raise
  except PermissionDeniedError as e:
    logger.error(f"Anthropic permission denied (403): {e.message}")
    raise
  except RateLimitError as e:
    retry_after = e.response.headers.get("retry-after", "unknown")
    logger.warning(f"Anthropic rate limited (429). Retry after: {retry_after}s")
    raise
  except BadRequestError as e:
    logger.error(f"Anthropic bad request (400): {e.message}")
    raise
  except UnprocessableEntityError as e:
    logger.error(f"Anthropic unprocessable entity (422): {e.message}")
    raise
  except InternalServerError as e:
    logger.error(f"Anthropic server error ({e.status_code}): {e.message}")
    raise
  except APIConnectionError as e:
    logger.error(f"Anthropic connection failed: {e.__cause__}")
    raise
  except APITimeoutError as e:
    logger.error(f"Anthropic request timed out: {e}")
    raise


async def upload_raw_bytes_as_file(filename: str, file_bytes: bytes):
  """Uploads File for storage and processing in Claude's API Platform"""
  llm_client = await get_client()
  logger.debug(
    f"Anthropic upload_raw_bytes_as_file request received with filename {filename} and content length {len(file_bytes)}bytes"
  )
  try:
    upload_response = await llm_client.beta.files.upload(
      file=(filename, file_bytes, "text/plain"),
      betas=["files-api-2025-04-14"],
    )
    logger.debug(f"Anthropic file uploaded: {upload_response.id}")
    return upload_response
  except AuthenticationError as e:
    logger.error(f"Anthropic auth failed (401): {e.message}")
    raise
  except PermissionDeniedError as e:
    logger.error(f"Anthropic permission denied (403): {e.message}")
    raise
  except RateLimitError as e:
    retry_after = e.response.headers.get("retry-after", "unknown")
    logger.warning(f"Anthropic rate limited (429). Retry after: {retry_after}s")
    raise
  except BadRequestError as e:
    logger.error(f"Anthropic bad request (400): {e.message}")
    raise
  except UnprocessableEntityError as e:
    logger.error(f"Anthropic unprocessable entity (422): {e.message}")
    raise
  except InternalServerError as e:
    logger.error(f"Anthropic server error ({e.status_code}): {e.message}")
    raise
  except APIConnectionError as e:
    logger.error(f"Anthropic connection failed: {e.__cause__}")
    raise
  except APITimeoutError as e:
    logger.error(f"Anthropic request timed out: {e}")
    raise
