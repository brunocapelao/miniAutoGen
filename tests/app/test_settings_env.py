"""Tests for MiniAutoGenSettings.env field."""

from __future__ import annotations

import os

import pytest

from miniautogen.app.settings import MiniAutoGenSettings


def test_env_defaults_to_development():
    """When ENV is not set, env should default to 'development'."""
    settings = MiniAutoGenSettings(
        DATABASE_URL="sqlite+aiosqlite:///test.db",
    )
    assert settings.env == "development"


def test_env_reads_from_env_var(monkeypatch):
    """When ENV is set, settings.env should reflect it."""
    monkeypatch.setenv("ENV", "production")
    settings = MiniAutoGenSettings(
        DATABASE_URL="sqlite+aiosqlite:///test.db",
    )
    assert settings.env == "production"
