import pytest
from httpx import ASGITransport, AsyncClient
from backend.app.main import app


@pytest.mark.asyncio
async def test_system_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "locked_queues" in data
        assert "recovery_needed_count" in data


@pytest.mark.asyncio
async def test_config_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/config")
        assert res.status_code == 200
        data = res.json()
        assert "host" in data
        assert "port" in data
        assert "management_port" in data


@pytest.mark.asyncio
async def test_operations_list_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/operations")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
