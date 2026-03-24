import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from api.logger import logger
from api import anthropic
from typing import Callable
from api.scraping import (
  ScrapeResult,
  respond_with_error,
  NON_FOOD_KEYWORDS,
  ALDI_FOOD_KEYWORDS,
  ALDI_HUB_PAGES,
  ALDI_TRAVEL_MARKERS,
  ALDI_AWARDS_KEYWORDS,
  ALDI_TALK_KEYWORDS,
  normalize_alt_text,
)


async def etl_aldi_prospekt(session_id: str, filepath: str, query_llm: bool = False) -> ScrapeResult:
  """Loads scraping output saved in tmpfs in memory for further parsing and sanitization
  Sanitizes alt text extracted from prospekt to clean superfluous information
  Upload json formatted alt text scrape output to LLM API Endpoint for later analysis
  Upload jpeg alt text scrape output to LLM API Endpoint for later analysis
  Query LLM API Endpoint with a message and attached file id references as context"""

  #                      __       ___    __
  #    \  /  /\  |    | |  \  /\   |  | /  \ |\ |
  #     \/  /~~\ |___ | |__/ /~~\  |  | \__/ | \|
  timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()
  # with open(filepath, "r") as f:
  with open("/tmp/scrape_test/aldi_prospekt_13919dd8-f468-4ceb-bfce-0a9ee1ca9cf0.json", "r") as f:  # TODO remove
    input = json.load(f)
  if ("status" in input.keys() and input["status"] == "success") and (
    "data" in input.keys() and "prospekt_images_src_alt_dict" in input["data"]
  ):
    logger.debug(f"JSON in path {filepath} contains expected keys")
  else:
    raise ValueError(f"ValueError: JSON key validation failed for {filepath}")

  try:
    input_img_dict: dict = input["data"]["prospekt_images_src_alt_dict"]
    output_img_dict: dict = input_img_dict

    #     __  ___      ___    __  ___    __   __
    #    /__`  |   /\   |  | /__`  |  | /  ` /__`    | |\ |
    #    .__/  |  /~~\  |  | .__/  |  | \__, .__/    | | \|
    input_img_cnt: int = len(list(input_img_dict.keys()))
    input_alt_text_bytes: int = sum(len(v) for v in input_img_dict.values())
  except KeyError as e:
    raise ValueError(f"Missing expected key in JSON structure: {e}") from e
  except TypeError as e:
    raise ValueError(f"Unexpected data type in JSON structure: {e}") from e

  #     __        __   ___     ___        ___  ___  __   __
  #    |__)  /\  / _` |__     |__  | |     |  |__  |__) /__`
  #    |    /~~\ \__> |___    |    | |___  |  |___ |  \ .__/
  # 1. FILTER OUT NON-FOOD PAGES ENTIRELY

  # 2. FILTER OUT ALDI-TRAVEL PAGES ENTIRELY

  # 3. FILTER OUT ALDI-TALK PAGES ENTIRELY

  # 4. FILTER OUT ALDI-AWARDS PAGES ENTIRELY

  #                 ___     ___        ___  ___  __   __
  #    |    | |\ | |__     |__  | |     |  |__  |__) /__`
  #    |___ | | \| |___    |    | |___  |  |___ |  \ .__/
  # 5. APPLY LINE FILTERS

  # legal_boilerplate any(p in line for p in patterns) "Aktionsartikel im Unterschied","begrenzter Anzahl zur Verfügung", "Aktionsbeginn ausverkauft", "Alle Artikel ohne Dekoration", "Artikel teilweise mit Serviervorschlägen", "Preis gültig im Aktionszeitraum",
  # haltungsform "Haltungsform" in line and ("Umstellungsphase" in line or "Kennzeichnung" in line)
  # aldi_address "ALDI SÜD Dienstleistungs" in line or "Burgstraße 37" in line or "Burgstr. 37" in line
  # ki_artifacts "Hintergrund KI-generiert", "KI-generiert"
  # trademark any(ind in line for ind in indicators) "©", "Licensed by", "Licensed through", "trademarks", "™ designate"
  # kundenmonitor "ServiceBarometer", "Kundenmonitor", "NielsenIQ"

  # 6. NORMALIZE TEXT
  # normalize_alt_text

  #     __  ___      ___    __  ___    __   __      __       ___
  #    /__`  |   /\   |  | /__`  |  | /  ` /__`    /  \ |  |  |
  #    .__/  |  /~~\  |  | .__/  |  | \__, .__/    \__/ \__/  |

  output_img_cnt: int = len(list(output_img_dict.keys()))
  output_alt_text_bytes: int = sum(len(v) for v in output_img_dict.values())
  #                       ___  __             __   ___  __   __
  #    |    |     |\/|     |  |__)  /\  |\ | /__` |__  /  \ |__)  |\/|
  #    |___ |___  |  |     |  |  \ /~~\ | \| .__/ |    \__/ |  \  |  |
  # Pass scraped alt text to Claude for data extraction
  # NOTE: The data is unstructured, full of artifacts and varies on a weekly basis
  # so programmatic extraction would require extensive RegExp and filtering and be unreliable
  if query_llm:
    try:
      await anthropic.launch_client()
      upload_bytes: bytes = (
        b'{"products": ['
        b'  {"name": "Widget B", "price": 19.99, "currency": "EUR"},'
        b'  {"name": "Widget A", "price": 24.50, "currency": "EUR"}'
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

      await asyncio.sleep(2)

      llm_response = await anthropic.send_single_message(
        message="""Hello Claude, can you output the two attached files referenced with their filenames
        and content formatted as json analyzing any diffs between them with a comment explaining the findings""",
        file_beta_tag=True,
        file_ids=[file_id, "file_011CZKfndwZ3jXxsNRatXgQa"],
      )
      logger.header(llm_response, level=2)
    except Exception as e:
      logger.error(f"Error querying LLM endpoint: {e}")
      raise
    finally:
      await anthropic.shutdown_client()

  # RETURN SANITIZED DATA AND ETL STATISTICS
  return ScrapeResult(
    status="transformed",
    session_id=session_id,
    target_url=input["target_url"],
    prospekt_url=input["prospekt_url"],
    timestamp=timestamp,
    data={
      "etl_statistics": {
        "input_img_cnt": input_img_cnt,
        "input_alt_text_bytes": input_alt_text_bytes,
        "output_img_cnt": output_img_cnt,
        "output_alt_text_bytes": output_alt_text_bytes,
      },
      "prospekt_images_src_alt_dict": output_img_dict,
      "optional_pdf_filepath": input["data"]["optional_pdf_filepath"],
    },
  )
