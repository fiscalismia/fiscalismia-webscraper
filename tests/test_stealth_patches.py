"""Unit tests for stealth browser hardening."""

import asyncio
import inspect
from api.stealth.browser_args import get_stealth_browser_args
from api.stealth.js_patches import (
  PATCH_WEBDRIVER,
  PATCH_CHROME_RUNTIME,
  PATCH_PLUGINS,
  PATCH_PERMISSIONS,
  PATCH_WEBGL_VENDOR,
  PATCH_SCREEN_XY,
  STEALTH_SCRIPTS,
  ALL_PATCHES,
)
from api.stealth import apply_stealth


class TestBrowserArgs:
  def test_returns_list(self):
    args = get_stealth_browser_args()
    assert isinstance(args, list)

  def test_contains_automation_controlled(self):
    args = get_stealth_browser_args()
    assert "--disable-blink-features=AutomationControlled" in args

  def test_contains_window_size(self):
    args = get_stealth_browser_args()
    assert "--window-size=1680,1050" in args

  def test_all_strings(self):
    args = get_stealth_browser_args()
    for arg in args:
      assert isinstance(arg, str)
      assert arg.startswith("--")


class TestJsPatches:
  def test_patches_non_empty(self):
    for patch in STEALTH_SCRIPTS:
      assert isinstance(patch, str)
      assert len(patch.strip()) > 0

  def test_webdriver_patch_content(self):
    assert "navigator" in PATCH_WEBDRIVER
    assert "webdriver" in PATCH_WEBDRIVER

  def test_chrome_runtime_patch_content(self):
    assert "chrome" in PATCH_CHROME_RUNTIME
    assert "runtime" in PATCH_CHROME_RUNTIME
    assert "connect" in PATCH_CHROME_RUNTIME

  def test_plugins_patch_content(self):
    assert "plugins" in PATCH_PLUGINS
    assert "Chrome PDF" in PATCH_PLUGINS

  def test_permissions_patch_content(self):
    assert "permissions" in PATCH_PERMISSIONS
    assert "notifications" in PATCH_PERMISSIONS

  def test_webgl_patch_content(self):
    assert "getParameter" in PATCH_WEBGL_VENDOR
    assert "37445" in PATCH_WEBGL_VENDOR
    assert "37446" in PATCH_WEBGL_VENDOR

  def test_all_patches_combines_all(self):
    for patch in STEALTH_SCRIPTS:
      assert patch.strip() in ALL_PATCHES

  def test_stealth_scripts_count(self):
    assert len(STEALTH_SCRIPTS) == 6


class TestApplyStealth:
  def test_is_coroutine_function(self):
    assert inspect.iscoroutinefunction(apply_stealth)
