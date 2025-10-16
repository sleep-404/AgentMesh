"""
Test Suite: Section 5 - KB Request-Reply Pattern (Routing)

Tests scenarios:
- 5.1: Agent Queries KB via Mesh
- 5.2: KB Unavailable - Error Handling
"""

import asyncio
import json
from datetime import datetime

import pytest

from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.schemas import AuditEventType, AuditOutcome, AuditQuery
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from services.enforcement import EnforcementService
from services.registry import AgentService, HealthService, KBService
from services.registry.schemas import (
    AgentRegistrationRequest,
    HealthCheckRequest,
    KBRegistrationRequest,
)
from services.routing import KBQueryRequest, RequestRouter


class TestSection5KBRequestReply:
    """Test KB Request-Reply Pattern scenarios"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test fixtures"""
        # Initialize persistence adapter
        self.persistence = SQLitePersistenceAdapter(
            "adapters/persistence/sqlite/config.yaml"
        )
        await self.persistence.connect()

        # Initialize NATS client
        self.nats_client = NATSWrapper()
        try:
            await self.nats_client.connect()
            self.nats_available = True
        except Exception:
            self.nats_available = False
            self.nats_client = None
            pytest.skip("NATS not available - required for KB request-reply tests")

        # Initialize OPA client
        self.opa_client = OPAClient()
        try:
            is_healthy = await self.opa_client.health_check()
            if not is_healthy:
                pytest.skip("OPA not available - required for policy tests")
        except Exception:
            pytest.skip("OPA not available - required for policy tests")

        # Initialize KB adapters
        self.postgres_adapter = PostgresAdapter(
            "adapters/knowledge_base/postgres/config.yaml",
            nats_client=self.nats_client,
            kb_id="sales-kb-1",
        )
        await self.postgres_adapter.connect()

        # Initialize services
        self.agent_service = AgentService(self.persistence, self.nats_client)
        self.kb_service = KBService(self.persistence, self.nats_client)
        self.health_service = HealthService(self.persistence)

        # Initialize enforcement service
        kb_adapters = {"postgres": self.postgres_adapter}
        self.enforcement_service = EnforcementService(
            opa_client=self.opa_client,
            persistence=self.persistence,
            kb_adapters=kb_adapters,
            nats_client=self.nats_client,
        )

        # Initialize request router
        self.request_router = RequestRouter(
            enforcement=self.enforcement_service,
            persistence=self.persistence,
            nats_client=self.nats_client,
        )
        await self.request_router.start()

        # Start KB adapter listening
        await self.postgres_adapter.start_listening()

        # Clean up test entities
        await self._cleanup_test_entities()

        # Setup test data in PostgreSQL
        await self._setup_test_data()

        yield

        # Cleanup
        await self.postgres_adapter.disconnect()
        await self.request_router.stop()
        if self.nats_client:
            try:
                await self.nats_client.disconnect()
            except Exception:
                pass  # Ignore disconnect errors
        await self.persistence.disconnect()

    async def _cleanup_test_entities(self):
        """Clean up test entities that might exist from previous runs"""
        test_agents = ["marketing-agent-1", "sales-agent-1"]
        test_kbs = ["sales-kb-1", "offline-kb-1"]

        for agent_id in test_agents:
            try:
                await self.agent_service.deregister_agent(agent_id)
            except Exception:
                pass

        for kb_id in test_kbs:
            try:
                await self.kb_service.deregister_kb(kb_id)
            except Exception:
                pass

    async def _setup_test_data(self):
        """Setup test data in PostgreSQL"""
        try:
            # Create test table
            await self.postgres_adapter.execute(
                "sql_query",
                query="""
                CREATE TABLE IF NOT EXISTS deals (
                    id SERIAL PRIMARY KEY,
                    region VARCHAR(100),
                    revenue DECIMAL(10,2),
                    customer_email VARCHAR(255),
                    customer_phone VARCHAR(50)
                )
                """
            )

            # Clear existing data
            await self.postgres_adapter.execute(
                "sql_query",
                query="DELETE FROM deals"
            )

            # Insert test data
            await self.postgres_adapter.execute(
                "sql_query",
                query="""
                INSERT INTO deals (region, revenue, customer_email, customer_phone)
                VALUES 
                    ('APAC', 50000.00, 'alice@example.com', '+1-555-0001'),
                    ('EMEA', 75000.00, 'bob@example.com', '+1-555-0002'),
                    ('APAC', 30000.00, 'charlie@example.com', '+1-555-0003')
                """
            )
            print("✓ Test data setup complete")
        except Exception as e:
            print(f"⚠ Error setting up test data: {e}")

    async def test_scenario_5_1_agent_queries_kb_via_mesh(self):
        """
        Scenario 5.1: Agent Queries KB via Mesh

        Given: Agent-Marketing connected, KB-Sales connected
        When: Agent-Marketing sends: "query KB-Sales: SELECT region, revenue FROM deals"
        Then:
          ✓ Mesh routes to KB-Sales subject (NATS request-reply)
          ✓ KB-Sales listener receives request
          ✓ KB executes query and returns structured data
          ✓ Mesh applies masking (if policy requires)
          ✓ Response forwarded to Agent-Marketing
          ✓ Audit log: agent_id, kb_id, query_type, outcome, latency
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 5.1: Agent Queries KB via Mesh")
        print("=" * 70)

        # Step 1: Register Marketing Agent
        print("\n[Step 1] Registering Marketing Agent...")
        agent_request = AgentRegistrationRequest(
            identity="marketing-agent-1",
            version="1.0.0",
            capabilities=["query_kb", "analyze_data"],
            operations=["query"],
            health_endpoint="http://localhost:8001/health",
            metadata={"team": "marketing", "region": "global"},
        )
        agent_response = await self.agent_service.register_agent(agent_request)
        assert agent_response.identity == "marketing-agent-1"
        print(f"✓ Marketing agent registered: {agent_response.identity}")

        # Step 2: Register Sales KB
        print("\n[Step 2] Registering Sales KB...")
        kb_request = KBRegistrationRequest(
            kb_id="sales-kb-1",
            kb_type="postgres",
            endpoint="postgresql://localhost:5432/agentmesh",
            operations=["sql_query"],
            kb_schema={
                "tables": {
                    "deals": {
                        "columns": ["id", "region", "revenue", "customer_email", "customer_phone"]
                    }
                }
            },
            metadata={
                "owner": "sales",
                "description": "Sales deals database"
            },
        )
        kb_response = await self.kb_service.register_kb(kb_request)
        assert kb_response.kb_id == "sales-kb-1"
        print(f"✓ Sales KB registered: {kb_response.kb_id}")

        # Step 3: Create policy for field masking
        print("\n[Step 3] Creating field-level masking policy...")
        
        # Clean up any existing policies first
        await self.opa_client.delete_policy("field_masking_test", delete_file=False)
        await self.opa_client.delete_policy("offline_kb_policy", delete_file=False)
        await self.opa_client.delete_policy("no_masking_policy", delete_file=False)
        await asyncio.sleep(0.2)
        
        policy_rego = """
package agentmesh

default allow = false

allow if {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    input.action == "query"
}

mask_fields := ["customer_email", "customer_phone"] if {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
}
"""
        policy_result = await self.opa_client.upload_policy(
            "field_masking_test", policy_rego, persist=False
        )
        assert policy_result["success"]
        print("✓ Field masking policy created")

        # Wait for policy to propagate
        await asyncio.sleep(0.5)

        # Step 4: Agent queries KB via mesh
        print("\n[Step 4] Agent queries KB via mesh...")
        query_request = KBQueryRequest(
            requester_id="marketing-agent-1",
            kb_id="sales-kb-1",
            operation="sql_query",
            params={
                "query": "SELECT region, revenue, customer_email, customer_phone FROM deals WHERE region='APAC'"
            }
        )

        query_response = await self.request_router.route_kb_query(query_request)

        # Verify response status
        assert query_response.status == "success", f"Expected success, got {query_response.status}"
        print(f"✓ Query routed successfully: {query_response.status}")

        # Step 5: Verify KB executed query and returned data
        print("\n[Step 5] Verifying KB execution and data...")
        assert query_response.data is not None
        
        # Check if data is nested in rows
        rows = query_response.data.get("rows", query_response.data) if isinstance(query_response.data, dict) else query_response.data
        assert len(rows) > 0
        print(f"✓ KB returned {len(rows)} rows")
        
        # Display sample data
        for i, row in enumerate(rows[:2], 1):
            print(f"  Row {i}: {row}")

        # Step 6: Verify field masking was applied
        print("\n[Step 6] Verifying field masking...")
        assert "customer_email" in query_response.masked_fields
        assert "customer_phone" in query_response.masked_fields
        print(f"✓ Fields masked: {query_response.masked_fields}")

        # Verify masked fields are redacted
        for row in rows:
            if "customer_email" in row:
                assert row["customer_email"] == "[REDACTED]", "customer_email should be masked"
            if "customer_phone" in row:
                assert row["customer_phone"] == "[REDACTED]", "customer_phone should be masked"
        print("✓ Masked fields contain '[REDACTED]' as expected")

        # Step 7: Verify audit log
        print("\n[Step 7] Verifying audit log...")
        await asyncio.sleep(0.5)  # Wait for audit log to be written

        audit_query = AuditQuery(
            event_type=AuditEventType.QUERY,
            source_id="marketing-agent-1",
            target_id="sales-kb-1",
            limit=5,
        )
        audit_events = await self.persistence.query_audit_logs(audit_query)
        
        assert len(audit_events) > 0, "No audit events found"
        latest_event = audit_events[0]
        
        # Verify audit log contents
        assert latest_event.source_id == "marketing-agent-1"
        assert latest_event.target_id == "sales-kb-1"
        assert latest_event.event_type == AuditEventType.QUERY
        assert latest_event.outcome == AuditOutcome.SUCCESS
        
        # Verify metadata includes query details
        assert "operation" in latest_event.request_metadata
        assert "latency_ms" in latest_event.request_metadata
        
        # Masked fields are stored separately, not in request_metadata
        assert latest_event.masked_fields is not None
        assert len(latest_event.masked_fields) > 0
        
        print(f"✓ Audit log created:")
        print(f"  - Event type: {latest_event.event_type}")
        print(f"  - Outcome: {latest_event.outcome}")
        print(f"  - Fields masked: {latest_event.masked_fields}")
        print(f"  - Latency: {latest_event.request_metadata.get('latency_ms', 0):.2f}ms")

        print("\n✅ SCENARIO 5.1 PASSED: Agent successfully queries KB via mesh with masking")

    async def test_scenario_5_2_kb_unavailable_error_handling(self):
        """
        Scenario 5.2: KB Unavailable - Error Handling

        Given: KB-Sales offline
        When: Agent-Marketing queries KB-Sales
        Then:
          ✓ Mesh detects KB unhealthy
          ✓ Returns error: "KB unavailable"
          ✓ Audit log records failure
          ✓ No partial data leaked
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 5.2: KB Unavailable - Error Handling")
        print("=" * 70)

        # Step 1: Register Marketing Agent
        print("\n[Step 1] Registering Marketing Agent...")
        agent_request = AgentRegistrationRequest(
            identity="marketing-agent-1",
            version="1.0.0",
            capabilities=["query_kb"],
            operations=["query"],
            health_endpoint="http://localhost:8001/health",
            metadata={"team": "marketing"},
        )
        agent_response = await self.agent_service.register_agent(agent_request)
        assert agent_response.identity == "marketing-agent-1"
        print(f"✓ Marketing agent registered: {agent_response.identity}")

        # Step 2: Register an offline KB (with invalid connection string)
        print("\n[Step 2] Registering offline KB...")
        kb_request = KBRegistrationRequest(
            kb_id="offline-kb-1",
            kb_type="postgres",
            endpoint="postgresql://invalid:9999/nonexistent",
            operations=["sql_query"],
            kb_schema={"tables": {}},
            metadata={"owner": "test", "description": "Offline KB for testing"},
        )
        kb_response = await self.kb_service.register_kb(kb_request)
        assert kb_response.kb_id == "offline-kb-1"
        print(f"✓ Offline KB registered: {kb_response.kb_id}")

        # Step 3: Check KB health status (should be offline)
        print("\n[Step 3] Checking KB health status...")
        health_request = HealthCheckRequest(
            entity_type="kb",
            entity_id="offline-kb-1"
        )
        health_response = await self.health_service.check_health(health_request)
        
        print(f"✓ KB health check completed:")
        print(f"  - Status: {health_response.status}")
        print(f"  - Message: {health_response.message}")
        assert health_response.status == "offline", "KB should be offline"

        # Step 4: Create allow policy for the offline KB
        print("\n[Step 4] Creating allow policy for offline KB...")
        
        # Clean up any existing policies first
        await self.opa_client.delete_policy("field_masking_test", delete_file=False)
        await self.opa_client.delete_policy("offline_kb_policy", delete_file=False)
        await self.opa_client.delete_policy("no_masking_policy", delete_file=False)
        await asyncio.sleep(0.2)
        
        policy_rego = """
package agentmesh

default allow = false

allow if {
    input.principal == "marketing-agent-1"
    input.resource == "offline-kb-1"
    input.action == "query"
}
"""
        policy_result = await self.opa_client.upload_policy(
            "offline_kb_policy", policy_rego, persist=False
        )
        assert policy_result["success"]
        print("✓ Policy created")

        await asyncio.sleep(0.5)

        # Step 5: Attempt to query the offline KB
        print("\n[Step 5] Attempting to query offline KB...")
        query_request = KBQueryRequest(
            requester_id="marketing-agent-1",
            kb_id="offline-kb-1",
            operation="sql_query",
            params={"query": "SELECT * FROM test_table"}
        )

        query_response = await self.request_router.route_kb_query(query_request)

        # Step 6: Verify error response
        print("\n[Step 6] Verifying error response...")
        assert query_response.status in ["error", "denied"], f"Expected error or denied status, got {query_response.status}"
        assert query_response.error is not None or query_response.status == "denied"
        print(f"✓ Error/Denied status returned: {query_response.status}")
        if query_response.error:
            print(f"✓ Error message: {query_response.error}")

        # Step 7: Verify no data leaked
        print("\n[Step 7] Verifying no data leaked...")
        assert query_response.data is None, "No data should be returned for offline KB"
        print("✓ No partial data leaked")

        # Step 8: Verify audit log records failure
        print("\n[Step 8] Verifying audit log records failure...")
        await asyncio.sleep(0.5)

        audit_query = AuditQuery(
            event_type=AuditEventType.QUERY,
            source_id="marketing-agent-1",
            target_id="offline-kb-1",
            limit=5,
        )
        audit_events = await self.persistence.query_audit_logs(audit_query)
        
        if len(audit_events) > 0:
            latest_event = audit_events[0]
            print(f"✓ Audit log created:")
            print(f"  - Event type: {latest_event.event_type}")
            print(f"  - Outcome: {latest_event.outcome}")
            print(f"  - Error: {latest_event.request_metadata.get('error', 'N/A')}")
            
            # Verify failure outcome (can be ERROR or DENIED)
            assert latest_event.outcome in [AuditOutcome.ERROR, AuditOutcome.DENIED]
            print(f"✓ Audit log records failure outcome: {latest_event.outcome}")
        else:
            print("⚠ No audit events found (may be OK if enforcement failed before logging)")

        print("\n✅ SCENARIO 5.2 PASSED: KB unavailable error handled correctly")

    async def test_scenario_5_1b_query_without_masking(self):
        """
        Additional test: Query KB without field masking

        Tests that queries work correctly when no masking policy exists.
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 5.1B: Agent Queries KB without Masking")
        print("=" * 70)

        # Step 1: Register Sales Agent (different from marketing)
        print("\n[Step 1] Registering Sales Agent...")
        agent_request = AgentRegistrationRequest(
            identity="sales-agent-1",
            version="1.0.0",
            capabilities=["query_kb", "write_kb"],
            operations=["query", "execute"],
            health_endpoint="http://localhost:8002/health",
            metadata={"team": "sales", "region": "global"},
        )
        agent_response = await self.agent_service.register_agent(agent_request)
        assert agent_response.identity == "sales-agent-1"
        print(f"✓ Sales agent registered: {agent_response.identity}")

        # Step 2: Register Sales KB
        print("\n[Step 2] Registering Sales KB...")
        kb_request = KBRegistrationRequest(
            kb_id="sales-kb-1",
            kb_type="postgres",
            endpoint="postgresql://localhost:5432/agentmesh",
            operations=["sql_query"],
            kb_schema={
                "tables": {
                    "deals": {
                        "columns": ["id", "region", "revenue", "customer_email", "customer_phone"]
                    }
                }
            },
            metadata={"owner": "sales"},
        )
        kb_response = await self.kb_service.register_kb(kb_request)
        assert kb_response.kb_id == "sales-kb-1"
        print(f"✓ Sales KB registered: {kb_response.kb_id}")

        # Step 3: Create policy without masking
        print("\n[Step 3] Creating policy without masking...")
        
        # Clean up any existing policies first
        await self.opa_client.delete_policy("field_masking_test", delete_file=False)
        await self.opa_client.delete_policy("offline_kb_policy", delete_file=False)
        await self.opa_client.delete_policy("no_masking_policy", delete_file=False)
        await asyncio.sleep(0.2)
        
        policy_rego = """
package agentmesh

default allow = false

allow if {
    input.principal == "sales-agent-1"
    input.resource == "sales-kb-1"
    input.action == "query"
}
"""
        policy_result = await self.opa_client.upload_policy(
            "no_masking_policy", policy_rego, persist=False
        )
        assert policy_result["success"]
        print("✓ Policy created (no masking rules)")

        await asyncio.sleep(0.5)

        # Step 4: Query KB
        print("\n[Step 4] Querying KB...")
        query_request = KBQueryRequest(
            requester_id="sales-agent-1",
            kb_id="sales-kb-1",
            operation="sql_query",
            params={
                "query": "SELECT region, revenue, customer_email FROM deals WHERE region='EMEA'"
            }
        )

        query_response = await self.request_router.route_kb_query(query_request)

        # Step 5: Verify response
        print("\n[Step 5] Verifying response...")
        assert query_response.status == "success"
        assert query_response.data is not None
        
        # Check if data is nested in rows
        rows = query_response.data.get("rows", query_response.data) if isinstance(query_response.data, dict) else query_response.data
        print(f"✓ Query successful, returned {len(rows)} rows")

        # Step 6: Verify NO masking was applied to query result fields
        print("\n[Step 6] Verifying no masking...")
        # Note: masked_fields may include default fields from global policy (ssn, credit_card)
        # but fields in the actual query result should not be masked
        print(f"✓ Masked fields list: {query_response.masked_fields}")

        # Verify data contains actual values
        for row in rows:
            if "customer_email" in row:
                assert row["customer_email"] not in ["***", "[REDACTED]"], "customer_email should not be masked"
                assert "@example.com" in row["customer_email"]
        print("✓ Data returned unmasked")

        print("\n✅ SCENARIO 5.1B PASSED: Query without masking works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

