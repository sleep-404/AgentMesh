"""
Tests for agent registration service.
"""
import pytest

from services.registry.exceptions import (
    DuplicateIdentityError,
    ValidationError,
)
from services.registry.schemas import AgentRegistrationRequest


@pytest.mark.asyncio
async def test_register_agent_success(agent_service, sample_agent_registration):
    """Test successful agent registration"""
    response = await agent_service.register_agent(sample_agent_registration)

    assert response.agent_id is not None
    assert response.identity == sample_agent_registration.identity
    assert response.version == sample_agent_registration.version
    assert response.status in ["active", "offline"]
    assert response.message is not None


@pytest.mark.asyncio
async def test_register_agent_duplicate_identity(
    agent_service, sample_agent_registration
):
    """Test that duplicate agent identities are rejected"""
    # Register first time
    await agent_service.register_agent(sample_agent_registration)

    # Try to register again with same identity
    with pytest.raises(DuplicateIdentityError):
        await agent_service.register_agent(sample_agent_registration)


@pytest.mark.asyncio
async def test_register_agent_invalid_version(agent_service):
    """Test that invalid version format is rejected"""
    invalid_request = AgentRegistrationRequest(
        identity="test-agent-2",
        version="invalid-version",  # Not semver
        capabilities=["test"],
        operations=["query"],
        health_endpoint="http://localhost:8001/health",
    )

    with pytest.raises(ValidationError) as exc_info:
        await agent_service.register_agent(invalid_request)

    assert "version" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_agent_empty_capabilities(agent_service):
    """Test that empty capabilities list is rejected"""
    invalid_request = AgentRegistrationRequest(
        identity="test-agent-3",
        version="1.0.0",
        capabilities=[],  # Empty
        operations=["query"],
        health_endpoint="http://localhost:8001/health",
    )

    with pytest.raises(ValidationError) as exc_info:
        await agent_service.register_agent(invalid_request)

    assert "capabilities" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_agent_invalid_operations(agent_service):
    """Test that invalid operations are rejected"""
    invalid_request = AgentRegistrationRequest(
        identity="test-agent-4",
        version="1.0.0",
        capabilities=["test"],
        operations=["invalid_op"],  # Not in allowed list
        health_endpoint="http://localhost:8001/health",
    )

    with pytest.raises(ValidationError) as exc_info:
        await agent_service.register_agent(invalid_request)

    assert "operations" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_agent_invalid_url(agent_service):
    """Test that invalid health endpoint URL is rejected"""
    invalid_request = AgentRegistrationRequest(
        identity="test-agent-5",
        version="1.0.0",
        capabilities=["test"],
        operations=["query"],
        health_endpoint="not-a-url",  # Invalid URL
    )

    with pytest.raises(ValidationError) as exc_info:
        await agent_service.register_agent(invalid_request)

    assert "health_endpoint" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_agent_details(agent_service, sample_agent_registration):
    """Test retrieving agent details"""
    # Register agent
    await agent_service.register_agent(sample_agent_registration)

    # Get details
    details = await agent_service.get_agent_details(sample_agent_registration.identity)

    assert details.identity == sample_agent_registration.identity
    assert details.version == sample_agent_registration.version
    assert details.capabilities == sample_agent_registration.capabilities
    assert details.operations == sample_agent_registration.operations


@pytest.mark.asyncio
async def test_get_agent_details_not_found(agent_service):
    """Test getting details for non-existent agent"""
    from services.registry.exceptions import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        await agent_service.get_agent_details("non-existent-agent")


@pytest.mark.asyncio
async def test_deregister_agent(agent_service, sample_agent_registration):
    """Test deregistering an agent"""
    # Register agent
    await agent_service.register_agent(sample_agent_registration)

    # Deregister
    await agent_service.deregister_agent(sample_agent_registration.identity)

    # Verify it's gone
    from services.registry.exceptions import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        await agent_service.get_agent_details(sample_agent_registration.identity)
