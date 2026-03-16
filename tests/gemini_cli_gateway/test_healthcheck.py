import pytest
from httpx import ASGITransport, AsyncClient

from gemini_cli_gateway.app import app


@pytest.mark.asyncio
async def test_healthcheck_returns_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
