"""Tests for LLM adapter deprecation warnings."""

from __future__ import annotations

import sys
import warnings
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock litellm to avoid import issues with pkg_resources."""
    mock_litellm = MagicMock()
    monkeypatch.setitem(sys.modules, "litellm", mock_litellm)


class TestDeprecationWarnings:
    def test_openai_provider_init_warns(self) -> None:
        from miniautogen.adapters.llm.providers import OpenAIProvider

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OpenAIProvider(client=MagicMock())
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "OpenAISDKDriver" in str(dep_warnings[0].message)

    def test_litellm_provider_init_warns(self) -> None:
        from miniautogen.adapters.llm.providers import LiteLLMProvider

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            LiteLLMProvider(client=MagicMock())
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "LiteLLMDriver" in str(dep_warnings[0].message)

    def test_openai_compatible_provider_init_warns(self) -> None:
        from miniautogen.adapters.llm.openai_compatible_provider import (
            OpenAICompatibleProvider,
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OpenAICompatibleProvider(
                base_url="http://localhost:8000",
                client=MagicMock(),
            )
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "AgentAPIDriver" in str(dep_warnings[0].message)
