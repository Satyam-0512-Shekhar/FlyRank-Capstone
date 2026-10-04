"""
Integration tests for strict tenant isolation and IDOR elimination.
Tests DESIGN.md §13 requirements.
"""

import pytest


@pytest.mark.asyncio
async def test_cross_tenant_access_denied_idor_protection(client):
    """
    Verify Tenant A cannot access Tenant B's data via URL path tampering.
    Must return 403 Forbidden with 'forbidden' error code.
    """
    # 1. Register Tenant A
    res_a = await client.post("/api/v1/tenants", json={"name": "Tenant Alpha"})
    assert res_a.status_code == 201
    tenant_a_id = res_a.json()["id"]

    # 2. Register Tenant B
    res_b = await client.post("/api/v1/tenants", json={"name": "Tenant Beta"})
    assert res_b.status_code == 201
    tenant_b_id = res_b.json()["id"]

    # 3. Tenant A requests Tenant A's endpoint -> Allowed (200 OK)
    res_own = await client.get(
        f"/api/v1/tenants/{tenant_a_id}",
        headers={"X-Tenant-ID": tenant_a_id},
    )
    assert res_own.status_code == 200
    assert res_own.json()["name"] == "Tenant Alpha"

    # 4. Tenant A attempts to access Tenant B's endpoint -> Denied (403 Forbidden)
    res_idor = await client.get(
        f"/api/v1/tenants/{tenant_b_id}",
        headers={"X-Tenant-ID": tenant_a_id},
    )
    assert res_idor.status_code == 403
    data = res_idor.json()
    assert data["error"] == "forbidden"
    assert "Cross-tenant access denied" in data["message"]

    # 5. Tenant B attempts to access Tenant A's endpoint -> Denied (403 Forbidden)
    res_idor_reverse = await client.get(
        f"/api/v1/tenants/{tenant_a_id}",
        headers={"X-Tenant-ID": tenant_b_id},
    )
    assert res_idor_reverse.status_code == 403
    assert res_idor_reverse.json()["error"] == "forbidden"
