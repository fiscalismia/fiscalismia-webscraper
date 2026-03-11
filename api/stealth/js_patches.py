from api.config import STEALTH_WEBGL_VENDOR, STEALTH_WEBGL_RENDERER

PATCH_WEBDRIVER = """
Object.defineProperty(navigator, 'webdriver', {
  get: () => undefined,
});
"""

PATCH_CHROME_RUNTIME = """
window.chrome = window.chrome || {};
window.chrome.runtime = {
  connect: function() { return { onMessage: { addListener: function() {} }, postMessage: function() {} }; },
  sendMessage: function(msg, cb) { if (cb) cb(); },
  onMessage: { addListener: function() {} },
  id: undefined,
};
"""

PATCH_PLUGINS = """
Object.defineProperty(navigator, 'plugins', {
  get: () => {
    const plugins = [
      { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
      { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
    ];
    plugins.refresh = function() {};
    return plugins;
  },
});
"""

PATCH_PERMISSIONS = """
const originalQuery = navigator.permissions.query;
navigator.permissions.query = function(parameters) {
  if (parameters.name === 'notifications') {
    return Promise.resolve({ state: Notification.permission === 'denied' ? 'denied' : 'prompt' });
  }
  return originalQuery.call(this, parameters);
};
"""

PATCH_WEBGL_VENDOR = f"""
const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {{
  if (parameter === 37445) return '{STEALTH_WEBGL_VENDOR}';
  if (parameter === 37446) return '{STEALTH_WEBGL_RENDERER}';
  return getParameterOrig.call(this, parameter);
}};
"""

PATCH_SCREEN_XY = """
if (window.self !== window.top) {
  Object.defineProperty(window, 'screenX', { get: () => window.top.screenX });
  Object.defineProperty(window, 'screenY', { get: () => window.top.screenY });
}
"""

STEALTH_SCRIPTS = [
  PATCH_WEBDRIVER,
  PATCH_CHROME_RUNTIME,
  PATCH_PLUGINS,
  PATCH_PERMISSIONS,
  PATCH_WEBGL_VENDOR,
  PATCH_SCREEN_XY,
]

ALL_PATCHES = "\n".join(STEALTH_SCRIPTS)
