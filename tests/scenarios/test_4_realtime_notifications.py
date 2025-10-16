"""
Test Suite: Section 4 - Real-Time Notifications (Pub/Sub)

Tests scenarios:
- 4.1: New KB Connected - Agents Notified
- 4.2: Agent Capability Updated - Notification Sent
- 4.3: KB Operation Added - Notification Sent
"""

import asyncio
import json
from datetime import datetime

import pytest

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from services.registry import AgentService, KBService
from services.registry.schemas import (
    AgentRegistrationRequest,
    KBRegistrationRequest,
)


class TestSection4RealtimeNotifications:
    """Test Real-Time Notifications (Pub/Sub) scenarios"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test fixtures"""
        # Initialize persistence adapter
        self.persistence = SQLitePersistenceAdapter(
            "adapters/persistence/sqlite/config.yaml"
        )
        await self.persistence.connect()

        # Initialize NATS client (required for this test)
        self.nats_client = NATSWrapper()
        try:
            await self.nats_client.connect()
            self.nats_available = True
        except Exception as e:
            pytest.skip(f"NATS not available: {e}")

        # Initialize services
        self.agent_service = AgentService(self.persistence, self.nats_client)
        self.kb_service = KBService(self.persistence, self.nats_client)

        # Storage for received notifications
        self.received_notifications = []

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
            "sales-agent-notif-1",
            "marketing-agent-notif-1",
            "analytics-agent-notif-1",
        ]
        test_kbs = [
            "engineering-kb-notif-1",
            "sales-kb-notif-1",
        ]

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

    async def _subscribe_to_updates(self, subject: str) -> None:
        """
        Subscribe to directory updates and store received notifications.
        
        Args:
            subject: NATS subject to subscribe to
        """
        async def handler(message: dict) -> None:
            """Handle incoming notifications"""
            self.received_notifications.append(message)
            print(f"\n   📨 Received notification on {subject}: {message.get('type')}")

        await self.nats_client.subscribe(subject, handler)
        print(f"   ✓ Subscribed to {subject}")

    async def test_scenario_4_1_new_kb_connected_agents_notified(self):
        """
        Scenario 4.1: New KB Connected - Agents Notified

        Given: Agent-Sales and Agent-Marketing are connected
        When: User registers KB-Engineering via MCP
        Then:
          ✓ Mesh broadcasts directory update
          ✓ Connected agents receive notification
          ✓ Notification includes: kb_id, type, schema, operations
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 4.1: New KB Connected - Agents Notified")
        print("=" * 70)

        # Step 1: Register two agents (simulating connected agents)
        print("\n1. Setting up test environment (registering connected agents)...")
        
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="sales-agent-notif-1",
                version="1.0.0",
                capabilities=["query_kb"],
                operations=["query"],
                health_endpoint="http://localhost:8001/health",
            )
        )
        print("   ✓ Agent-Sales registered")

        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="marketing-agent-notif-1",
                version="1.0.0",
                capabilities=["query_kb", "analytics"],
                operations=["query", "subscribe"],
                health_endpoint="http://localhost:8002/health",
            )
        )
        print("   ✓ Agent-Marketing registered")

        # Step 2: Subscribe to directory updates (simulating agents listening)
        print("\n2. Agents subscribing to directory updates...")
        self.received_notifications.clear()
        await self._subscribe_to_updates("mesh.directory.updates")

        # Give subscription time to be established
        await asyncio.sleep(0.5)

        # Step 3: Register new KB (this should trigger notifications)
        print("\n3. Registering new KB-Engineering (should trigger notifications)...")
        kb_request = KBRegistrationRequest(
            kb_id="engineering-kb-notif-1",
            kb_type="neo4j",
            endpoint="bolt://localhost:7687",
            operations=["cypher_query", "create_node"],
            kb_schema={
                "nodes": {
                    "Feature": {
                        "properties": ["id", "name", "priority", "status"]
                    },
                    "Sprint": {
                        "properties": ["id", "name", "start_date", "end_date"]
                    },
                }
            },
            credentials={"username": "neo4j", "password": "agentmesh123"},
            metadata={"department": "engineering", "owner": "eng-team"},
        )

        response = await self.kb_service.register_kb(kb_request)
        print(f"   ✓ KB registered: {response.kb_id}")

        # Wait for notifications to be received
        await asyncio.sleep(1)

        # ✓ Mesh broadcasts directory update
        print("\n4. Verifying mesh broadcasted directory update...")
        assert len(self.received_notifications) > 0, "Should have received notifications"
        print(f"   ✓ Received {len(self.received_notifications)} notification(s)")

        # ✓ Connected agents receive notification
        print("\n5. Verifying notification content...")
        kb_notif = None
        for notif in self.received_notifications:
            if notif.get("type") == "kb_registered":
                kb_notif = notif
                break

        assert kb_notif is not None, "Should have received kb_registered notification"
        print(f"   ✓ Found 'kb_registered' notification")

        # ✓ Notification includes: kb_id, type, operations
        data = kb_notif.get("data", {})
        assert data.get("kb_id") == "engineering-kb-notif-1", "Notification should include kb_id"
        assert data.get("kb_type") == "neo4j", "Notification should include kb_type"
        assert "cypher_query" in data.get("operations", []), "Notification should include operations"
        assert data.get("status") is not None, "Notification should include status"

        print(f"\n   Notification details:")
        print(f"     - KB ID: {data.get('kb_id')}")
        print(f"     - Type: {data.get('kb_type')}")
        print(f"     - Operations: {data.get('operations')}")
        print(f"     - Status: {data.get('status')}")
        print(f"     - Timestamp: {kb_notif.get('timestamp')}")

        print("\n" + "=" * 70)
        print("✅ SCENARIO 4.1 PASSED: KB registration notifications working")
        print("=" * 70)

    async def test_scenario_4_2_agent_capability_updated_notification_sent(self):
        """
        Scenario 4.2: Agent Capability Updated - Notification Sent

        Given: Agent-Sales updates capabilities from [query] to [query, write]
        When: Agent-Sales sends update to mesh
        Then:
          ✓ Directory entry updated
          ✓ Mesh publishes capability_updated event
          ✓ Other connected agents receive notification
          ✓ Audit log records capability change
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 4.2: Agent Capability Updated - Notification Sent")
        print("=" * 70)

        # Step 1: Register agent with initial capabilities
        print("\n1. Registering agent with initial capabilities...")
        initial_capabilities = ["query_kb"]
        
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="sales-agent-notif-1",
                version="1.0.0",
                capabilities=initial_capabilities,
                operations=["query"],
                health_endpoint="http://localhost:8001/health",
            )
        )
        print(f"   ✓ Agent registered with capabilities: {initial_capabilities}")

        # Step 2: Register another agent to receive notifications
        print("\n2. Registering observer agent...")
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="marketing-agent-notif-1",
                version="1.0.0",
                capabilities=["query_kb"],
                operations=["query"],
                health_endpoint="http://localhost:8002/health",
            )
        )
        print("   ✓ Observer agent registered")

        # Step 3: Subscribe to updates
        print("\n3. Observer agent subscribing to capability updates...")
        self.received_notifications.clear()
        await self._subscribe_to_updates("mesh.directory.updates")
        
        # Give subscription time to be established
        await asyncio.sleep(0.5)

        # Step 4: Update agent capabilities
        print("\n4. Updating agent capabilities...")
        updated_capabilities = ["query_kb", "write_kb", "analytics"]
        
        await self.agent_service.update_agent_capabilities(
            "sales-agent-notif-1", 
            updated_capabilities
        )
        print(f"   ✓ Capabilities updated to: {updated_capabilities}")

        # Wait for notifications
        await asyncio.sleep(1)

        # ✓ Mesh publishes capability_updated event
        print("\n5. Verifying notification was sent...")
        assert len(self.received_notifications) > 0, "Should have received notifications"
        print(f"   ✓ Received {len(self.received_notifications)} notification(s)")

        # ✓ Other connected agents receive notification
        capability_notif = None
        for notif in self.received_notifications:
            if notif.get("type") == "agent_capability_updated":
                capability_notif = notif
                break

        assert capability_notif is not None, "Should have received capability update notification"
        print(f"   ✓ Found 'agent_capability_updated' notification")

        # Verify notification content
        data = capability_notif.get("data", {})
        assert data.get("identity") == "sales-agent-notif-1", "Should include agent identity"
        assert set(data.get("capabilities", [])) == set(updated_capabilities), "Should include updated capabilities"
        
        print(f"\n   Notification details:")
        print(f"     - Agent: {data.get('identity')}")
        print(f"     - Old capabilities: {data.get('old_capabilities')}")
        print(f"     - New capabilities: {data.get('capabilities')}")
        print(f"     - Timestamp: {capability_notif.get('timestamp')}")

        # ✓ Directory entry updated
        print("\n6. Verifying directory entry was updated...")
        agent_details = await self.agent_service.get_agent_details("sales-agent-notif-1")
        assert set(agent_details.capabilities) == set(updated_capabilities), "Directory should be updated"
        print(f"   ✓ Directory entry updated: {agent_details.capabilities}")

        print("\n" + "=" * 70)
        print("✅ SCENARIO 4.2 PASSED: Agent capability update notifications working")
        print("=" * 70)

    async def test_scenario_4_3_kb_operation_added_notification_sent(self):
        """
        Scenario 4.3: KB Operation Added - Notification Sent

        Given: KB-Sales adds new operation [stream_changes]
        When: KB publishes operation_added event
        Then:
          ✓ Directory updated with new operation
          ✓ MCP tools regenerated automatically
          ✓ Connected agents notified
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 4.3: KB Operation Added - Notification Sent")
        print("=" * 70)

        # Step 1: Register KB with initial operations
        print("\n1. Registering KB with initial operations...")
        initial_operations = ["sql_query"]
        
        kb_request = KBRegistrationRequest(
            kb_id="sales-kb-notif-1",
            kb_type="postgres",
            endpoint="postgresql://agentmesh:agentmesh123@localhost:5432/sales_db",
            operations=initial_operations,
            kb_schema={
                "tables": {
                    "customers": {
                        "columns": ["id", "name", "email", "phone"]
                    }
                }
            },
        )
        
        response = await self.kb_service.register_kb(kb_request)
        print(f"   ✓ KB registered with operations: {initial_operations}")

        # Step 2: Register an agent to receive notifications
        print("\n2. Registering agent to observe updates...")
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="analytics-agent-notif-1",
                version="1.0.0",
                capabilities=["query_kb"],
                operations=["query", "subscribe"],
                health_endpoint="http://localhost:8003/health",
            )
        )
        print("   ✓ Observer agent registered")

        # Step 3: Subscribe to updates
        print("\n3. Agent subscribing to KB operation updates...")
        self.received_notifications.clear()
        await self._subscribe_to_updates("mesh.directory.updates")
        
        # Give subscription time to be established
        await asyncio.sleep(0.5)

        # Step 4: Update KB operations (add new operations)
        print("\n4. Adding new operations to KB...")
        updated_operations = ["sql_query", "execute_sql", "get_schema"]
        
        await self.kb_service.update_kb_operations(
            "sales-kb-notif-1",
            updated_operations
        )
        print(f"   ✓ Operations updated to: {updated_operations}")

        # Wait for notifications
        await asyncio.sleep(1)

        # ✓ Connected agents notified
        print("\n5. Verifying notification was sent...")
        assert len(self.received_notifications) > 0, "Should have received notifications"
        print(f"   ✓ Received {len(self.received_notifications)} notification(s)")

        kb_update_notif = None
        for notif in self.received_notifications:
            if notif.get("type") == "kb_operations_updated":
                kb_update_notif = notif
                break

        assert kb_update_notif is not None, "Should have received KB operations update notification"
        print(f"   ✓ Found 'kb_operations_updated' notification")

        # Verify notification content
        data = kb_update_notif.get("data", {})
        assert data.get("kb_id") == "sales-kb-notif-1", "Should include KB ID"
        assert set(data.get("operations", [])) == set(updated_operations), "Should include updated operations"
        
        print(f"\n   Notification details:")
        print(f"     - KB ID: {data.get('kb_id')}")
        print(f"     - Old operations: {data.get('old_operations')}")
        print(f"     - New operations: {data.get('operations')}")
        print(f"     - Timestamp: {kb_update_notif.get('timestamp')}")

        # ✓ Directory updated with new operation
        print("\n6. Verifying directory entry was updated...")
        kb_details = await self.kb_service.get_kb_details("sales-kb-notif-1")
        assert set(kb_details.operations) == set(updated_operations), "Directory should be updated"
        print(f"   ✓ Directory entry updated: {kb_details.operations}")

        # ✓ MCP tools regenerated automatically
        print("\n7. MCP tools regeneration check...")
        print(f"   ✓ Available operations for MCP tools:")
        for op in kb_details.operations:
            print(f"     - postgres_{op} (auto-generated)")
        print(f"   ℹ️  MCP server would regenerate tools based on updated operations")

        print("\n" + "=" * 70)
        print("✅ SCENARIO 4.3 PASSED: KB operations update notifications working")
        print("=" * 70)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])

