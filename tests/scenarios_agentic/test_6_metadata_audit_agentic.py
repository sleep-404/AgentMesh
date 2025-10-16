"""
AGENTIC TEST SECTION 6: Metadata & Audit Queries

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
from datetime import UTC, datetime, timedelta

import pytest

from dummy_agents.simple_nats_agent import SimpleNATSAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
class TestSection6MetadataAuditAgentic:
    """
    AGENTIC Test Suite: Metadata & Audit Queries
    
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

    async def test_6_1_user_queries_audit_logs_agentic(self):
        """
        Test 6.1: User Queries Audit Logs (AGENTIC)
        
        Demonstrates:
        - Agent queries audit logs via NATS only
        - Mesh handles audit log access and filtering
        - Can filter by event type, source, target, outcome, time range
        - NO knowledge of SQLitePersistenceAdapter or AuditQuery schema
        - Agent sees audit trail of mesh activities
        """
        logger.info("=" * 60)
        logger.info("TEST 6.1: User Queries Audit Logs (AGENTIC)")
        logger.info("=" * 60)

        # Create test agents to generate audit events
        import uuid
        agent1 = SimpleNATSAgent("nats://localhost:4222")
        agent2 = SimpleNATSAgent("nats://localhost:4222")
        query_agent = SimpleNATSAgent("nats://localhost:4222")

        try:
            # Step 1: Generate some audit events by performing actions
            await agent1.connect_to_mesh()
            await agent2.connect_to_mesh()
            await query_agent.connect_to_mesh()

            test_agent1_id = f"audit-test-agent-1-{uuid.uuid4().hex[:8]}"
            test_agent2_id = f"audit-test-agent-2-{uuid.uuid4().hex[:8]}"
            test_kb_id = f"audit-test-kb-{uuid.uuid4().hex[:8]}"

            logger.info("📝 Generating audit events...")

            # Register agents (creates "register" audit events)
            await agent1.register_with_mesh(
                identity=test_agent1_id,
                capabilities=["query_kb"],
                operations=["query"],
            )
            logger.info(f"✅ Registered {test_agent1_id}")

            await agent2.register_with_mesh(
                identity=test_agent2_id,
                capabilities=["query_kb", "invoke_agent"],
                operations=["query", "invoke"],
            )
            logger.info(f"✅ Registered {test_agent2_id}")

            # Register KB (creates another "register" audit event)
            await query_agent.register_kb(
                kb_id=test_kb_id,
                kb_type="postgres",
                endpoint="postgresql://localhost:5432/test_db",
                operations=["sql_query"],
            )
            logger.info(f"✅ Registered {test_kb_id}")

            # Allow audit events to be written
            await asyncio.sleep(1.0)

            # Step 2: Query audit logs via NATS (NO direct persistence access)
            logger.info("\n--- Querying Audit Logs via NATS ---")

            # Query all audit logs (no filters)
            all_logs = await query_agent.query_audit_logs(limit=100)
            logger.info(f"📊 Total audit logs: {all_logs['total_count']}")
            assert all_logs["total_count"] >= 3, "Should have at least 3 audit events"
            assert "audit_logs" in all_logs
            assert len(all_logs["audit_logs"]) > 0

            # Verify audit log structure
            sample_log = all_logs["audit_logs"][0]
            assert "id" in sample_log
            assert "event_type" in sample_log
            assert "source_id" in sample_log
            assert "outcome" in sample_log
            assert "timestamp" in sample_log
            logger.info("✅ Audit log structure verified")

            # Query by event type (filter for registration events)
            register_logs = await query_agent.query_audit_logs(
                event_type="register",
                limit=100,
            )
            logger.info(f"📊 Registration audit logs: {register_logs['total_count']}")
            assert register_logs["total_count"] >= 3, "Should have at least 3 registration events"
            
            # Verify all returned logs are "register" type
            for log in register_logs["audit_logs"]:
                assert log["event_type"] == "register"
            logger.info("✅ Event type filter works correctly")

            # Query by source (filter by specific agent)
            agent1_logs = await query_agent.query_audit_logs(
                source_id=test_agent1_id,
                limit=100,
            )
            logger.info(f"📊 Audit logs from {test_agent1_id}: {agent1_logs['total_count']}")
            assert agent1_logs["total_count"] >= 1, "Should have at least 1 event from agent1"
            
            # Verify all returned logs are from agent1
            for log in agent1_logs["audit_logs"]:
                assert log["source_id"] == test_agent1_id
            logger.info("✅ Source filter works correctly")

            # Query by outcome (filter for successful events)
            success_logs = await query_agent.query_audit_logs(
                outcome="success",
                limit=100,
            )
            logger.info(f"📊 Successful audit logs: {success_logs['total_count']}")
            assert success_logs["total_count"] >= 3, "Should have successful events"
            
            # Verify all returned logs have "success" outcome
            for log in success_logs["audit_logs"]:
                assert log["outcome"] == "success"
            logger.info("✅ Outcome filter works correctly")

            # Query by time range (last 5 minutes)
            now = datetime.now(UTC)
            five_minutes_ago = now - timedelta(minutes=5)
            
            recent_logs = await query_agent.query_audit_logs(
                start_time=five_minutes_ago.isoformat(),
                end_time=now.isoformat(),
                limit=100,
            )
            logger.info(f"📊 Recent audit logs (last 5 min): {recent_logs['total_count']}")
            assert recent_logs["total_count"] >= 3, "Should have recent events"
            logger.info("✅ Time range filter works correctly")

            # Query with multiple filters (specific agent + event type)
            filtered_logs = await query_agent.query_audit_logs(
                source_id=test_agent2_id,
                event_type="register",
                outcome="success",
                limit=100,
            )
            logger.info(f"📊 Filtered audit logs: {filtered_logs['total_count']}")
            assert filtered_logs["total_count"] >= 1, "Should have filtered events"
            
            # Verify filters are applied correctly
            for log in filtered_logs["audit_logs"]:
                assert log["source_id"] == test_agent2_id
                assert log["event_type"] == "register"
                assert log["outcome"] == "success"
            logger.info("✅ Multiple filters work correctly")

            # Query by target (KB-related events)
            kb_logs = await query_agent.query_audit_logs(
                target_id=test_kb_id,
                limit=100,
            )
            logger.info(f"📊 KB-related audit logs: {kb_logs['total_count']}")
            if kb_logs["total_count"] > 0:
                for log in kb_logs["audit_logs"]:
                    assert log["target_id"] == test_kb_id
                logger.info("✅ Target filter works correctly")

            logger.info("\n--- Audit Query Results ---")
            logger.info(f"✅ Total audit logs: {all_logs['total_count']}")
            logger.info(f"✅ Registration events: {register_logs['total_count']}")
            logger.info(f"✅ Agent1 events: {agent1_logs['total_count']}")
            logger.info(f"✅ Successful events: {success_logs['total_count']}")
            logger.info(f"✅ Recent events: {recent_logs['total_count']}")
            logger.info(f"✅ Filtered events: {filtered_logs['total_count']}")
            logger.info("✅ Agent can query audit trail without direct persistence access")

            logger.info("=" * 60)
            logger.info("TEST 6.1: PASSED ✅")
            logger.info("=" * 60)

        finally:
            await agent1.disconnect()
            await agent2.disconnect()
            await query_agent.disconnect()

    async def test_6_2_user_queries_agent_registry_agentic(self):
        """
        Test 6.2: User Queries Agent Registry (AGENTIC)
        
        Demonstrates:
        - Agent queries registry for detailed agent/KB information via NATS
        - Mesh handles directory queries with various filters
        - Can discover agents by capability, status, and other attributes
        - Can discover KBs by type, status, and operations
        - NO knowledge of DirectoryService or RegistryQuery schema
        - Dynamic discovery of mesh entities
        """
        logger.info("=" * 60)
        logger.info("TEST 6.2: User Queries Agent Registry (AGENTIC)")
        logger.info("=" * 60)

        # Setup: Register multiple agents and KBs with different attributes
        import uuid
        setup_agent = SimpleNATSAgent("nats://localhost:4222")
        query_agent = None  # Initialize for cleanup

        try:
            await setup_agent.connect_to_mesh()

            # Register diverse set of agents
            sales_id = f"sales-agent-reg-{uuid.uuid4().hex[:8]}"
            marketing_id = f"marketing-agent-reg-{uuid.uuid4().hex[:8]}"
            engineering_id = f"engineering-agent-reg-{uuid.uuid4().hex[:8]}"

            logger.info("📝 Registering test agents...")

            await setup_agent.register_with_mesh(
                identity=sales_id,
                version="1.0.0",
                capabilities=["query_kb", "write_kb"],
                operations=["query", "execute"],
            )
            logger.info(f"✅ Registered {sales_id}")

            await setup_agent.register_with_mesh(
                identity=marketing_id,
                version="2.1.0",
                capabilities=["query_kb", "invoke_agent"],
                operations=["query", "invoke"],
            )
            logger.info(f"✅ Registered {marketing_id}")

            await setup_agent.register_with_mesh(
                identity=engineering_id,
                version="1.5.0",
                capabilities=["query_kb", "write_kb", "invoke_agent"],
                operations=["query", "execute", "invoke"],
            )
            logger.info(f"✅ Registered {engineering_id}")

            # Register diverse set of KBs
            postgres_kb_id = f"postgres-kb-reg-{uuid.uuid4().hex[:8]}"
            neo4j_kb_id = f"neo4j-kb-reg-{uuid.uuid4().hex[:8]}"

            logger.info("📝 Registering test KBs...")

            await setup_agent.register_kb(
                kb_id=postgres_kb_id,
                kb_type="postgres",
                endpoint="postgresql://localhost:5432/sales_db",
                operations=["sql_query", "execute_sql"],
            )
            logger.info(f"✅ Registered {postgres_kb_id}")

            await setup_agent.register_kb(
                kb_id=neo4j_kb_id,
                kb_type="neo4j",
                endpoint="bolt://localhost:7687",
                operations=["cypher_query", "create_node"],
            )
            logger.info(f"✅ Registered {neo4j_kb_id}")

            # Allow registry updates to propagate
            await asyncio.sleep(1.0)

            # Now use query agent to discover entities
            query_agent = SimpleNATSAgent("nats://localhost:4222")
            await query_agent.connect_to_mesh()

            logger.info("\n--- Querying Agent Registry via NATS ---")

            # Query all agents (no filters)
            all_agents = await query_agent.discover_agents()
            logger.info(f"📊 Total agents in registry: {all_agents['total_count']}")
            assert all_agents["total_count"] >= 3, "Should have at least 3 agents"

            # Verify agent structure
            for agent in all_agents["agents"]:
                assert "agent_id" in agent
                assert "identity" in agent
                assert "version" in agent
                assert "capabilities" in agent
                assert "operations" in agent
                assert "status" in agent
                assert "registered_at" in agent
            logger.info("✅ Agent registry structure verified")

            # Query agents by capability (query_kb)
            query_capable = await query_agent.discover_agents(
                capability_filter="query_kb"
            )
            logger.info(
                f"📊 Agents with 'query_kb' capability: {query_capable['total_count']}"
            )
            assert query_capable["total_count"] >= 3, "Should have at least 3 query-capable agents"
            
            # Verify all have query_kb capability
            for agent in query_capable["agents"]:
                assert "query_kb" in agent["capabilities"]
            logger.info("✅ Capability filter works correctly")

            # Query agents by capability (write_kb)
            write_capable = await query_agent.discover_agents(
                capability_filter="write_kb"
            )
            logger.info(
                f"📊 Agents with 'write_kb' capability: {write_capable['total_count']}"
            )
            assert write_capable["total_count"] >= 2, "Should have at least 2 write-capable agents"
            
            # Verify all have write_kb capability
            for agent in write_capable["agents"]:
                assert "write_kb" in agent["capabilities"]
            logger.info("✅ Write capability filter works correctly")

            # Query agents by capability (invoke_agent)
            invoke_capable = await query_agent.discover_agents(
                capability_filter="invoke_agent"
            )
            logger.info(
                f"📊 Agents with 'invoke_agent' capability: {invoke_capable['total_count']}"
            )
            assert invoke_capable["total_count"] >= 2, "Should have at least 2 invoke-capable agents"
            logger.info("✅ Invoke capability filter works correctly")

            # Query all KBs
            all_kbs = await query_agent.discover_kbs()
            logger.info(f"📊 Total KBs in registry: {all_kbs['total_count']}")
            assert all_kbs["total_count"] >= 2, "Should have at least 2 KBs"

            # Verify KB structure
            for kb in all_kbs["kbs"]:
                assert "kb_id" in kb
                assert "kb_type" in kb
                assert "operations" in kb
                assert "status" in kb
                assert "registered_at" in kb
            logger.info("✅ KB registry structure verified")

            # Query KBs by type (postgres)
            postgres_kbs = await query_agent.discover_kbs(type_filter="postgres")
            logger.info(f"📊 Postgres KBs: {postgres_kbs['total_count']}")
            assert postgres_kbs["total_count"] >= 1, "Should have at least 1 Postgres KB"
            
            # Verify all are postgres type
            for kb in postgres_kbs["kbs"]:
                assert kb["kb_type"] == "postgres"
            logger.info("✅ Postgres type filter works correctly")

            # Query KBs by type (neo4j)
            neo4j_kbs = await query_agent.discover_kbs(type_filter="neo4j")
            logger.info(f"📊 Neo4j KBs: {neo4j_kbs['total_count']}")
            assert neo4j_kbs["total_count"] >= 1, "Should have at least 1 Neo4j KB"
            
            # Verify all are neo4j type
            for kb in neo4j_kbs["kbs"]:
                assert kb["kb_type"] == "neo4j"
            logger.info("✅ Neo4j type filter works correctly")

            # Verify specific agents are in registry
            agent_identities = [a["identity"] for a in all_agents["agents"]]
            assert sales_id in agent_identities
            assert marketing_id in agent_identities
            assert engineering_id in agent_identities
            logger.info("✅ All registered agents found in directory")

            # Verify specific KBs are in registry
            kb_ids = [kb["kb_id"] for kb in all_kbs["kbs"]]
            assert postgres_kb_id in kb_ids
            assert neo4j_kb_id in kb_ids
            logger.info("✅ All registered KBs found in directory")

            # Get details of specific agent
            sales_agent = next(
                (a for a in all_agents["agents"] if a["identity"] == sales_id), None
            )
            assert sales_agent is not None
            assert sales_agent["version"] == "1.0.0"
            assert "query_kb" in sales_agent["capabilities"]
            assert "write_kb" in sales_agent["capabilities"]
            logger.info(f"✅ Sales agent details retrieved: {sales_agent['identity']}")

            # Get details of specific KB
            postgres_kb = next(
                (kb for kb in all_kbs["kbs"] if kb["kb_id"] == postgres_kb_id), None
            )
            assert postgres_kb is not None
            assert postgres_kb["kb_type"] == "postgres"
            assert "sql_query" in postgres_kb["operations"]
            assert "execute_sql" in postgres_kb["operations"]
            logger.info(f"✅ Postgres KB details retrieved: {postgres_kb['kb_id']}")

            logger.info("\n--- Registry Query Results ---")
            logger.info(f"✅ Total agents: {all_agents['total_count']}")
            logger.info(f"✅ Query-capable agents: {query_capable['total_count']}")
            logger.info(f"✅ Write-capable agents: {write_capable['total_count']}")
            logger.info(f"✅ Invoke-capable agents: {invoke_capable['total_count']}")
            logger.info(f"✅ Total KBs: {all_kbs['total_count']}")
            logger.info(f"✅ Postgres KBs: {postgres_kbs['total_count']}")
            logger.info(f"✅ Neo4j KBs: {neo4j_kbs['total_count']}")
            logger.info("✅ Agent can query registry without direct directory service access")

            logger.info("=" * 60)
            logger.info("TEST 6.2: PASSED ✅")
            logger.info("=" * 60)

        finally:
            await setup_agent.disconnect()
            if query_agent:
                await query_agent.disconnect()


if __name__ == "__main__":
    """
    Run tests directly (requires mesh service to be running).
    
    Start mesh service first:
        python -m services.bootstrap.mesh_service
    
    Then run tests:
        python -m pytest tests/scenarios_agentic/test_6_metadata_audit_agentic.py -v -s
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

