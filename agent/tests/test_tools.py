"""
End-to-end integration tests for the agent API.
Requires the FastAPI server to be running (or uses TestClient).
"""
import sys, os
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health(self, client):
        async with client as c:
            resp = await c.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_tools_list(self, client):
        async with client as c:
            resp = await c.get("/tools")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["tools"]) >= 7


class TestProcessEndpoint:
    @pytest.mark.asyncio
    async def test_empty_request_rejected(self, client):
        async with client as c:
            resp = await c.post("/process", data={"query": ""})
            assert resp.status_code == 200
            data = resp.json()
            assert data["response_type"] == "clarification"
            assert data["intent"] == "unclear"

    @pytest.mark.asyncio
    async def test_text_only_query(self, client):
        async with client as c:
            resp = await c.post("/process", data={"query": "Hello, how are you?"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["response_type"] in ("answer", "clarification")
            assert len(data["result"]) > 0

    @pytest.mark.asyncio
    async def test_text_only_shortcut(self, client):
        async with client as c:
            resp = await c.post(
                "/process/text",
                json={"query": "What is 2+2?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "result" in data
