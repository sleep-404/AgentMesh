"""
Tests for health monitoring service.
"""
import pytest

from services.registry.schemas import (
    HealthCheckRequest,
)


@pytest.mark.asyncio
async def test_check_agent_health(
    agent_service, health_service, sample_agent_registration
):
    """Test checking agent health"""
    # Register agent
    await agent_service.register_agent(sample_agent_registration)

    # Check health
    request = HealthCheckRequest(
        entity_id=sample_agent_registration.identity,
        entity_type="agent",
    )
    response = await health_service.check_health(request)

    assert response.entity_id == sample_agent_registration.identity
    assert response.entity_type == "agent"
    assert response.status in ["active", "degraded", "offline"]
    assert response.last_check is not None


@pytest.mark.asyncio
async def test_check_kb_health(kb_service, health_service, sample_kb_registration):
    """Test checking KB health"""
    # Register KB
    await kb_service.register_kb(sample_kb_registration)

    # Check health
    request = HealthCheckRequest(
        entity_id=sample_kb_registration.kb_id,
        entity_type="kb",
    )
    response = await health_service.check_health(request)

    assert response.entity_id == sample_kb_registration.kb_id
    assert response.entity_type == "kb"
    assert response.status in ["active", "degraded", "offline"]
    assert response.last_check is not None


@pytest.mark.asyncio
async def test_check_health_invalid_entity_type(health_service):
    """Test checking health with invalid entity type"""
    request = HealthCheckRequest(
        entity_id="test-entity",
        entity_type="invalid",
    )

    with pytest.raises(ValueError):
        await health_service.check_health(request)


@pytest.mark.asyncio
async def test_check_health_not_found(health_service):
    """Test checking health for non-existent entity"""
    from services.registry.exceptions import EntityNotFoundError

    request = HealthCheckRequest(
        entity_id="non-existent",
        entity_type="agent",
    )

    with pytest.raises(EntityNotFoundError):
        await health_service.check_health(request)


@pytest.mark.asyncio
async def test_get_health_summary(
    agent_service,
    kb_service,
    health_service,
    sample_agent_registration,
    sample_kb_registration,
):
    """Test getting health summary"""
    # Register some entities
    await agent_service.register_agent(sample_agent_registration)
    await kb_service.register_kb(sample_kb_registration)

    # Get summary
    summary = await health_service.get_health_summary()

    assert "agents" in summary
    assert "kbs" in summary
    assert summary["agents"]["total"] == 1
    assert summary["kbs"]["total"] == 1
    assert "timestamp" in summary


@pytest.mark.asyncio
async def test_start_stop_monitoring(health_service):
    """Test starting and stopping health monitoring"""
    # Start monitoring
    await health_service.start_monitoring(interval_seconds=1)

    # Give it a moment to run
    import asyncio

    await asyncio.sleep(0.5)

    # Stop monitoring
    await health_service.stop_monitoring()

    # Should complete without errors
    assert True
