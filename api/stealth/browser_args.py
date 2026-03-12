def get_stealth_browser_args() -> list[str]:
  """Chrome launch flags to reduce automation detection signals."""
  return [
    "--disable-blink-features=AutomationControlled",
    "--window-size=1600,900",
    "--no-default-browser-check",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-features=AutofillServerCommunication,CertificateTransparencyComponentUpdater",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--metrics-recording-only",
    "--no-service-autorun",
    "--password-store=basic",
    "--use-mock-keychain",
    "--export-tagged-pdf",
    "--disable-search-engine-choice-screen",
    "--unsafely-treat-insecure-origin-as-secure=http://localhost",
  ]
