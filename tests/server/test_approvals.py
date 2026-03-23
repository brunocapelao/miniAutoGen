"""Tests for approval endpoints."""

from __future__ import annotations


def test_list_approvals_empty(client):
    resp = client.get("/api/v1/runs/r1/approvals")
    assert resp.status_code == 200
    assert resp.json() == []


def test_resolve_approval_no_channel(client):
    resp = client.post(
        "/api/v1/runs/r1/approvals/req-1",
        json={"decision": "approved"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "run_not_found"


def test_resolve_approval_invalid_decision(client):
    resp = client.post(
        "/api/v1/runs/r1/approvals/req-1",
        json={"decision": "maybe"},
    )
    assert resp.status_code == 422  # Pydantic validation error
