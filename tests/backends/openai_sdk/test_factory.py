"""Tests for OpenAI SDK factory."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver
from miniautogen.backends.openai_sdk.factory import openai_sdk_factory


class TestOpenAISDKFactory:
    @patch("openai.AsyncOpenAI")
    def test_creates_driver(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="openai-test",
            driver=DriverType.OPENAI_SDK,
            metadata={"model": "gpt-4o"},
        )
        driver = openai_sdk_factory(config)
        assert isinstance(driver, OpenAISDKDriver)

    @patch("openai.AsyncOpenAI")
    def test_passes_model_from_metadata(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            metadata={"model": "gpt-4o-mini"},
        )
        driver = openai_sdk_factory(config)
        assert driver._model == "gpt-4o-mini"

    @patch("openai.AsyncOpenAI")
    @patch.dict(os.environ, {"MY_KEY": "sk-test-123"})
    def test_resolves_api_key_from_auth(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="MY_KEY"),
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-test-123"

    @patch("openai.AsyncOpenAI")
    def test_passes_endpoint_as_base_url(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            endpoint="https://custom-endpoint.com/v1",
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://custom-endpoint.com/v1"
