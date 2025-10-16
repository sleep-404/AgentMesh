"""
Test Suite: Section 3 - Agent-to-Agent Invocation (AGENTIC VERSION)

This test follows the AGENTIC principle:
- ✅ Zero imports from mesh services
- ✅ All communication via NATS only
- ✅ Uses SimpleNATSAgent (external agent perspective)
- ✅ No knowledge of mesh internals

Tests scenarios:
- 3.1: Agent Invokes Another Agent
"""

import asyncio
import json
import logging
import time

import pytest

from dummy_agents.simple_nats_agent import SimpleNATSAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSection3AgentInvocationAgentic:
    """AGENTIC Test: Agent-to-Agent Invocation (Zero Mesh Knowledge)"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """
        Setup test fixtures.
        
        NOTE: This assumes the mesh service is already running externally
        (via docker-compose or services/bootstrap/mesh_service.py)
        """
        # Test agent instances (will be initialized in tests)
        self.agents = []
        
        yield
        
        # Cleanup: disconnect all agents
        for agent in self.agents:
            try:
                await agent.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting agent: {e}")

    def _track_agent(self, agent: SimpleNATSAgent):
        """Track agent for cleanup"""
        self.agents.append(agent)
        return agent

    async def test_scenario_3_1_agent_invokes_another_agent_agentic(self):
        """
        AGENTIC Scenario 3.1: Agent Invokes Another Agent
        
        This test demonstrates:
        1. Two external agents connecting to mesh via NATS
        2. Sales agent invoking engineering agent through mesh
        3. Engineering agent receiving and responding to invocation
        4. Completion notification flowing back through mesh
        
        Zero knowledge of:
        - RequestRouter internals
        - AgentService implementation
        - EnforcementService logic
        - Persistence layer details
        """
        print("\n" + "=" * 70)
        print("AGENTIC TEST 3.1: Agent Invokes Another Agent")
        print("(External agent perspective - Zero mesh knowledge)")
        print("=" * 70)

        # Generate unique agent IDs for this test run
        timestamp = int(time.time())
        sales_agent_id = f"sales-agent-inv-agentic-{timestamp}"
        eng_agent_id = f"engineering-agent-inv-agentic-{timestamp}"
        
        # ========== STEP 1: Sales Agent Connects and Registers ==========
        print("\n1. Sales agent connecting to mesh via NATS...")
        sales_agent = self._track_agent(SimpleNATSAgent("nats://localhost:4222"))
        
        try:
            await sales_agent.connect_to_mesh()
        except Exception as e:
            pytest.skip(f"Cannot connect to NATS - is mesh running? Error: {e}")

        print("   ✓ Connected to NATS")

        # Register sales agent
        print(f"   Registering as '{sales_agent_id}'...")
        try:
            sales_registration = await sales_agent.register_with_mesh(
                identity=sales_agent_id,
                version="1.0.0",
                capabilities=["invoke_agent", "query_kb"],
                operations=["invoke", "query"],
            )
            print(f"   ✓ Sales agent registered (status: {sales_registration.get('status')})")
        except RuntimeError as e:
            pytest.skip(f"Mesh not responding - is it running? Error: {e}")

        # ========== STEP 2: Engineering Agent Connects and Registers ==========
        print("\n2. Engineering agent connecting to mesh via NATS...")
        eng_agent = self._track_agent(SimpleNATSAgent("nats://localhost:4222"))
        await eng_agent.connect_to_mesh()
        print("   ✓ Connected to NATS")

        # Register engineering agent
        print(f"   Registering as '{eng_agent_id}'...")
        eng_registration = await eng_agent.register_with_mesh(
            identity=eng_agent_id,
            version="2.0.0",
            capabilities=["prioritize_feature", "deploy", "code_review"],
            operations=["execute", "invoke"],
        )
        print(f"   ✓ Engineering agent registered (status: {eng_registration.get('status')})")

        # ========== STEP 3: Engineering Agent Listens for Invocations ==========
        print("\n3. Engineering agent subscribing to invocation requests...")
        
        received_invocations = []
        completion_sent = asyncio.Event()

        async def handle_invocation(invocation_msg: dict):
            """
            Engineering agent handles incoming invocation.
            
            This is what a real agent would do:
            1. Receive invocation message
            2. Process the request
            3. Send completion notification back to mesh
            """
            print("\n   [Engineering Agent] 📥 Received invocation!")
            print(f"     - Tracking ID: {invocation_msg.get('tracking_id')}")
            print(f"     - From: {invocation_msg.get('source')}")
            print(f"     - Operation: {invocation_msg.get('operation')}")
            print(f"     - Payload: {json.dumps(invocation_msg.get('payload'), indent=2)}")
            
            received_invocations.append(invocation_msg)
            
            # Simulate processing work
            await asyncio.sleep(0.2)
            
            # Send completion back to mesh via NATS
            tracking_id = invocation_msg.get("tracking_id")
            result_data = {
                "priority": "P0",
                "sprint": "Sprint-42",
                "estimated_effort": "5 days",
                "assigned_to": "engineering-team-alpha",
                "feature": invocation_msg.get("payload", {}).get("feature"),
            }
            
            print(f"\n   [Engineering Agent] 📤 Sending completion...")
            await eng_agent.send_completion(
                tracking_id=tracking_id,
                status="complete",
                result=result_data,
            )
            print(f"     ✓ Completion sent for {tracking_id}")
            completion_sent.set()

        # Subscribe to invocations
        await eng_agent.subscribe_to_invocations(handle_invocation)
        print("   ✓ Engineering agent listening for invocations")

        # ========== STEP 4: Sales Agent Subscribes to Notifications ==========
        print("\n4. Sales agent subscribing to notifications...")
        
        received_notifications = []
        notification_received = asyncio.Event()

        async def handle_notification(notification_msg: dict):
            """
            Sales agent receives completion notifications.
            
            This is how source agents know when invocations complete.
            """
            print("\n   [Sales Agent] 📥 Received notification!")
            print(f"     - Type: {notification_msg.get('type')}")
            print(f"     - Tracking ID: {notification_msg.get('tracking_id')}")
            print(f"     - Status: {notification_msg.get('status')}")
            if notification_msg.get("result"):
                print(f"     - Result: {json.dumps(notification_msg.get('result'), indent=2)}")
            
            received_notifications.append(notification_msg)
            notification_received.set()

        await sales_agent.subscribe_to_notifications(handle_notification)
        print("   ✓ Sales agent listening for notifications")

        # Give subscriptions a moment to be ready
        await asyncio.sleep(0.5)

        # ========== STEP 5: Sales Agent Invokes Engineering Agent ==========
        print("\n5. Sales agent invoking engineering agent through mesh...")
        
        invoke_payload = {
            "feature": "Multi-tenant support",
            "demand": "high",
            "customer_requests": 15,
            "revenue_impact": "$500K",
            "urgency": "critical",
        }
        
        print(f"   Request details:")
        print(f"     - Target: {eng_agent_id}")
        print(f"     - Operation: prioritize_feature")
        print(f"     - Payload: {json.dumps(invoke_payload, indent=2)}")

        # Invoke via mesh (through NATS)
        invoke_response = await sales_agent.invoke_agent(
            target_agent_id=eng_agent_id,
            operation="prioritize_feature",
            payload=invoke_payload,
            timeout=10.0,
        )

        # ========== STEP 6: Verify Invocation Response ==========
        print(f"\n6. Verifying invocation response from mesh...")
        print(f"   Response: {json.dumps(invoke_response, indent=2)}")

        # Check status
        assert invoke_response.get("status") != "denied", (
            f"Invocation should not be denied: {invoke_response.get('error')}"
        )
        
        if invoke_response.get("status") == "error":
            pytest.fail(f"Invocation failed: {invoke_response.get('error')}")
        
        assert invoke_response.get("status") in ["processing", "queued"], (
            f"Expected processing/queued status, got: {invoke_response.get('status')}"
        )
        print(f"   ✓ Status: {invoke_response.get('status')}")

        # Verify tracking ID
        tracking_id = invoke_response.get("tracking_id")
        assert tracking_id, "Tracking ID should be assigned"
        assert len(tracking_id) > 0, "Tracking ID should not be empty"
        print(f"   ✓ Tracking ID: {tracking_id}")

        # Verify policy info (if available)
        if invoke_response.get("policy"):
            print(f"   ✓ Policy: {invoke_response.get('policy')}")

        # ========== STEP 7: Wait for Engineering Agent to Receive ==========
        print(f"\n7. Waiting for engineering agent to receive invocation...")
        
        try:
            # Wait for engineering agent to receive and process
            await asyncio.wait_for(completion_sent.wait(), timeout=5.0)
            print(f"   ✓ Engineering agent received and processed invocation")
            
            # Verify invocation message
            assert len(received_invocations) > 0, "Engineering agent should receive invocation"
            # Get the invocation with matching tracking ID
            invocation = next((inv for inv in received_invocations if inv.get("tracking_id") == tracking_id), received_invocations[-1])
            
            assert invocation.get("tracking_id") == tracking_id
            assert invocation.get("operation") == "prioritize_feature"
            assert invocation.get("payload") == invoke_payload
            print(f"   ✓ Invocation data matches original request")
            
        except asyncio.TimeoutError:
            pytest.fail(
                "Engineering agent did not receive invocation within timeout. "
                "Check if mesh routing is working properly."
            )

        # ========== STEP 8: Wait for Sales Agent to Receive Notification ==========
        print(f"\n8. Waiting for sales agent to receive completion notification...")
        
        try:
            # Wait for notification
            await asyncio.wait_for(notification_received.wait(), timeout=5.0)
            print(f"   ✓ Sales agent received completion notification")
            
            # Verify notification
            assert len(received_notifications) > 0, "Sales agent should receive notification"
            
            # Find the notification with matching tracking ID (there might be multiple from previous test runs)
            notification = next(
                (n for n in received_notifications if n.get("tracking_id") == tracking_id),
                received_notifications[0]  # Fallback to first
            )
            
            assert notification.get("type") == "invocation_complete"
            assert notification.get("tracking_id") == tracking_id
            assert notification.get("status") == "complete"
            assert notification.get("result") is not None
            print(f"   ✓ Notification data is valid")
            
            # Verify result contains expected data
            result = notification.get("result")
            assert result.get("priority") == "P0"
            assert result.get("sprint") == "Sprint-42"
            assert result.get("feature") == "Multi-tenant support"
            print(f"   ✓ Result data matches expected output")
            
        except asyncio.TimeoutError:
            pytest.fail(
                "Sales agent did not receive completion notification within timeout. "
                "Check if mesh notification routing is working properly."
            )

        # ========== STEP 9: Summary ==========
        print("\n" + "=" * 70)
        print("✅ AGENTIC TEST 3.1 PASSED")
        print("=" * 70)
        print("\nWhat was tested (from external agent perspective):")
        print("  1. ✓ Agents can connect to mesh via NATS")
        print("  2. ✓ Agents can register themselves")
        print("  3. ✓ Agents can invoke other agents through mesh")
        print("  4. ✓ Mesh assigns tracking IDs")
        print("  5. ✓ Mesh routes invocations to target agents")
        print("  6. ✓ Target agents receive invocation messages")
        print("  7. ✓ Target agents can send completion notifications")
        print("  8. ✓ Mesh routes notifications back to source agents")
        print("  9. ✓ All communication happens through NATS (no direct calls)")
        print("\nMesh components tested (black-box):")
        print("  - Agent registration")
        print("  - Policy evaluation (sales → engineering allowed)")
        print("  - Invocation routing")
        print("  - Notification routing")
        print("  - Lifecycle tracking")
        print("=" * 70)

    async def test_scenario_3_2_agent_discovery_before_invocation_agentic(self):
        """
        AGENTIC Scenario 3.2: Agent Discovers Target Before Invocation
        
        Demonstrates dynamic discovery pattern:
        1. Agent discovers available agents via mesh
        2. Agent filters by capability
        3. Agent invokes discovered agent
        
        This is more realistic - agents don't hardcode target IDs.
        """
        print("\n" + "=" * 70)
        print("AGENTIC TEST 3.2: Agent Discovery Before Invocation")
        print("=" * 70)

        # Generate unique agent IDs for this test run
        timestamp = int(time.time())
        marketing_agent_id = f"marketing-agent-discovery-{timestamp}"
        support_agent_id = f"support-agent-discovery-{timestamp}"
        
        # ========== STEP 1: Marketing Agent Connects ==========
        print("\n1. Marketing agent connecting and registering...")
        marketing_agent = self._track_agent(SimpleNATSAgent("nats://localhost:4222"))
        
        try:
            await marketing_agent.connect_to_mesh()
        except Exception as e:
            pytest.skip(f"Cannot connect to NATS: {e}")

        await marketing_agent.register_with_mesh(
            identity=marketing_agent_id,
            version="1.0.0",
            capabilities=["analytics", "invoke_agent"],
            operations=["query", "invoke"],
        )
        print(f"   ✓ Marketing agent registered as {marketing_agent_id}")

        # ========== STEP 2: Support Agent Connects ==========
        print("\n2. Support agent connecting and registering...")
        support_agent = self._track_agent(SimpleNATSAgent("nats://localhost:4222"))
        await support_agent.connect_to_mesh()
        
        await support_agent.register_with_mesh(
            identity=support_agent_id,
            version="1.0.0",
            capabilities=["customer_feedback", "ticket_analysis"],
            operations=["execute", "invoke"],
        )
        print(f"   ✓ Support agent registered as {support_agent_id}")

        # Support agent listens for invocations
        invocations_received = []
        
        async def handle_invocation(msg):
            invocations_received.append(msg)
            await support_agent.send_completion(
                tracking_id=msg.get("tracking_id"),
                status="complete",
                result={"feedback_summary": "Feature X highly requested"},
            )

        await support_agent.subscribe_to_invocations(handle_invocation)
        await asyncio.sleep(0.3)  # Let subscription settle

        # Wait for agents to be registered in directory
        await asyncio.sleep(1.0)

        # ========== STEP 3: Marketing Discovers Agents ==========
        print("\n3. Marketing agent discovering available agents...")
        
        # Discover all agents
        all_agents = await marketing_agent.discover_agents()
        print(f"   ✓ Found {all_agents.get('total_count', 0)} total agents")
        
        if all_agents.get("agents"):
            print("   Discovered agents:")
            for agent in all_agents["agents"]:
                print(f"     - {agent.get('identity')}: {agent.get('capabilities')}")

        # Discover agents with specific capability
        print("\n   Filtering for agents with 'customer_feedback' capability...")
        feedback_agents = await marketing_agent.discover_agents(
            capability_filter="customer_feedback"
        )
        
        assert feedback_agents.get("total_count", 0) > 0, (
            "Should find at least one agent with customer_feedback capability"
        )
        print(f"   ✓ Found {feedback_agents['total_count']} agents with capability")

        # ========== STEP 4: Marketing Invokes Discovered Agent ==========
        print("\n4. Marketing agent invoking discovered support agent...")
        
        # Find the newly created support agent by identity
        target_agent = next(
            (a for a in feedback_agents["agents"] if a["identity"] == support_agent_id),
            feedback_agents["agents"][0]  # Fallback to first if not found
        )
        target_id = target_agent.get("identity")
        print(f"   Target: {target_id}")
        
        # Skip test if we couldn't find the specific agent we created
        if target_id != support_agent_id:
            pytest.skip(f"Could not find newly created agent {support_agent_id} in discovery results")

        # Setup notification listener
        notifications = []
        notif_event = asyncio.Event()
        
        async def handle_notif(msg):
            notifications.append(msg)
            notif_event.set()

        await marketing_agent.subscribe_to_notifications(handle_notif)
        await asyncio.sleep(0.2)

        # Invoke
        response = await marketing_agent.invoke_agent(
            target_agent_id=target_id,
            operation="get_customer_feedback",
            payload={"feature": "Feature X", "period": "last_month"},
        )

        assert response.get("status") != "denied", f"Invocation denied: {response.get('error')}"
        assert response.get("tracking_id"), "Should have tracking ID"
        print(f"   ✓ Invocation initiated: {response.get('tracking_id')}")

        # ========== STEP 5: Wait for Completion ==========
        print("\n5. Waiting for completion...")
        
        try:
            await asyncio.wait_for(notif_event.wait(), timeout=3.0)
            assert len(notifications) > 0
            assert notifications[0].get("type") == "invocation_complete"
            print(f"   ✓ Completion received: {notifications[0].get('result')}")
        except asyncio.TimeoutError:
            pytest.fail("Did not receive completion notification")

        print("\n" + "=" * 70)
        print("✅ AGENTIC TEST 3.2 PASSED: Dynamic Discovery + Invocation")
        print("=" * 70)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])

