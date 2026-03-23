from datetime import datetime
from zoneinfo import ZoneInfo
from api.logger import logger
from api import anthropic
from api.scraping import (
  ScrapeResult,
  respond_with_error,
)


async def etl_aldi_prospekt(
  session_id: str,
) -> ScrapeResult:
  """Loads scraping output saved in tmpfs in memory for further parsing and sanitization
  Sanitizes alt text extracted from prospekt to clean superfluous information
  Upload json formatted alt text scrape output to LLM API Endpoint for later analysis
  Upload jpeg alt text scrape output to LLM API Endpoint for later analysis
  Query LLM API Endpoint with a message and attached file id references as context"""
  timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()

  # 9. Pass scraped alt text to Claude for data extraction
  # NOTE: The data is unstructured, full of artifacts and varies on a weekly basis
  # so programmatic extraction would require extensive RegExp and filtering and be unreliable
  try:
    await anthropic.launch_client()
    llm_response = await anthropic.send_single_message(
      """Hello Claude, can you output the two attached files referenced with their filenames
      and content formatted as json analyzing any diffs between them with a comment explaining the findings""",
      True,
      ["file_011CZ5WsCrDv3e9fj2TC3BCi", "file_011CZKfndwZ3jXxsNRatXgQa"],
    )
    logger.header(llm_response, level=2)
    upload_bytes: bytes = (
      b'{"products": ['
      b'  {"name": "Widget A", "price": 19.99, "currency": "EUR"},'
      b'  {"name": "Widget B", "price": 24.50, "currency": "EUR"}'
      b"]}"
    )
    upload_file_name = "testfile.json"
    file_upload_response = await anthropic.upload_raw_bytes_as_file(upload_file_name, upload_bytes)
    # Pydantic models do not have a .get method since they are not dictionaries, use getattr instead
    file_id = getattr(file_upload_response, "id", None)
    file_name = getattr(file_upload_response, "filename", None)
    if not file_id or not file_name or file_name != upload_file_name:
      return respond_with_error(
        session_id, "None", f"anthropic file_id {file_id} file_name {file_name} mismatch. Aborted."
      )
    logger.success(f"file {file_name} with id [{file_id}] uploaded successfully")
  except Exception as e:
    logger.error(f"Error querying LLM endpoint: {e}")
    raise
  finally:
    await anthropic.shutdown_client()
