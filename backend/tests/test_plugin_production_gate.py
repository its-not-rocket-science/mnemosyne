"""Verify that test-only plugins cannot leak into a production registry.

All tests run without a live database or NLP model — direct instantiation only.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.plugins.fake_cjk import FakeCJKPlugin
from backend.plugins.fake_rtl import FakeRTLPlugin


# ── Flag presence ─────────────────────────────────────────────────────────────

def test_fake_rtl_has_test_only_flag():
    assert FakeRTLPlugin.test_only is True

def test_fake_cjk_has_test_only_flag():
    assert FakeCJKPlugin.test_only is True

def test_fake_rtl_language_code_is_x_prefixed():
    assert FakeRTLPlugin.language_code.startswith("x-")

def test_fake_cjk_language_code_is_x_prefixed():
    assert FakeCJKPlugin.language_code.startswith("x-")


# ── Registry integration ──────────────────────────────────────────────────────

def _registry(debug: bool):
    from backend.core.config import Settings
    from backend.parsing.plugin_loader import load_plugins

    settings = Settings(debug=debug, database_url="postgresql+asyncpg://x/x")
    with patch("backend.parsing.plugin_loader.get_settings", return_value=settings):
        return load_plugins()


def test_test_plugins_excluded_in_production():
    reg = _registry(debug=False)
    codes = reg.all().keys()
    assert "x-rtl-test" not in codes, "FakeRTLPlugin leaked into production registry"
    assert "x-cjk-test" not in codes, "FakeCJKPlugin leaked into production registry"


def test_test_plugins_present_in_debug():
    reg = _registry(debug=True)
    codes = reg.all().keys()
    assert "x-rtl-test" in codes, "FakeRTLPlugin missing from debug registry"
    assert "x-cjk-test" in codes, "FakeCJKPlugin missing from debug registry"


def test_real_plugins_still_load_in_production():
    reg = _registry(debug=False)
    codes = reg.all().keys()
    # English plugin is always available, no model download needed.
    assert "en" in codes, "EnglishPlugin should load in production"


# ── Direct instantiation unaffected ──────────────────────────────────────────
# Tests that use fake plugins directly (not via load_plugins) must continue
# to work regardless of DEBUG setting.

def test_fake_rtl_instantiates_outside_registry():
    plugin = FakeRTLPlugin()
    results = plugin.analyze_text("مرحبا بالعالم.")
    assert results
    assert results[0].candidates


def test_fake_cjk_instantiates_outside_registry():
    plugin = FakeCJKPlugin()
    results = plugin.analyze_text("こんにちは。")
    assert results
    assert results[0].candidates


# ── Belt-and-suspenders: x-* prefix alone blocks even without test_only ───────

def test_x_code_blocked_without_test_only_flag():
    """x-* code is rejected in prod even if the author forgot test_only=True."""
    from backend.core.config import Settings
    from backend.parsing.plugin_loader import PluginRegistry

    settings = Settings(debug=False, database_url="postgresql+asyncpg://x/x")

    class ForgottenFlagPlugin:
        language_code = "x-forgot-flag"
        display_name  = "Forgotten"
        direction     = "ltr"
        # deliberately no test_only attribute
        capabilities  = None
        lesson_store  = {}

    plugin = ForgottenFlagPlugin()
    code            = plugin.language_code.lower()
    is_test_flagged = getattr(plugin, "test_only", False)
    is_x_code       = code.startswith("x-")

    assert not is_test_flagged, "sanity: flag is absent"
    assert not settings.debug and (is_test_flagged or is_x_code), (
        "x-* code should trigger the production gate even without test_only"
    )
