"""
Tests for directory query service.
"""
import pytest

from services.registry.schemas import (
    AgentListRequest,
    AgentRegistrationRequest,
    KBListRequest,
    KBRegistrationRequest,
)


@pytest.mark.asyncio
async def test_list_agents_empty(directory_service):
    """Test listing agents when registry is empty"""
    request = AgentListRequest()
    response = await directory_service.list_agents(request)

    assert response.total_count == 0
    assert len(response.agents) == 0


@pytest.mark.asyncio
async def test_list_agents_with_results(
    agent_service, directory_service, sample_agent_registration
):
    """Test listing agents with results"""
    # Register some agents
    await agent_service.register_agent(sample_agent_registration)

    agent2 = AgentRegistrationRequest(
        identity="test-agent-2",
        version="2.0.0",
        capabilities=["different_capability"],
        operations=["publish"],
        health_endpoint="http://localhost:8002/health",
    )
    await agent_service.register_agent(agent2)

    # List all agents
    request = AgentListRequest()
    response = await directory_service.list_agents(request)

    assert response.total_count == 2
    assert len(response.agents) == 2


@pytest.mark.asyncio
async def test_list_agents_with_capability_filter(
    agent_service, directory_service, sample_agent_registration
):
    """Test filtering agents by capability"""
    # Register agents with different capabilities
    await agent_service.register_agent(sample_agent_registration)

    agent2 = AgentRegistrationRequest(
        identity="test-agent-2",
        version="2.0.0",
        capabilities=["different_capability"],
        operations=["publish"],
        health_endpoint="http://localhost:8002/health",
    )
    await agent_service.register_agent(agent2)

    # Filter by specific capability
    request = AgentListRequest(capability_filter="query_kb")
    response = await directory_service.list_agents(request)

    assert response.total_count == 1
    assert response.agents[0].identity == sample_agent_registration.identity


@pytest.mark.asyncio
async def test_list_kbs_empty(directory_service):
    """Test listing KBs when registry is empty"""
    request = KBListRequest()
    response = await directory_service.list_kbs(request)

    assert response.total_count == 0
    assert len(response.kbs) == 0


@pytest.mark.asyncio
async def test_list_kbs_with_results(
    kb_service, directory_service, sample_kb_registration
):
    """Test listing KBs with results"""
    # Register some KBs
    await kb_service.register_kb(sample_kb_registration)

    kb2 = KBRegistrationRequest(
        kb_id="test-kb-2",
        kb_type="neo4j",
        endpoint="bolt://localhost:7687",
        operations=["cypher_query"],
    )
    await kb_service.register_kb(kb2)

    # List all KBs
    request = KBListRequest()
    response = await directory_service.list_kbs(request)

    assert response.total_count == 2
    assert len(response.kbs) == 2


@pytest.mark.asyncio
async def test_list_kbs_with_type_filter(
    kb_service, directory_service, sample_kb_registration
):
    """Test filtering KBs by type"""
    # Register KBs with different types
    await kb_service.register_kb(sample_kb_registration)

    kb2 = KBRegistrationRequest(
        kb_id="test-kb-2",
        kb_type="neo4j",
        endpoint="bolt://localhost:7687",
        operations=["cypher_query"],
    )
    await kb_service.register_kb(kb2)

    # Filter by type
    request = KBListRequest(type_filter="postgres")
    response = await directory_service.list_kbs(request)

    assert response.total_count == 1
    assert response.kbs[0].kb_type == "postgres"


@pytest.mark.asyncio
async def test_find_agents_by_capability(
    agent_service, directory_service, sample_agent_registration
):
    """Test finding agents by capability"""
    await agent_service.register_agent(sample_agent_registration)

    agents = await directory_service.find_agents_by_capability("query_kb")

    assert len(agents) == 1
    assert agents[0].identity == sample_agent_registration.identity


@pytest.mark.asyncio
async def test_find_kbs_by_type(kb_service, directory_service, sample_kb_registration):
    """Test finding KBs by type"""
    await kb_service.register_kb(sample_kb_registration)

    kbs = await directory_service.find_kbs_by_type("postgres")

    assert len(kbs) == 1
    assert kbs[0].kb_id == sample_kb_registration.kb_id


@pytest.mark.asyncio
async def test_get_directory_summary(
    agent_service,
    kb_service,
    directory_service,
    sample_agent_registration,
    sample_kb_registration,
):
    """Test getting directory summary"""
    # Register some entities
    await agent_service.register_agent(sample_agent_registration)
    await kb_service.register_kb(sample_kb_registration)

    summary = await directory_service.get_directory_summary()

    assert summary["total_agents"] == 1
    assert summary["total_kbs"] == 1
    assert "agent_status_counts" in summary
    assert "kb_status_counts" in summary
    assert "kb_type_counts" in summary
