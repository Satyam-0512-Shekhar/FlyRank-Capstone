"""
Integration tests for Tenant API endpoints (/api/v1/tenants).
"""

import uuid
import pytest


@pytest.mark.asyncio
async def test_create_tenant_endpoint_success(client):
    """POST /api/v1/tenants creates a new tenant with Free plan."""
    response = await client.post("/api/v1/tenants", json={"name": "Hooli Corp"})
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Hooli Corp"
    assert data["plan"] == "free"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_tenant_invalid_name(client):
    """POST /api/v1/tenants with empty string returns 422 Unprocessable Entity."""
    response = await client.post("/api/v1/tenants", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tenant_me_authenticated(client):
    """GET /api/v1/tenants/me with valid X-Tenant-ID returns tenant profile."""
    # 1. Register tenant
    create_res = await client.post("/api/v1/tenants", json={"name": "Pied Piper"})
    assert create_res.status_code == 201
    tenant_id = create_res.json()["id"]

    # 2. Query profile
    res = await client.get("/api/v1/tenants/me", headers={"X-Tenant-ID": tenant_id})
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == tenant_id
    assert data["name"] == "Pied Piper"
    assert data["plan"]["name"] == "free"
    assert data["plan"]["api_call_quota"] == 1000
    assert data["plan"]["token_quota"] == 100000
    assert data["plan"]["price_micro_inr"] == 0
    assert data["plan"]["formatted_price"] == "₹0.00"
    assert data["subscription"]["status"] == "active"


@pytest.mark.asyncio
async def test_get_tenant_me_missing_header(client):
    """GET /api/v1/tenants/me without X-Tenant-ID header returns 400 Bad Request."""
    res = await client.get("/api/v1/tenants/me")
    assert res.status_code == 400
    data = res.json()
    assert data["error"] == "validation_error"


@pytest.mark.asyncio
async def test_get_tenant_me_invalid_uuid(client):
    """GET /api/v1/tenants/me with invalid UUID returns 400 Bad Request."""
    res = await client.get("/api/v1/tenants/me", headers={"X-Tenant-ID": "not-a-uuid"})
    assert res.status_code == 400
    data = res.json()
    assert data["error"] == "validation_error"


@pytest.mark.asyncio
async def test_get_tenant_me_not_found(client):
    """GET /api/v1/tenants/me with non-existent UUID returns 404 Not Found."""
    random_uuid = str(uuid.uuid4())
    res = await client.get("/api/v1/tenants/me", headers={"X-Tenant-ID": random_uuid})
    assert res.status_code == 404
    data = res.json()
    assert data["error"] == "not_found"
