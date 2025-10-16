"""
AGENTIC TEST SECTION 1: Registration & Discovery

These tests demonstrate agents with ZERO knowledge of mesh internals.
All interactions happen via NATS only.

Prerequisites:
1. NATS server running at localhost:4222
2. OPA server running at localhost:8181
3. AgentMesh service running (python -m services.bootstrap.mesh_service)

Success Criteria:
✅ No imports from services.* or adapters.*
✅ Only NATS communication
✅ Agent identity as authentication
✅ Dynamic discovery
✅ Could be written in any language
"""
import asyncio
import logging

import pytest

from dummy_agents.simple_nats_agent import SimpleNATSAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
class TestSection1RegistrationDiscoveryAgentic:
    """
    AGENTIC Test Suite: Registration & Discovery
    
    All tests use SimpleNATSAgent - an agent that only knows NATS.
    """

    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Setup before each test, cleanup after."""
        # Allow mesh to settle between tests
        await asyncio.sleep(0.5)
        yield
        # Cleanup delay
        await asyncio.sleep(0.5)

    async def test_1_1_user_registers_agent_agentic(self):
        """
        Test 1.1: User Registers Agent (AGENTIC)
        
        Demonstrates:
        - Agent connects to mesh via NATS only
        - Registers itself with identity and capabilities
        - Verifies registration via discovery
        - NO knowledge of AgentService, DirectoryService, etc.
        """
        logger.info("=" * 60)
        logger.info("TEST 1.1: User Registers Agent (AGENTIC)")
        logger.info("=" * 60)

        # Create agent with ONLY NATS knowledge
        agent = SimpleNATSAgent("nats://localhost:4222")
        
        try:
            # Step 1: Connect to mesh (NATS only)
            await agent.connect_to_mesh()
            logger.info("✅ Agent connected to mesh via NATS")

            # Step 2: Register via NATS (no direct service calls)
            import uuid
            test_id = f"sales-agent-{uuid.uuid4().hex[:8]}"
            result = await agent.register_with_mesh(
                identity=test_id,
                version="1.0.0",
                capabilities=["query_kb", "invoke_agent"],
                operations=["query", "invoke"],
            )

            # Verify registration response
            assert result["agent_id"] is not None, "Agent ID should be assigned"
            assert result["identity"] == test_id
            assert result["status"] in ["active", "offline"], f"Unexpected status: {result['status']}"
            logger.info(f"✅ Agent registered: {result['identity']} (status: {result['status']})")

            # Step 3: Verify via discovery (also through NATS)
            await asyncio.sleep(0.5)  # Let directory update propagate
            agents = await agent.discover_agents()

            # Verify our agent is in the directory
            agent_identities = [a["identity"] for a in agents.get("agents", [])]
            assert test_id in agent_identities, f"Registered agent {test_id} not found in directory"
            logger.info(f"✅ Agent found in directory")

            # Verify agent details
            sales_agent = next(a for a in agents["agents"] if a["identity"] == test_id)
            assert "query_kb" in sales_agent["capabilities"]
            assert "invoke_agent" in sales_agent["capabilities"]
            assert sales_agent["version"] == "1.0.0"
            logger.info("✅ Agent capabilities verified")

            logger.info("=" * 60)
            logger.info("TEST 1.1: PASSED ✅")
            logger.info("=" * 60)

        finally:
            await agent.disconnect()

    async def test_1_2_user_registers_kb_agentic(self):
        """
        Test 1.2: User Registers KB (AGENTIC)
        
        Demonstrates:
        - Agent (or admin) registers KB via NATS only
        - Mesh validates KB type and operations
        - Mesh performs connectivity check
        - KB appears in directory
        - NO knowledge of KBService
        """
        logger.info("=" * 60)
        logger.info("TEST 1.2: User Registers KB (AGENTIC)")
        logger.info("=" * 60)

        # Agent acts as admin for KB registration
        agent = SimpleNATSAgent("nats://localhost:4222")

        try:
            await agent.connect_to_mesh()
            logger.info("✅ Connected to mesh")

            # Register KB via NATS (no direct KBService calls)
            import uuid
            test_kb_id = f"sales-kb-{uuid.uuid4().hex[:8]}"
            result = await agent.register_kb(
                kb_id=test_kb_id,
                kb_type="postgres",
                endpoint="postgresql://localhost:5432/test_db",
                operations=["sql_query", "execute_sql"],
                kb_schema={
                    "tables": {
                        "customers": ["id", "name", "email", "phone"],
                        "deals": ["id", "customer_id", "amount", "status"],
                    }
                },
            )

            # Verify registration response
            assert result["kb_id"] == test_kb_id
            assert result["kb_type"] == "postgres"
            assert result["status"] in ["active", "offline"]
            logger.info(f"✅ KB registered: {result['kb_id']} (status: {result['status']})")

            # Verify via discovery
            await asyncio.sleep(0.5)
            kbs = await agent.discover_kbs()

            kb_ids = [kb["kb_id"] for kb in kbs.get("kbs", [])]
            assert test_kb_id in kb_ids, "Registered KB not found in directory"
            logger.info(f"✅ KB found in directory")

            # Verify KB details
            sales_kb = next(kb for kb in kbs["kbs"] if kb["kb_id"] == test_kb_id)
            assert sales_kb["kb_type"] == "postgres"
            assert "sql_query" in sales_kb["operations"]
            assert "execute_sql" in sales_kb["operations"]
            logger.info("✅ KB details verified")

            logger.info("=" * 60)
            logger.info("TEST 1.2: PASSED ✅")
            logger.info("=" * 60)

        finally:
            await agent.disconnect()

    async def test_1_3_agent_discovers_capabilities_agentic(self):
        """
        Test 1.3: Agent Discovers Capabilities (AGENTIC)
        
        Demonstrates:
        - Marketing agent discovers available agents and KBs
        - Uses filters to find specific capabilities
        - Discovers KB types dynamically
        - NO knowledge of DirectoryService
        - Could make decisions based on discovered capabilities
        """
        logger.info("=" * 60)
        logger.info("TEST 1.3: Agent Discovers Capabilities (AGENTIC)")
        logger.info("=" * 60)

        # Setup: Register multiple agents and KBs for discovery
        import uuid
        setup_agent = SimpleNATSAgent("nats://localhost:4222")
        marketing_agent = None  # Initialize for cleanup
        await setup_agent.connect_to_mesh()

        try:
            # Register 2 agents with different capabilities
            sales_id = f"sales-agent-{uuid.uuid4().hex[:8]}"
            await setup_agent.register_with_mesh(
                identity=sales_id,
                capabilities=["query_kb", "write_kb"],
                operations=["query", "execute"],
            )
            logger.info(f"✅ Registered {sales_id}")

            marketing_agent = SimpleNATSAgent("nats://localhost:4222")
            await marketing_agent.connect_to_mesh()

            marketing_id = f"marketing-agent-{uuid.uuid4().hex[:8]}"
            await marketing_agent.register_with_mesh(
                identity=marketing_id,
                capabilities=["query_kb", "invoke_agent"],
                operations=["query", "invoke"],
            )
            logger.info(f"✅ Registered {marketing_id}")

            # Register KB
            kb_id = f"engineering-kb-{uuid.uuid4().hex[:8]}"
            await setup_agent.register_kb(
                kb_id=kb_id,
                kb_type="neo4j",
                endpoint="bolt://localhost:7687",
                operations=["cypher_query", "create_node"],
            )
            logger.info(f"✅ Registered {kb_id}")

            await asyncio.sleep(1.0)  # Let directory updates propagate

            # Now marketing agent discovers what's available
            logger.info("\n--- Marketing Agent Starting Discovery ---")

            # Discover all agents
            all_agents = await marketing_agent.discover_agents()
            total = all_agents.get("total_count", len(all_agents.get("agents", [])))
            logger.info(f"📊 Discovered {total} total agents")
            assert total >= 2, "Should have at least 2 agents"

            # Discover agents with specific capability
            query_capable_agents = await marketing_agent.discover_agents(
                capability_filter="query_kb"
            )
            query_total = query_capable_agents.get("total_count", len(query_capable_agents.get("agents", [])))
            logger.info(
                f"📊 Discovered {query_total} agents with 'query_kb' capability"
            )
            assert query_total >= 2

            # Verify filtered results
            for agent_info in query_capable_agents.get("agents", []):
                assert "query_kb" in agent_info["capabilities"]
            logger.info("✅ All discovered agents have 'query_kb' capability")

            # Discover agents with write capability
            write_capable_agents = await marketing_agent.discover_agents(
                capability_filter="write_kb"
            )
            write_total = write_capable_agents.get("total_count", len(write_capable_agents.get("agents", [])))
            logger.info(
                f"📊 Discovered {write_total} agents with 'write_kb' capability"
            )
            assert write_total >= 1

            # Discover all KBs
            all_kbs = await marketing_agent.discover_kbs()
            kb_total = all_kbs.get("total_count", len(all_kbs.get("kbs", [])))
            logger.info(f"📊 Discovered {kb_total} total KBs")
            assert kb_total >= 1

            # Discover Neo4j KBs specifically
            neo4j_kbs = await marketing_agent.discover_kbs(type_filter="neo4j")
            neo4j_total = neo4j_kbs.get("total_count", len(neo4j_kbs.get("kbs", [])))
            logger.info(f"📊 Discovered {neo4j_total} Neo4j KBs")
            assert neo4j_total >= 1

            # Verify filtered KB results
            for kb_info in neo4j_kbs.get("kbs", []):
                assert kb_info["kb_type"] == "neo4j"
            logger.info("✅ All discovered KBs are Neo4j type")

            # Marketing agent can now make informed decisions
            logger.info("\n--- Marketing Agent Decision Making ---")
            logger.info(f"✅ Can query {query_total} agents for KB access")
            logger.info(f"✅ Can write through {write_total} agents")
            logger.info(f"✅ Can use {neo4j_total} Neo4j knowledge bases")
            logger.info("✅ Agent has complete dynamic knowledge of mesh capabilities")

            logger.info("=" * 60)
            logger.info("TEST 1.3: PASSED ✅")
            logger.info("=" * 60)

        finally:
            await setup_agent.disconnect()
            if marketing_agent:
                await marketing_agent.disconnect()


if __name__ == "__main__":
    """
    Run tests directly (requires mesh service to be running).
    
    Start mesh service first:
        python -m services.bootstrap.mesh_service
    
    Then run tests:
        python -m pytest tests/scenarios_agentic/test_1_registration_discovery_agentic.py -v -s
    """
    import sys

    # Check if mesh is reachable
    async def check_mesh():
        agent = SimpleNATSAgent()
        try:
            await agent.connect_to_mesh()
            await agent.disconnect()
            logger.info("✅ Mesh service is reachable")
            return True
        except Exception as e:
            logger.error(f"❌ Cannot reach mesh service: {e}")
            logger.error("Please start mesh service: python -m services.bootstrap.mesh_service")
            return False

    if not asyncio.run(check_mesh()):
        sys.exit(1)

    pytest.main([__file__, "-v", "-s"])

