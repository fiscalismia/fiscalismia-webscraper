from api.stealth.browser_args import get_stealth_browser_args
from api.stealth.cdp_patches import apply_cdp_patches
from api.stealth.js_patches import ALL_PATCHES
from api.logger import logger


async def apply_stealth(page, cdp_session) -> None:
  """Apply all stealth hardening to a page and CDP session."""
  # Playwright-level: add_init_script persists across navigations
  await page.add_init_script(ALL_PATCHES)
  logger.debug("Injected stealth init script via Playwright page.add_init_script")
  # CDP-level: Page.addScriptToEvaluateOnNewDocument for CDP session persistence
  await apply_cdp_patches(cdp_session)
