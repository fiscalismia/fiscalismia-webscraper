from api.stealth.js_patches import ALL_PATCHES
from api.logger import logger


def _strip_source_urls(script: str) -> str:
  """Remove sourceURL comments that reveal script injection."""
  return "\n".join(
    line for line in script.splitlines()
    if not line.strip().startswith("//# sourceURL=")
  )


async def apply_cdp_patches(cdp_session) -> None:
  """Inject stealth JS via Page.addScriptToEvaluateOnNewDocument.
  This persists across navigations and runs before any page JS."""
  clean_script = _strip_source_urls(ALL_PATCHES)
  await cdp_session.send(
    "Page.addScriptToEvaluateOnNewDocument",
    {"source": clean_script},
  )
  logger.debug("Applied CDP stealth patches via Page.addScriptToEvaluateOnNewDocument")
