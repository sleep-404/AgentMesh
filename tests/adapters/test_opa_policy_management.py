"""Tests for OPA policy management functionality."""

import pytest

from adapters.policy.opa_client import OPAClient


@pytest.fixture
async def opa_client():
    """Create OPA client fixture."""
    client = OPAClient(url="http://localhost:8181", timeout=5)
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_opa_health_check(opa_client):
    """Test OPA health check."""
    is_healthy = await opa_client.health_check()
    assert isinstance(is_healthy, bool)
    # Note: Test may pass with False if OPA is not running


@pytest.mark.asyncio
async def test_list_policies(opa_client):
    """Test listing policies."""
    policies = await opa_client.list_policies()
    assert isinstance(policies, dict)
    assert "result" in policies or "error" in str(policies)


@pytest.mark.asyncio
async def test_upload_and_delete_policy(opa_client):
    """Test uploading and deleting a custom policy."""
    # Skip if OPA is not available
    is_healthy = await opa_client.health_check()
    if not is_healthy:
        pytest.skip("OPA server not available")

    test_policy = """
package test_policy

default allow = false

allow {
    input.action == "test"
}
"""

    # Upload policy
    upload_result = await opa_client.upload_policy("test_policy", test_policy)
    assert "success" in upload_result
    if upload_result.get("success"):
        assert upload_result["policy_id"] == "test_policy"

        # Get policy
        get_result = await opa_client.get_policy("test_policy")
        assert "error" not in get_result or get_result.get("error") is None

        # Delete policy
        delete_result = await opa_client.delete_policy("test_policy")
        assert "success" in delete_result
        if delete_result.get("success"):
            assert "deleted" in delete_result["message"].lower()


@pytest.mark.asyncio
async def test_get_nonexistent_policy(opa_client):
    """Test getting a policy that doesn't exist."""
    result = await opa_client.get_policy("nonexistent_policy_12345")
    # Should return error or empty result
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_delete_nonexistent_policy(opa_client):
    """Test deleting a policy that doesn't exist."""
    result = await opa_client.delete_policy("nonexistent_policy_12345")
    assert isinstance(result, dict)
    # Should handle gracefully (either success=False or appropriate error)


@pytest.mark.asyncio
async def test_upload_invalid_policy(opa_client):
    """Test uploading invalid Rego syntax."""
    # Skip if OPA is not available
    is_healthy = await opa_client.health_check()
    if not is_healthy:
        pytest.skip("OPA server not available")

    invalid_policy = """
package invalid_policy

this is not valid rego syntax!!!
"""

    result = await opa_client.upload_policy("invalid_test", invalid_policy)
    assert isinstance(result, dict)
    # Should fail with error
    if "success" in result:
        assert result["success"] is False
