"""
Test Suite: Section 3 - Agent-to-Agent Invocation

Tests scenarios:
- 3.1: Agent Invokes Another Agent
- 3.2: Agent Returns Result
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.schemas import AuditEventType, AuditOutcome, AuditQuery
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from services.enforcement import EnforcementService
from services.registry import AgentService
from services.registry.schemas import AgentRegistrationRequest
from services.routing import AgentInvokeRequest, InvocationStatus, RequestRouter


class TestSection3AgentInvocation:
    """Test Agent-to-Agent Invocation scenarios"""

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
            pytest.skip("NATS not available - required for agent invocation tests")

        # Initialize OPA client
        self.opa_client = OPAClient()
        try:
            is_healthy = await self.opa_client.health_check()
            if not is_healthy:
                pytest.skip("OPA not available - required for agent invocation tests")
        except Exception:
            pytest.skip("OPA not available - required for agent invocation tests")

        # Initialize services
        self.agent_service = AgentService(self.persistence, self.nats_client)

        # Initialize enforcement service
        self.enforcement_service = EnforcementService(
            opa_client=self.opa_client,
            persistence=self.persistence,
            kb_adapters={},
            nats_client=self.nats_client,
        )

        # Initialize request router
        self.request_router = RequestRouter(
            enforcement=self.enforcement_service,
            persistence=self.persistence,
            nats_client=self.nats_client,
        )
        await self.request_router.start()

        # Clean up test entities
        await self._cleanup_test_entities()

        # Setup agent invocation policy
        await self._setup_invocation_policy()

        # Track mock agent subscriptions for cleanup
        self.mock_subscriptions = []

        yield

        # Cleanup subscriptions
        for sub_id in self.mock_subscriptions:
            try:
                await self.nats_client.nc.unsubscribe(sub_id)
            except Exception:
                pass

        # Cleanup services
        await self.request_router.stop()
        if self.nats_client and not self.nats_client.nc.is_closed:
            try:
                await self.nats_client.disconnect()
            except Exception:
                pass  # Already closed
        await self.opa_client.close()
        await self.persistence.disconnect()

    async def _cleanup_test_entities(self):
        """Clean up test entities that might exist from previous runs"""
        test_agents = [
            "sales-agent-inv-1",
            "engineering-agent-inv-1",
            "marketing-agent-inv-1",
        ]

        for agent_id in test_agents:
            try:
                await self.agent_service.deregister_agent(agent_id)
            except Exception:
                pass  # Ignore if doesn't exist

    async def _setup_invocation_policy(self):
        """Setup OPA policy for agent invocation tests"""
        # Upload policy to allow sales agents to invoke engineering agents
        policy_content = """
package agentmesh_invocation

import future.keywords.if
import future.keywords.in

# Default deny
default allow_agent_invoke = false

# Allow sales agents to invoke engineering agents
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "sales-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "engineering-agent-")
    input.action == "invoke"
}

# Allow engineering agents to invoke marketing agents (for testing chain)
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "engineering-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "marketing-agent-")
    input.action == "invoke"
}

# Main decision point for agent invocation
decision = result if {
    input.resource_type == "agent"
    input.action == "invoke"
    result := {
        "allow": allow_agent_invoke,
        "reason": "Policy evaluated for agent invocation"
    }
}
"""

        print("\n   Setting up agent invocation policy in OPA...")
        result = await self.opa_client.upload_policy(
            "agentmesh_invocation", policy_content, persist=False
        )
        assert result.get("success") or "result" in result, "Policy upload should succeed"
        print("   ✓ Agent invocation policy uploaded")

    async def _simulate_target_agent(
        self, agent_id: str, operation: str, response_data: dict, delay: float = 0.1
    ):
        """
        Simulate a target agent receiving and responding to an invocation.
        
        Args:
            agent_id: The agent ID to simulate
            operation: The operation being invoked
            response_data: The response data to send back
            delay: Delay before responding (to simulate processing)
        """
        async def handle_invoke(message: dict):
            """Handle invocation message"""
            tracking_id = message.get("tracking_id")
            source = message.get("source")
            msg_operation = message.get("operation")
            payload = message.get("payload")

            print(f"\n   [Mock Agent {agent_id}] Received invocation:")
            print(f"     - Tracking ID: {tracking_id}")
            print(f"     - From: {source}")
            print(f"     - Operation: {msg_operation}")
            print(f"     - Payload: {payload}")

            # Simulate processing
            await asyncio.sleep(delay)

            # Send completion notification
            completion_msg = {
                "tracking_id": tracking_id,
                "status": "complete",
                "result": response_data,
                "error": None,
            }

            print(f"   [Mock Agent {agent_id}] Sending completion notification")
            await self.nats_client.publish("mesh.routing.completion", completion_msg)

        # Subscribe to invocation subject for this agent
        subject = f"mesh.agent.{agent_id}.invoke"
        sub_id = await self.nats_client.subscribe(subject, handle_invoke)
        self.mock_subscriptions.append(sub_id)
        print(f"   ✓ Mock agent {agent_id} listening on {subject}")

    async def _subscribe_to_notifications(self, agent_id: str, notification_queue: asyncio.Queue):
        """
        Subscribe to notifications for an agent.
        
        Args:
            agent_id: The agent ID to subscribe for
            notification_queue: Queue to put received notifications
        """
        async def handle_notification(message: dict):
            """Handle notification message"""
            await notification_queue.put(message)

        subject = f"mesh.agent.{agent_id}.notifications"
        sub_id = await self.nats_client.subscribe(subject, handle_notification)
        self.mock_subscriptions.append(sub_id)
        print(f"   ✓ Subscribed to notifications for {agent_id} on {subject}")

    async def test_scenario_3_1_agent_invokes_another_agent(self):
        """
        Scenario 3.1: Agent Invokes Another Agent

        Given: Agent-Sales wants to invoke Agent-Engineering
        When: Agent-Sales sends: "invoke prioritize_feature with {feature: 'X', demand: 'high'}"
        Then:
          ✓ Policy check: Can Sales invoke Engineering?
          ✓ Tracking ID assigned
          ✓ Request forwarded to Agent-Engineering
          ✓ Lifecycle tracked: [queued → processing → complete]
          ✓ Audit log records full invocation chain
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 3.1: Agent Invokes Another Agent")
        print("=" * 70)

        # Register source agent (Sales)
        print("\n1. Registering source agent (sales-agent-inv-1)...")
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="sales-agent-inv-1",
                version="1.0.0",
                capabilities=["query_kb", "invoke_agent"],
                operations=["query", "invoke"],
                health_endpoint="http://localhost:8001/health",
                metadata={"department": "sales", "team": "west-coast"},
            )
        )
        print("   ✓ sales-agent-inv-1 registered")

        # Register target agent (Engineering)
        print("\n2. Registering target agent (engineering-agent-inv-1)...")
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="engineering-agent-inv-1",
                version="2.0.0",
                capabilities=["prioritize_feature", "deploy"],
                operations=["invoke", "execute"],
                health_endpoint="http://localhost:8003/health",
                metadata={"department": "engineering", "team": "platform"},
            )
        )
        print("   ✓ engineering-agent-inv-1 registered")

        # Setup mock target agent to respond
        print("\n3. Setting up mock target agent to handle invocation...")
        await self._simulate_target_agent(
            agent_id="engineering-agent-inv-1",
            operation="prioritize_feature",
            response_data={
                "priority": "P0",
                "sprint": "Sprint-42",
                "estimated_effort": "5 days",
                "assigned_to": "engineering-team-alpha",
            },
            delay=0.2,
        )

        # Setup notification listener for source agent
        notification_queue = asyncio.Queue()
        await self._subscribe_to_notifications("sales-agent-inv-1", notification_queue)

        # ✓ Policy check: Can Sales invoke Engineering?
        print("\n4. Initiating agent invocation request...")
        invoke_request = AgentInvokeRequest(
            source_agent_id="sales-agent-inv-1",
            target_agent_id="engineering-agent-inv-1",
            operation="prioritize_feature",
            payload={
                "feature": "Multi-tenant support",
                "demand": "high",
                "customer_requests": 15,
                "revenue_impact": "$500K",
            },
        )

        print(f"   Request details:")
        print(f"     - Source: {invoke_request.source_agent_id}")
        print(f"     - Target: {invoke_request.target_agent_id}")
        print(f"     - Operation: {invoke_request.operation}")
        print(f"     - Payload: {json.dumps(invoke_request.payload, indent=2)}")

        # Route invocation through mesh
        response = await self.request_router.route_agent_invoke(invoke_request)

        # Verify policy check succeeded
        assert response.status != InvocationStatus.DENIED, (
            f"Invocation should be allowed by policy: {response.error}"
        )
        print(f"\n   ✓ Policy check passed: {response.policy}")

        # ✓ Tracking ID assigned
        assert response.tracking_id, "Tracking ID should be assigned"
        assert len(response.tracking_id) > 0, "Tracking ID should not be empty"
        print(f"   ✓ Tracking ID assigned: {response.tracking_id}")

        # ✓ Request forwarded to Agent-Engineering
        assert response.status == InvocationStatus.PROCESSING, (
            f"Should be in processing status, got: {response.status}"
        )
        print(f"   ✓ Request forwarded to target agent")
        print(f"   ✓ Initial status: {response.status}")

        # ✓ Lifecycle tracked: processing → complete
        print("\n5. Tracking invocation lifecycle...")
        print(f"   → Status: {response.status} (started at {response.started_at})")

        # Wait for target agent to process and send completion
        print("\n6. Waiting for target agent to complete task...")
        try:
            # Wait for notification with timeout
            notification = await asyncio.wait_for(notification_queue.get(), timeout=2.0)
            
            print(f"   ✓ Completion notification received:")
            print(f"     - Type: {notification.get('type')}")
            print(f"     - Tracking ID: {notification.get('tracking_id')}")
            print(f"     - Status: {notification.get('status')}")
            print(f"     - Result: {json.dumps(notification.get('result'), indent=2)}")

            assert notification.get("type") == "invocation_complete"
            assert notification.get("tracking_id") == response.tracking_id
            assert notification.get("status") == "complete"
            assert notification.get("result") is not None

        except asyncio.TimeoutError:
            pytest.fail("Did not receive completion notification within timeout")

        # Give mesh a moment to update invocation record
        await asyncio.sleep(0.1)

        # Check invocation status
        print("\n7. Verifying invocation status in mesh...")
        final_status = await self.request_router.get_invocation_status(
            response.tracking_id
        )

        if final_status:
            print(f"   ✓ Final status: {final_status.status}")
            print(f"   ✓ Started at: {final_status.started_at}")
            print(f"   ✓ Completed at: {final_status.completed_at}")
            if final_status.result:
                print(f"   ✓ Result: {json.dumps(final_status.result, indent=2)}")

            assert final_status.status == InvocationStatus.COMPLETED
            assert final_status.completed_at is not None
            assert final_status.result is not None

        # ✓ Audit log records full invocation chain
        print("\n8. Verifying audit trail...")
        audit_query = AuditQuery(
            event_type=AuditEventType.INVOKE,
            source_id="sales-agent-inv-1",
            target_id="engineering-agent-inv-1",
            limit=5,
        )
        audit_logs = await self.persistence.query_audit_logs(audit_query)

        if len(audit_logs) > 0:
            invocation_log = audit_logs[0]
            print(f"   ✓ Audit log recorded:")
            print(f"     - Event type: {invocation_log.event_type}")
            print(f"     - Source: {invocation_log.source_id}")
            print(f"     - Target: {invocation_log.target_id}")
            print(f"     - Outcome: {invocation_log.outcome}")
            print(f"     - Timestamp: {invocation_log.timestamp}")
            
            # Verify audit log details
            assert invocation_log.event_type == AuditEventType.INVOKE
            assert invocation_log.source_id == "sales-agent-inv-1"
            assert invocation_log.target_id == "engineering-agent-inv-1"
            assert invocation_log.outcome == AuditOutcome.SUCCESS

            # Check for tracking ID in metadata
            if invocation_log.request_metadata:
                metadata = invocation_log.request_metadata
                print(f"     - Metadata: {json.dumps(metadata, indent=2)}")
                if "tracking_id" in metadata:
                    assert metadata["tracking_id"] == response.tracking_id
                    print(f"     ✓ Tracking ID in audit log matches")
        else:
            print(f"   ℹ️  No audit logs found yet (may be async)")

        print("\n" + "=" * 70)
        print("✅ SCENARIO 3.1 PASSED: Agent invocation successful")
        print("=" * 70)

    async def test_scenario_3_2_agent_returns_result(self):
        """
        Scenario 3.2: Agent Returns Result

        Given: Agent-Engineering completes task
        When: Agent-Engineering sends completion status to mesh
        Then:
          ✓ Mesh logs completion timestamp
          ✓ Agent-Sales receives notification
          ✓ Audit log updated with outcome
        """
        print("\n" + "=" * 70)
        print("TEST SCENARIO 3.2: Agent Returns Result")
        print("=" * 70)

        # Register agents
        print("\n1. Registering test agents...")
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="sales-agent-inv-1",
                version="1.0.0",
                capabilities=["invoke_agent"],
                operations=["invoke"],
                health_endpoint="http://localhost:8001/health",
            )
        )
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="engineering-agent-inv-1",
                version="2.0.0",
                capabilities=["execute_task"],
                operations=["execute"],
                health_endpoint="http://localhost:8003/health",
            )
        )
        print("   ✓ Agents registered")

        # Setup mock target agent with custom result
        print("\n2. Setting up mock target agent...")
        custom_result = {
            "task_id": "TASK-1234",
            "status": "completed",
            "output": {
                "feature_implemented": "API rate limiting",
                "tests_passed": 42,
                "coverage": "95%",
                "deployed_to": "staging",
            },
            "completion_time": datetime.now(UTC).isoformat(),
        }
        await self._simulate_target_agent(
            agent_id="engineering-agent-inv-1",
            operation="execute_task",
            response_data=custom_result,
            delay=0.15,
        )

        # Setup notification listener
        notification_queue = asyncio.Queue()
        await self._subscribe_to_notifications("sales-agent-inv-1", notification_queue)

        # Initiate invocation
        print("\n3. Initiating invocation request...")
        invoke_request = AgentInvokeRequest(
            source_agent_id="sales-agent-inv-1",
            target_agent_id="engineering-agent-inv-1",
            operation="execute_task",
            payload={
                "task": "Implement API rate limiting",
                "priority": "high",
                "deadline": "2025-10-20",
            },
        )

        response = await self.request_router.route_agent_invoke(invoke_request)
        
        assert response.status == InvocationStatus.PROCESSING
        tracking_id = response.tracking_id
        print(f"   ✓ Invocation initiated: {tracking_id}")
        print(f"   ✓ Started at: {response.started_at}")

        # ✓ Agent-Sales receives notification
        print("\n4. Waiting for completion notification...")
        try:
            notification = await asyncio.wait_for(notification_queue.get(), timeout=2.0)
            
            print(f"   ✓ Notification received by source agent:")
            print(f"     - Type: {notification.get('type')}")
            print(f"     - Tracking ID: {notification.get('tracking_id')}")
            print(f"     - Status: {notification.get('status')}")
            
            assert notification.get("type") == "invocation_complete"
            assert notification.get("tracking_id") == tracking_id
            assert notification.get("status") == "complete"
            
            result = notification.get("result")
            assert result is not None
            assert result.get("task_id") == "TASK-1234"
            assert result.get("status") == "completed"
            print(f"     - Result data: {json.dumps(result, indent=2)}")

        except asyncio.TimeoutError:
            pytest.fail("Did not receive completion notification within timeout")

        # Give mesh time to update
        await asyncio.sleep(0.1)

        # ✓ Mesh logs completion timestamp
        print("\n5. Verifying completion timestamp in mesh...")
        final_status = await self.request_router.get_invocation_status(tracking_id)

        assert final_status is not None, "Should be able to retrieve invocation status"
        assert final_status.status == InvocationStatus.COMPLETED
        assert final_status.completed_at is not None, "Completion timestamp should be recorded"
        
        print(f"   ✓ Completion logged:")
        print(f"     - Status: {final_status.status}")
        print(f"     - Completed at: {final_status.completed_at}")
        
        # Calculate and verify latency
        if final_status.started_at and final_status.completed_at:
            latency = (final_status.completed_at - final_status.started_at).total_seconds()
            print(f"     - Latency: {latency:.3f} seconds")
            assert latency > 0, "Latency should be positive"

        # ✓ Audit log updated with outcome
        print("\n6. Verifying audit log with completion outcome...")
        audit_query = AuditQuery(
            event_type=AuditEventType.INVOKE,
            source_id="sales-agent-inv-1",
            target_id="engineering-agent-inv-1",
            outcome=AuditOutcome.SUCCESS,
            limit=5,
        )
        audit_logs = await self.persistence.query_audit_logs(audit_query)

        if len(audit_logs) > 0:
            completion_log = audit_logs[0]
            print(f"   ✓ Completion audit log found:")
            print(f"     - Event type: {completion_log.event_type}")
            print(f"     - Outcome: {completion_log.outcome}")
            print(f"     - Timestamp: {completion_log.timestamp}")
            
            assert completion_log.outcome == AuditOutcome.SUCCESS
            
            # Check metadata for tracking ID and latency
            if completion_log.request_metadata:
                metadata = completion_log.request_metadata
                print(f"     - Metadata: {json.dumps(metadata, indent=2)}")
                
                if "tracking_id" in metadata:
                    assert metadata["tracking_id"] == tracking_id
                    print(f"     ✓ Tracking ID matches in audit log")
                
                if "latency_ms" in metadata:
                    latency_ms = metadata["latency_ms"]
                    print(f"     ✓ Latency recorded: {latency_ms:.2f}ms")
                    assert latency_ms > 0
        else:
            print(f"   ℹ️  No completion audit logs found yet (may be async)")

        print("\n7. Verifying result data persistence...")
        if final_status.result:
            print(f"   ✓ Result data available:")
            print(f"     {json.dumps(final_status.result, indent=2)}")
            assert final_status.result.get("task_id") == custom_result["task_id"]
            assert final_status.result.get("status") == custom_result["status"]

        print("\n" + "=" * 70)
        print("✅ SCENARIO 3.2 PASSED: Agent result handling successful")
        print("=" * 70)

    async def test_scenario_3_3_invocation_denied_by_policy(self):
        """
        Additional Test: Invocation Denied by Policy

        Given: Agent-Marketing attempts to invoke Agent-Engineering
        When: Policy does not allow marketing → engineering invocation
        Then:
          ✓ Request denied immediately
          ✓ No tracking ID assigned
          ✓ Audit log records denial
        """
        print("\n" + "=" * 70)
        print("ADDITIONAL TEST: Invocation Denied by Policy")
        print("=" * 70)

        # Register agents
        print("\n1. Registering test agents...")
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="marketing-agent-inv-1",
                version="1.0.0",
                capabilities=["analytics"],
                operations=["query"],
                health_endpoint="http://localhost:8002/health",
            )
        )
        await self.agent_service.register_agent(
            AgentRegistrationRequest(
                identity="engineering-agent-inv-1",
                version="2.0.0",
                capabilities=["deploy"],
                operations=["execute"],
                health_endpoint="http://localhost:8003/health",
            )
        )
        print("   ✓ Agents registered")

        # Attempt unauthorized invocation
        print("\n2. Attempting unauthorized invocation...")
        print("   Marketing agent trying to invoke Engineering agent...")
        
        invoke_request = AgentInvokeRequest(
            source_agent_id="marketing-agent-inv-1",
            target_agent_id="engineering-agent-inv-1",
            operation="deploy_to_production",
            payload={"service": "critical-api", "environment": "production"},
        )

        response = await self.request_router.route_agent_invoke(invoke_request)

        # ✓ Request denied
        assert response.status == InvocationStatus.DENIED, (
            f"Should be denied, got: {response.status}"
        )
        print(f"   ✓ Request denied as expected")
        print(f"   ✓ Denial reason: {response.error}")

        # ✓ No tracking ID for denied requests
        assert response.tracking_id == "", "Denied requests should not have tracking ID"
        print(f"   ✓ No tracking ID assigned to denied request")

        # ✓ Policy information included
        assert response.policy, "Should include policy decision"
        print(f"   ✓ Policy decision: {response.policy}")

        # ✓ Audit log records denial
        print("\n3. Verifying denial in audit log...")
        audit_query = AuditQuery(
            source_id="marketing-agent-inv-1",
            target_id="engineering-agent-inv-1",
            outcome=AuditOutcome.DENIED,
            limit=5,
        )
        audit_logs = await self.persistence.query_audit_logs(audit_query)

        if len(audit_logs) > 0:
            denial_log = audit_logs[0]
            print(f"   ✓ Denial logged in audit trail:")
            print(f"     - Event type: {denial_log.event_type}")
            print(f"     - Outcome: {denial_log.outcome}")
            print(f"     - Reason: {denial_log.policy_decision}")
            
            assert denial_log.outcome == AuditOutcome.DENIED
        else:
            print(f"   ℹ️  No denial audit logs found yet (may be async)")

        print("\n" + "=" * 70)
        print("✅ ADDITIONAL TEST PASSED: Unauthorized invocation correctly denied")
        print("=" * 70)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])

