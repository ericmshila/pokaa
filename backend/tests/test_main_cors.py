"""
Unit tests for app.main's ALLOWED_ORIGINS parsing — see
_allowed_origins' docstring in main.py for why it defaults to wide
open ("*") for local/LAN play and becomes a real allow-list once
ALLOWED_ORIGINS is set on a real deployment (see docs/deploy.md).

Tests the parsing function directly rather than the FastAPI app's
actual CORS behavior at request time — the app only reads this once,
at import time, to build its middleware list, so exercising that via
a live app instance per test case would mean reloading the module
under different env vars rather than testing the (simple, pure)
parsing logic itself.
"""

import pytest

from app.main import _allowed_origins


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)


def test_defaults_to_wide_open_when_unset():
    assert _allowed_origins() == ["*"]


def test_explicit_wildcard_is_wide_open(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    assert _allowed_origins() == ["*"]


def test_empty_string_falls_back_to_wide_open(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    assert _allowed_origins() == ["*"]


def test_single_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://kadi-frontend.onrender.com")
    assert _allowed_origins() == ["https://kadi-frontend.onrender.com"]


def test_multiple_comma_separated_origins_are_trimmed(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        " https://a.example.com ,https://b.example.com,, ",
    )
    assert _allowed_origins() == [
        "https://a.example.com",
        "https://b.example.com",
    ]
