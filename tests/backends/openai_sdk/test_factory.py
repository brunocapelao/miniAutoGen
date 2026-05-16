"""Tests for OpenAI SDK factory."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.errors import BackendConfigurationError
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver
from miniautogen.backends.openai_sdk.factory import openai_sdk_factory

_LOCAL_SENTINEL = "sk-noauth-local"


class TestOpenAISDKFactory:
    @patch("openai.AsyncOpenAI")
    @patch.dict(os.environ, {"TEST_KEY": "sk-test-dummy"})
    def test_creates_driver(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="openai-test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="TEST_KEY"),
            metadata={"model": "gpt-4o"},
        )
        driver = openai_sdk_factory(config)
        assert isinstance(driver, OpenAISDKDriver)

    @patch("openai.AsyncOpenAI")
    @patch.dict(os.environ, {"TEST_KEY": "sk-test-dummy"})
    def test_passes_model_from_metadata(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="TEST_KEY"),
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
    @patch.dict(os.environ, {"TEST_KEY": "sk-test-dummy"})
    def test_passes_endpoint_as_base_url(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="TEST_KEY"),
            endpoint="https://custom-endpoint.com/v1",
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://custom-endpoint.com/v1"

    # ── Decision table: endpoint × api_key × host ────────────────────────

    @patch("openai.AsyncOpenAI")
    def test_default_endpoint_no_key_raises(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            metadata={"model": "gpt-4o"},
        )
        with pytest.raises(BackendConfigurationError):
            openai_sdk_factory(config)

    @patch("openai.AsyncOpenAI")
    @patch.dict(os.environ, {"MY_KEY": "sk-test-123"})
    def test_default_endpoint_with_key_ok(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="MY_KEY"),
            metadata={"model": "gpt-4o"},
        )
        driver = openai_sdk_factory(config)
        assert isinstance(driver, OpenAISDKDriver)

    @patch("openai.AsyncOpenAI")
    def test_openai_host_no_key_raises(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            endpoint="https://api.openai.com/v1",
            metadata={"model": "gpt-4o"},
        )
        with pytest.raises(BackendConfigurationError):
            openai_sdk_factory(config)

    @patch("openai.AsyncOpenAI")
    def test_openai_subdomain_no_key_raises(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            endpoint="https://eu.api.openai.com/v1",
            metadata={"model": "gpt-4o"},
        )
        with pytest.raises(BackendConfigurationError):
            openai_sdk_factory(config)

    @patch("openai.AsyncOpenAI")
    def test_local_endpoint_no_key_injects_sentinel(
        self, mock_openai_cls: MagicMock
    ) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            endpoint="http://localhost:11434/v1",
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["api_key"] == _LOCAL_SENTINEL

    @patch("openai.AsyncOpenAI")
    @patch.dict(os.environ, {"MY_KEY": "sk-test-456"})
    def test_local_endpoint_with_key_uses_key(
        self, mock_openai_cls: MagicMock
    ) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="MY_KEY"),
            endpoint="http://localhost:11434/v1",
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-test-456"

    @patch("openai.AsyncOpenAI")
    def test_custom_endpoint_no_key_injects_sentinel(
        self, mock_openai_cls: MagicMock
    ) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            endpoint="https://gateway.internal/v1",
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["api_key"] == _LOCAL_SENTINEL
