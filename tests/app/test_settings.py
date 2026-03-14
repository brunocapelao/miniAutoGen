import pytest

from miniautogen.app.settings import MiniAutoGenSettings


def test_settings_reads_required_database_url_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///prod.db")

    settings = MiniAutoGenSettings()

    assert settings.database_url == "sqlite+aiosqlite:///prod.db"
    assert settings.default_provider == "litellm"
    assert settings.default_model == "gpt-4o-mini"
    assert settings.default_timeout_seconds == 30.0
    assert settings.default_retry_attempts == 1


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(Exception):
        MiniAutoGenSettings()
