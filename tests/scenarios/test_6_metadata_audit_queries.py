"""
Test Suite: Section 6 - Metadata & Audit Queries

Tests scenarios:
- 6.1: User Queries Audit Logs
- 6.2: User Queries Agent Registry
"""

import asyncio
import json
from datetime import datetime, timedelta, UTC

import pytest

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.schemas import (
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditQuery,
    RegistryQuery,
)
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from services.registry import AgentService, DirectoryService, KBService
from services.registry.schemas import (
    AgentRegistrationRequest,
    KBRegistrationRequest,
)


class TestSection6MetadataAuditQueries:
    """Test Metadata & Audit Query scenarios"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test fixtures"""
        # Initialize persistence adapter
        self.persistence = SQLitePersistenceAdapter(
            "adapters/persistence/sqlite/config.yaml"
        )
        await self.persistence.connect()

        # Initialize NATS client (optional)
        self.nats_client = NATSWrapper()
        try:
            await self.nats_client.connect()
            self.nats_available = True
        except Exception:
            self.nats_available = False
            self.nats_client = None

        # Initialize services
        self.agent_service = AgentService(self.persistence, self.nats_client)
        self.kb_service = KBService(self.persistence, self.nats_client)
        self.directory_service = DirectoryService(self.persistence)

        # Clean up test entities from previous runs
        await self._cleanup_test_entities()

        yield

        # Cleanup
        if self.nats_client:
            await self.nats_client.disconnect()
        await self.persistence.disconnect()

    async def _cleanup_test_entities(self):
        """Clean up test entities that might exist from previous runs"""
        test_agents = [
            "sales-agent-audit",
            "marketing-agent-audit",
            "engineering-agent-audit",
            "finance-agent-audit",
        ]
        test_kbs = ["sales-kb-audit", "engineering-kb-audit"]

        for agent_id in test_agents:
            try:
                await self.agent_service.deregister_agent(agent_id)
            except Exception:
                pass  # Ignore if doesn't exist

        for kb_id in test_kbs:
            try:
                await self.kb_service.deregister_kb(kb_id)
            except Exception:
                pass  # Ignore if doesn't exist

    @pytest.mark.asyncio
    async def test_scenario_6_1_query_audit_logs(self):
        """
        Scenario 6.1: User Queries Audit Logs
        
        Given: User via MCP
        When: User queries: "Show all KB-Sales accesses in last 24 hours"
        Then:
          ✓ Direct SQL query to audit metadata store
          ✓ Results include: timestamp, requester, action, outcome, fields_masked
          ✓ Results filtered by user's own access level (if multi-tenant)
        """
        print("\n=== TEST 6.1: Query Audit Logs ===")

        # Step 1: Register test entities
        print("\nStep 1: Registering test entities...")
        
        # Register KB
        kb_request = KBRegistrationRequest(
            kb_id="sales-kb-audit",
            kb_type="postgres",
            endpoint="postgresql://localhost:5432/sales_db",
            operations=["sql_query", "get_schema"],
            kb_schema={
                "tables": {
                    "customers": ["id", "name", "email", "phone", "region"],
                    "deals": ["id", "customer_id", "amount", "status"],
                }
            },
            metadata={"owner": "sales-team", "environment": "test"},
        )
        kb_id = await self.kb_service.register_kb(kb_request)
        print(f"✓ KB registered: {kb_id}")

        # Register agents
        agent_ids = []
        for agent_name in ["sales-agent-audit", "marketing-agent-audit"]:
            agent_request = AgentRegistrationRequest(
                identity=agent_name,
                version="1.0.0",
                capabilities=["query_kb"],
                operations=["query", "subscribe"],
                health_endpoint=f"http://localhost:8001/{agent_name}/health",
                metadata={"team": agent_name.split("-")[0]},
            )
            agent_id = await self.agent_service.register_agent(agent_request)
            agent_ids.append(agent_name)
            print(f"✓ Agent registered: {agent_name}")

        # Wait a bit for registrations to complete
        await asyncio.sleep(0.1)

        # Step 2: Create diverse audit events
        print("\nStep 2: Creating audit events...")
        
        now = datetime.now(UTC)
        yesterday = now - timedelta(hours=24)
        two_days_ago = now - timedelta(hours=48)
        
        audit_events = [
            # Recent successful query from sales agent
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id="sales-agent-audit",
                target_id="sales-kb-audit",
                outcome=AuditOutcome.SUCCESS,
                timestamp=now - timedelta(hours=2),
                request_metadata={
                    "query": "SELECT * FROM customers WHERE region='APAC'",
                    "latency_ms": 45,
                },
                masked_fields=None,
            ),
            # Recent query with field masking from marketing agent
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id="marketing-agent-audit",
                target_id="sales-kb-audit",
                outcome=AuditOutcome.SUCCESS,
                timestamp=now - timedelta(hours=5),
                request_metadata={
                    "query": "SELECT * FROM customers WHERE region='EMEA'",
                    "latency_ms": 52,
                },
                masked_fields=["email", "phone"],
                policy_decision={
                    "effect": "allow",
                    "matched_policy": "marketing-data-access",
                },
            ),
            # Denied access attempt
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id="marketing-agent-audit",
                target_id="sales-kb-audit",
                outcome=AuditOutcome.DENIED,
                timestamp=now - timedelta(hours=10),
                request_metadata={
                    "query": "DELETE FROM customers WHERE id=123",
                    "denied_reason": "write operation not permitted",
                },
                policy_decision={
                    "effect": "deny",
                    "matched_policy": "marketing-read-only",
                },
            ),
            # Old event (>24 hours ago)
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id="sales-agent-audit",
                target_id="sales-kb-audit",
                outcome=AuditOutcome.SUCCESS,
                timestamp=two_days_ago,
                request_metadata={"query": "SELECT COUNT(*) FROM deals"},
            ),
            # Agent registration event
            AuditEvent(
                event_type=AuditEventType.REGISTER,
                source_id="sales-agent-audit",
                target_id=None,
                outcome=AuditOutcome.SUCCESS,
                timestamp=now - timedelta(hours=3),
                request_metadata={"version": "1.0.0", "capabilities": ["query_kb"]},
            ),
        ]

        event_ids = []
        for event in audit_events:
            event_id = await self.persistence.log_event(event)
            event_ids.append(event_id)
            print(f"✓ Logged audit event: {event.event_type.value} at {event.timestamp}")

        # Step 3: Query all KB-Sales accesses in last 24 hours
        print("\nStep 3: Querying KB accesses in last 24 hours...")
        
        query_24h = AuditQuery(
            target_id="sales-kb-audit",
            start_time=yesterday,
            end_time=now,
            limit=100,
        )
        recent_events = await self.persistence.query_audit_logs(query_24h)
        
        print(f"✓ Found {len(recent_events)} events in last 24 hours")
        # Should find at least 3 from this test run (may include events from previous runs)
        assert len(recent_events) >= 3, f"Expected at least 3 recent events, got {len(recent_events)}"
        
        # Verify results include required fields
        for event in recent_events:
            print(f"\n  Event: {event.event_type.value}")
            print(f"    Source: {event.source_id}")
            print(f"    Target: {event.target_id}")
            print(f"    Outcome: {event.outcome.value}")
            print(f"    Timestamp: {event.timestamp}")
            
            assert event.timestamp is not None
            assert event.source_id is not None
            assert event.outcome is not None
            
            if event.masked_fields:
                print(f"    Masked fields: {event.masked_fields}")
            
            if event.request_metadata:
                print(f"    Metadata: {json.dumps(event.request_metadata, indent=6)}")

        # Step 4: Query only successful KB queries
        print("\nStep 4: Querying only successful KB queries...")
        
        query_success = AuditQuery(
            event_type=AuditEventType.QUERY,
            target_id="sales-kb-audit",
            outcome=AuditOutcome.SUCCESS,
            limit=100,
        )
        success_events = await self.persistence.query_audit_logs(query_success)
        
        print(f"✓ Found {len(success_events)} successful KB queries")
        assert len(success_events) >= 2, "Expected at least 2 successful queries"
        
        for event in success_events:
            assert event.outcome == AuditOutcome.SUCCESS
            assert event.event_type == AuditEventType.QUERY
            print(f"  ✓ {event.source_id} -> {event.target_id} at {event.timestamp}")

        # Step 5: Query denied accesses
        print("\nStep 5: Querying denied accesses...")
        
        query_denied = AuditQuery(
            outcome=AuditOutcome.DENIED,
            limit=100,
        )
        denied_events = await self.persistence.query_audit_logs(query_denied)
        
        print(f"✓ Found {len(denied_events)} denied accesses")
        assert len(denied_events) >= 1, "Expected at least 1 denied access"
        
        for event in denied_events:
            assert event.outcome == AuditOutcome.DENIED
            print(f"  ✓ Denied: {event.source_id} -> {event.target_id}")
            if event.policy_decision:
                print(f"    Policy: {event.policy_decision}")

        # Step 6: Query events from specific source
        print("\nStep 6: Querying events from marketing agent...")
        
        query_source = AuditQuery(
            source_id="marketing-agent-audit",
            limit=100,
        )
        source_events = await self.persistence.query_audit_logs(query_source)
        
        print(f"✓ Found {len(source_events)} events from marketing agent")
        assert len(source_events) >= 2, "Expected at least 2 events from marketing agent"
        
        for event in source_events:
            assert event.source_id == "marketing-agent-audit"
            print(f"  ✓ {event.event_type.value}: {event.outcome.value}")

        # Step 7: Get audit statistics
        print("\nStep 7: Getting audit statistics...")
        
        stats = await self.persistence.get_audit_stats()
        print(f"✓ Audit statistics:")
        print(f"  Outcome counts: {stats.get('outcome_counts', {})}")
        print(f"  Event type counts: {stats.get('event_type_counts', {})}")
        
        # Calculate total events from outcome counts
        total_events = sum(stats.get('outcome_counts', {}).values())
        print(f"  Total events: {total_events}")
        
        assert total_events >= 5, f"Expected at least 5 total events, got {total_events}"
        assert 'outcome_counts' in stats, "Expected outcome_counts in stats"
        assert 'event_type_counts' in stats, "Expected event_type_counts in stats"

        print("\n✅ SCENARIO 6.1 PASSED: Audit logs queryable with filtering")

    @pytest.mark.asyncio
    async def test_scenario_6_2_query_agent_registry(self):
        """
        Scenario 6.2: User Queries Agent Registry
        
        Given: User via MCP
        When: User queries: "List all agents with 'write' capability"
        Then:
          ✓ Direct query to agent metadata store
          ✓ Results include: agent_id, capabilities, health_status, last_active
        """
        print("\n=== TEST 6.2: Query Agent Registry ===")

        # Step 1: Register agents with different capabilities
        print("\nStep 1: Registering agents with various capabilities...")
        
        agents_config = [
            {
                "identity": "sales-agent-audit",
                "capabilities": ["query_kb", "write_kb"],
                "team": "sales",
            },
            {
                "identity": "marketing-agent-audit",
                "capabilities": ["query_kb"],
                "team": "marketing",
            },
            {
                "identity": "engineering-agent-audit",
                "capabilities": ["query_kb", "write_kb", "invoke_agent"],
                "team": "engineering",
            },
            {
                "identity": "finance-agent-audit",
                "capabilities": ["query_kb", "generate_report"],
                "team": "finance",
            },
        ]

        registered_agents = []
        for config in agents_config:
            agent_request = AgentRegistrationRequest(
                identity=config["identity"],
                version="1.0.0",
                capabilities=config["capabilities"],
                operations=["query", "subscribe"],
                health_endpoint=f"http://localhost:8001/{config['identity']}/health",
                metadata={"team": config["team"]},
            )
            agent_id = await self.agent_service.register_agent(agent_request)
            registered_agents.append(config["identity"])
            print(f"✓ Agent registered: {config['identity']} with capabilities {config['capabilities']}")

        # Wait for registrations to complete
        await asyncio.sleep(0.1)

        # Step 2: Query all agents
        print("\nStep 2: Querying all agents...")
        
        query_all = RegistryQuery(limit=100)
        all_agents = await self.persistence.list_agents(query_all)
        
        print(f"✓ Found {len(all_agents)} total agents")
        assert len(all_agents) >= 4, f"Expected at least 4 agents, got {len(all_agents)}"
        
        for agent in all_agents:
            if agent.identity in registered_agents:
                print(f"\n  Agent: {agent.identity}")
                print(f"    Version: {agent.version}")
                print(f"    Capabilities: {agent.capabilities}")
                print(f"    Status: {agent.status}")
                print(f"    Registered at: {agent.registered_at}")
                
                # Verify all required fields are present
                assert agent.identity is not None
                assert agent.capabilities is not None
                assert agent.status is not None
                assert agent.registered_at is not None

        # Step 3: Query agents with 'write_kb' capability
        print("\nStep 3: Querying agents with 'write_kb' capability...")
        
        query_write = RegistryQuery(
            capabilities=["write_kb"],
            limit=100,
        )
        write_agents = await self.persistence.list_agents(query_write)
        
        print(f"✓ Found {len(write_agents)} agents with 'write_kb' capability")
        assert len(write_agents) >= 2, f"Expected at least 2 agents with write capability, got {len(write_agents)}"
        
        for agent in write_agents:
            print(f"  ✓ {agent.identity}: {agent.capabilities}")
            assert "write_kb" in agent.capabilities

        # Step 4: Query agents with 'invoke_agent' capability
        print("\nStep 4: Querying agents with 'invoke_agent' capability...")
        
        query_invoke = RegistryQuery(
            capabilities=["invoke_agent"],
            limit=100,
        )
        invoke_agents = await self.persistence.list_agents(query_invoke)
        
        print(f"✓ Found {len(invoke_agents)} agents with 'invoke_agent' capability")
        assert len(invoke_agents) >= 1, "Expected at least 1 agent with invoke capability"
        
        for agent in invoke_agents:
            print(f"  ✓ {agent.identity}: {agent.capabilities}")
            assert "invoke_agent" in agent.capabilities

        # Step 5: Query specific agent by identity
        print("\nStep 5: Querying specific agent by identity...")
        
        specific_agent = await self.persistence.get_agent("engineering-agent-audit")
        
        assert specific_agent is not None, "Agent not found"
        print(f"✓ Retrieved agent: {specific_agent.identity}")
        print(f"  Capabilities: {specific_agent.capabilities}")
        print(f"  Status: {specific_agent.status}")
        print(f"  Health endpoint: {specific_agent.health_endpoint}")
        print(f"  Metadata: {specific_agent.metadata}")
        
        assert specific_agent.identity == "engineering-agent-audit"
        assert "write_kb" in specific_agent.capabilities
        assert "invoke_agent" in specific_agent.capabilities

        # Step 6: Update agent capabilities and verify
        print("\nStep 6: Updating agent capabilities...")
        
        new_capabilities = ["query_kb", "write_kb", "invoke_agent", "stream_data"]
        await self.persistence.update_agent_capabilities(
            "engineering-agent-audit", new_capabilities
        )
        
        updated_agent = await self.persistence.get_agent("engineering-agent-audit")
        assert updated_agent is not None
        print(f"✓ Updated capabilities: {updated_agent.capabilities}")
        assert "stream_data" in updated_agent.capabilities
        assert len(updated_agent.capabilities) == 4

        # Step 7: Query agents by status
        print("\nStep 7: Querying agents by health status...")
        
        # All newly registered agents should have 'offline' status by default
        query_offline = RegistryQuery(
            status="offline",
            limit=100,
        )
        offline_agents = await self.persistence.list_agents(query_offline)
        
        print(f"✓ Found {len(offline_agents)} offline agents")
        for agent in offline_agents:
            if agent.identity in registered_agents:
                print(f"  ✓ {agent.identity}: {agent.status}")

        # Step 8: Query KB registry
        print("\nStep 8: Querying KB registry...")
        
        # Register a test KB
        kb_request = KBRegistrationRequest(
            kb_id="engineering-kb-audit",
            kb_type="neo4j",
            endpoint="bolt://localhost:7687",
            operations=["cypher_query", "match_nodes"],
            kb_schema={
                "nodes": ["Feature", "Sprint", "Team"],
                "relationships": ["ASSIGNED_TO", "BELONGS_TO"],
            },
            metadata={"team": "engineering"},
        )
        kb_id = await self.kb_service.register_kb(kb_request)
        print(f"✓ KB registered: {kb_id}")

        # Query all KBs
        query_kbs = RegistryQuery(limit=100)
        all_kbs = await self.persistence.list_kbs(query_kbs)
        
        print(f"✓ Found {len(all_kbs)} total KBs")
        for kb in all_kbs:
            if kb.kb_id in ["sales-kb-audit", "engineering-kb-audit"]:
                print(f"\n  KB: {kb.kb_id}")
                print(f"    Type: {kb.kb_type}")
                print(f"    Operations: {kb.operations}")
                print(f"    Status: {kb.status}")
                
                assert kb.kb_id is not None
                assert kb.kb_type is not None
                assert kb.operations is not None

        # Query KBs by type
        print("\nStep 9: Querying KBs by type...")
        
        query_postgres = RegistryQuery(kb_type="postgres", limit=100)
        postgres_kbs = await self.persistence.list_kbs(query_postgres)
        
        print(f"✓ Found {len(postgres_kbs)} PostgreSQL KBs")
        for kb in postgres_kbs:
            print(f"  ✓ {kb.kb_id}: {kb.kb_type}")
            assert kb.kb_type == "postgres"

        print("\n✅ SCENARIO 6.2 PASSED: Agent and KB registries queryable with filtering")


if __name__ == "__main__":
    # Run tests directly
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))

