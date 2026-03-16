from miniautogen.app.provider_factory import build_provider
from miniautogen.app.settings import MiniAutoGenSettings


def test_build_provider_returns_gateway_provider_when_selected() -> None:
    settings = MiniAutoGenSettings.model_construct(
        database_url="sqlite+aiosqlite:///tmp.db",
        default_provider="gemini-cli-gateway",
        default_model="gemini-2.5-pro",
        default_timeout_seconds=30.0,
        default_retry_attempts=1,
        gateway_base_url="http://gateway.local",
        gateway_api_key=None,
    )
    provider = build_provider(settings)
    assert provider.__class__.__name__ == "OpenAICompatibleProvider"


def test_build_provider_requires_gateway_url_for_gateway_provider() -> None:
    settings = MiniAutoGenSettings.model_construct(
        database_url="sqlite+aiosqlite:///tmp.db",
        default_provider="gemini-cli-gateway",
        default_model="gemini-2.5-pro",
        default_timeout_seconds=30.0,
        default_retry_attempts=1,
        gateway_base_url=None,
        gateway_api_key=None,
    )
    try:
        build_provider(settings)
    except ValueError:
        return
    raise AssertionError("Expected ValueError when gateway_base_url is missing")
