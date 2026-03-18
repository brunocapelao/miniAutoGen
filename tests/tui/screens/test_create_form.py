"""Tests for CreateFormScreen."""

from __future__ import annotations

from textual.screen import ModalScreen

from miniautogen.tui.screens.create_form import (
    CreateFormScreen,
    _AGENT_FIELDS,
    _ENGINE_FIELDS,
    _PIPELINE_FIELDS,
)


def test_form_is_modal_screen() -> None:
    assert issubclass(CreateFormScreen, ModalScreen)


def test_form_stores_resource_type() -> None:
    form = CreateFormScreen(resource_type="engine")
    assert form._resource_type == "engine"
    assert form._edit_name is None


def test_form_edit_mode() -> None:
    form = CreateFormScreen(resource_type="agent", edit_name="researcher")
    assert form._resource_type == "agent"
    assert form._edit_name == "researcher"


def test_engine_fields_defined() -> None:
    names = [f["name"] for f in _ENGINE_FIELDS]
    assert "name" in names
    assert "provider" in names
    assert "model" in names
    assert "kind" in names


def test_agent_fields_defined() -> None:
    names = [f["name"] for f in _AGENT_FIELDS]
    assert "name" in names
    assert "role" in names
    assert "goal" in names
    assert "engine_profile" in names


def test_pipeline_fields_defined() -> None:
    names = [f["name"] for f in _PIPELINE_FIELDS]
    assert "name" in names
    assert "mode" in names
