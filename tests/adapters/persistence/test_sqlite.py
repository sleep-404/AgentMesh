"""
Integration tests for SQLite persistence adapter.
"""
from datetime import UTC, datetime, timedelta

import pytest

from adapters.persistence.exceptions import DuplicateRecordError
from adapters.persistence.schemas import (
    AgentRegistration,
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditQuery,
    HealthStatus,
    KBRegistration,
    PolicyDefinition,
    PolicyRule,
    RegistryQuery,
)

# ============================================
# HEALTH CHECK TESTS
# ============================================


@pytest.mark.asyncio
async def test_health_check(sqlite_adapter):
    """Test adapter health check"""
    health = await sqlite_adapter.health_check()
    assert health["status"] == "healthy"


# ============================================
# AGENT REGISTRY TESTS
# ============================================


@pytest.mark.asyncio
async def test_register_and_get_agent(sqlite_adapter):
    """Test agent registration and retrieval"""
    # Register agent
    agent_id = await sqlite_adapter.register_agent(
        AgentRegistration(
            identity="test-agent-1",
            version="1.0.0",
            capabilities=["query_kb", "invoke_agent"],
            operations=["publish", "query"],
            schemas={"input": {"type": "object"}, "output": {"type": "array"}},
            health_endpoint="http://localhost:8001/health",
            metadata={"team": "engineering"},
        )
    )

    assert agent_id is not None

    # Retrieve agent
    agent = await sqlite_adapter.get_agent("test-agent-1")

    assert agent is not None
    assert agent.identity == "test-agent-1"
    assert agent.version == "1.0.0"
    assert agent.capabilities == ["query_kb", "invoke_agent"]
    assert agent.operations == ["publish", "query"]
    assert agent.status == HealthStatus.OFFLINE
    assert agent.metadata["team"] == "engineering"


@pytest.mark.asyncio
async def test_register_duplicate_agent_fails(sqlite_adapter):
    """Test that registering duplicate agent fails"""
    # Register first agent
    await sqlite_adapter.register_agent(
        AgentRegistration(
            identity="duplicate-agent",
            version="1.0.0",
            capabilities=["test"],
            operations=["query"],
            schemas={},
            health_endpoint="http://localhost:8001/health",
            metadata={},
        )
    )

    # Try to register same identity again
    with pytest.raises(DuplicateRecordError):
        await sqlite_adapter.register_agent(
            AgentRegistration(
                identity="duplicate-agent",
                version="2.0.0",
                capabilities=["test"],
                operations=["query"],
                schemas={},
                health_endpoint="http://localhost:8002/health",
                metadata={},
            )
        )


@pytest.mark.asyncio
async def test_update_agent_status(sqlite_adapter):
    """Test updating agent health status"""
    # Register agent
    await sqlite_adapter.register_agent(
        AgentRegistration(
            identity="test-agent-2",
            version="1.0.0",
            capabilities=["query_kb"],
            operations=["query"],
            schemas={},
            health_endpoint="http://localhost:8002/health",
            metadata={},
        )
    )

    # Update status
    await sqlite_adapter.update_agent_status("test-agent-2", HealthStatus.ACTIVE.value)

    # Verify
    agent = await sqlite_adapter.get_agent("test-agent-2")
    assert agent.status == HealthStatus.ACTIVE
    assert agent.last_heartbeat is not None


@pytest.mark.asyncio
async def test_list_agents_with_filters(sqlite_adapter):
    """Test querying agents with filters"""
    # Register multiple agents
    await sqlite_adapter.register_agent(
        AgentRegistration(
            identity="sales-agent-1",
            version="1.0.0",
            capabilities=["query_kb", "generate_report"],
            operations=["query"],
            schemas={},
            health_endpoint="http://localhost:8001/health",
            metadata={"team": "sales"},
        )
    )

    await sqlite_adapter.register_agent(
        AgentRegistration(
            identity="engineering-agent-1",
            version="1.0.0",
            capabilities=["query_kb", "code_review"],
            operations=["query", "invoke"],
            schemas={},
            health_endpoint="http://localhost:8002/health",
            metadata={"team": "engineering"},
        )
    )

    # Query by capability
    agents = await sqlite_adapter.list_agents(RegistryQuery(capabilities=["query_kb"]))
    assert len(agents) == 2

    # Query by specific identity
    agents = await sqlite_adapter.list_agents(RegistryQuery(identity="sales-agent-1"))
    assert len(agents) == 1
    assert agents[0].identity == "sales-agent-1"


@pytest.mark.asyncio
async def test_deregister_agent(sqlite_adapter):
    """Test agent deregistration"""
    # Register
    await sqlite_adapter.register_agent(
        AgentRegistration(
            identity="temp-agent",
            version="1.0.0",
            capabilities=["test"],
            operations=["query"],
            schemas={},
            health_endpoint="http://localhost:9000/health",
            metadata={},
        )
    )

    # Verify exists
    agent = await sqlite_adapter.get_agent("temp-agent")
    assert agent is not None

    # Deregister
    await sqlite_adapter.deregister_agent("temp-agent")

    # Verify removed
    agent = await sqlite_adapter.get_agent("temp-agent")
    assert agent is None


# ============================================
# KB REGISTRY TESTS
# ============================================


@pytest.mark.asyncio
async def test_register_and_get_kb(sqlite_adapter):
    """Test KB registration and retrieval"""
    # Register KB
    kb_id = await sqlite_adapter.register_kb(
        KBRegistration(
            kb_id="postgres-sales-kb",
            kb_type="postgres",
            endpoint="postgres://localhost:5432/sales",
            operations=["sql_query", "insert", "update"],
            kb_schema={"tables": ["customers", "deals", "activities"]},
            health_endpoint="http://localhost:5432/health",
            metadata={"owner": "sales-team", "region": "us-west"},
        )
    )

    assert kb_id is not None

    # Retrieve KB
    kb = await sqlite_adapter.get_kb("postgres-sales-kb")

    assert kb is not None
    assert kb.kb_id == "postgres-sales-kb"
    assert kb.kb_type == "postgres"
    assert kb.operations == ["sql_query", "insert", "update"]
    assert kb.kb_schema["tables"] == ["customers", "deals", "activities"]
    assert kb.metadata["owner"] == "sales-team"


@pytest.mark.asyncio
async def test_register_duplicate_kb_fails(sqlite_adapter):
    """Test that registering duplicate KB fails"""
    # Register first KB
    await sqlite_adapter.register_kb(
        KBRegistration(
            kb_id="duplicate-kb",
            kb_type="postgres",
            endpoint="postgres://localhost:5432/test",
            operations=["sql_query"],
            kb_schema={},
            metadata={},
        )
    )

    # Try to register same kb_id again
    with pytest.raises(DuplicateRecordError):
        await sqlite_adapter.register_kb(
            KBRegistration(
                kb_id="duplicate-kb",
                kb_type="neo4j",
                endpoint="bolt://localhost:7687",
                operations=["cypher_query"],
                kb_schema={},
                metadata={},
            )
        )


@pytest.mark.asyncio
async def test_update_kb_status(sqlite_adapter):
    """Test updating KB health status"""
    # Register KB
    await sqlite_adapter.register_kb(
        KBRegistration(
            kb_id="test-kb",
            kb_type="postgres",
            endpoint="postgres://localhost:5432/test",
            operations=["sql_query"],
            kb_schema={},
            metadata={},
        )
    )

    # Update status
    await sqlite_adapter.update_kb_status("test-kb", HealthStatus.ACTIVE.value)

    # Verify
    kb = await sqlite_adapter.get_kb("test-kb")
    assert kb.status == HealthStatus.ACTIVE
    assert kb.last_health_check is not None


@pytest.mark.asyncio
async def test_list_kbs_with_filters(sqlite_adapter):
    """Test querying KBs with filters"""
    # Register multiple KBs
    await sqlite_adapter.register_kb(
        KBRegistration(
            kb_id="postgres-kb-1",
            kb_type="postgres",
            endpoint="postgres://localhost:5432/db1",
            operations=["sql_query"],
            kb_schema={},
            metadata={},
        )
    )

    await sqlite_adapter.register_kb(
        KBRegistration(
            kb_id="neo4j-kb-1",
            kb_type="neo4j",
            endpoint="bolt://localhost:7687",
            operations=["cypher_query"],
            kb_schema={},
            metadata={},
        )
    )

    # Query by type
    kbs = await sqlite_adapter.list_kbs(RegistryQuery(kb_type="postgres"))
    assert len(kbs) == 1
    assert kbs[0].kb_type == "postgres"


@pytest.mark.asyncio
async def test_deregister_kb(sqlite_adapter):
    """Test KB deregistration"""
    # Register
    await sqlite_adapter.register_kb(
        KBRegistration(
            kb_id="temp-kb",
            kb_type="postgres",
            endpoint="postgres://localhost:5432/temp",
            operations=["sql_query"],
            kb_schema={},
            metadata={},
        )
    )

    # Verify exists
    kb = await sqlite_adapter.get_kb("temp-kb")
    assert kb is not None

    # Deregister
    await sqlite_adapter.deregister_kb("temp-kb")

    # Verify removed
    kb = await sqlite_adapter.get_kb("temp-kb")
    assert kb is None


# ============================================
# POLICY TESTS
# ============================================


@pytest.mark.asyncio
async def test_create_and_get_policy(sqlite_adapter):
    """Test policy creation and retrieval"""
    # Create policy
    policy_id = await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="sales-team-read-only",
            rules=[
                PolicyRule(
                    principal="sales-agent-*",
                    resource="sales-kb-1",
                    action="read",
                    effect="allow",
                    conditions={"time": "business_hours"},
                    masking_rules=["customer_email", "phone"],
                )
            ],
            precedence=100,
            active=True,
            metadata={"created_by": "admin"},
        )
    )

    assert policy_id is not None

    # Retrieve policy
    policy = await sqlite_adapter.get_policy("sales-team-read-only")

    assert policy is not None
    assert policy.policy_name == "sales-team-read-only"
    assert len(policy.rules) == 1
    assert policy.rules[0].principal == "sales-agent-*"
    assert policy.rules[0].effect == "allow"
    assert policy.rules[0].masking_rules == ["customer_email", "phone"]


@pytest.mark.asyncio
async def test_create_duplicate_policy_fails(sqlite_adapter):
    """Test that creating duplicate policy fails"""
    # Create first policy
    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="duplicate-policy",
            rules=[
                PolicyRule(principal="*", resource="*", action="read", effect="allow")
            ],
            precedence=100,
            active=True,
            metadata={},
        )
    )

    # Try to create same policy name again
    with pytest.raises(DuplicateRecordError):
        await sqlite_adapter.create_policy(
            PolicyDefinition(
                policy_name="duplicate-policy",
                rules=[
                    PolicyRule(
                        principal="*", resource="*", action="write", effect="deny"
                    )
                ],
                precedence=200,
                active=True,
                metadata={},
            )
        )


@pytest.mark.asyncio
async def test_list_policies(sqlite_adapter):
    """Test listing policies"""
    # Create multiple policies
    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="policy-1",
            rules=[
                PolicyRule(
                    principal="agent-1", resource="kb-1", action="read", effect="allow"
                )
            ],
            precedence=100,
            active=True,
            metadata={},
        )
    )

    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="policy-2",
            rules=[
                PolicyRule(
                    principal="agent-2", resource="kb-2", action="write", effect="deny"
                )
            ],
            precedence=200,
            active=False,
            metadata={},
        )
    )

    # List all policies
    all_policies = await sqlite_adapter.list_policies(active_only=False)
    assert len(all_policies) == 2

    # List only active
    active_policies = await sqlite_adapter.list_policies(active_only=True)
    assert len(active_policies) == 1
    assert active_policies[0].policy_name == "policy-1"


@pytest.mark.asyncio
async def test_update_policy(sqlite_adapter):
    """Test updating a policy"""
    # Create policy
    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="updatable-policy",
            rules=[
                PolicyRule(principal="*", resource="*", action="read", effect="allow")
            ],
            precedence=100,
            active=True,
            metadata={},
        )
    )

    # Update policy
    await sqlite_adapter.update_policy(
        "updatable-policy",
        PolicyDefinition(
            policy_name="updatable-policy",
            rules=[
                PolicyRule(principal="*", resource="*", action="read", effect="deny"),
                PolicyRule(
                    principal="admin-*", resource="*", action="*", effect="allow"
                ),
            ],
            precedence=50,
            active=True,
            metadata={"updated": "true"},
        ),
    )

    # Verify update
    policy = await sqlite_adapter.get_policy("updatable-policy")
    assert len(policy.rules) == 2
    assert policy.precedence == 50
    assert policy.metadata["updated"] == "true"


@pytest.mark.asyncio
async def test_delete_policy(sqlite_adapter):
    """Test deleting a policy"""
    # Create policy
    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="deletable-policy",
            rules=[
                PolicyRule(principal="*", resource="*", action="read", effect="allow")
            ],
            precedence=100,
            active=True,
            metadata={},
        )
    )

    # Verify exists
    policy = await sqlite_adapter.get_policy("deletable-policy")
    assert policy is not None

    # Delete
    await sqlite_adapter.delete_policy("deletable-policy")

    # Verify removed
    policy = await sqlite_adapter.get_policy("deletable-policy")
    assert policy is None


@pytest.mark.asyncio
async def test_evaluate_policy_exact_match(sqlite_adapter):
    """Test policy evaluation with exact match"""
    # Create policy
    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="test-policy",
            rules=[
                PolicyRule(
                    principal="test-agent",
                    resource="test-kb",
                    action="read",
                    effect="allow",
                    masking_rules=["email"],
                )
            ],
            precedence=100,
            active=True,
            metadata={},
        )
    )

    # Evaluate matching request
    result = await sqlite_adapter.evaluate_policy("test-agent", "test-kb", "read")
    assert result["effect"] == "allow"
    assert result["masking_rules"] == ["email"]
    assert result["matched_policy"] == "test-policy"

    # Evaluate non-matching request
    result = await sqlite_adapter.evaluate_policy("test-agent", "test-kb", "write")
    assert result["effect"] == "deny"
    assert result["matched_policy"] is None


@pytest.mark.asyncio
async def test_evaluate_policy_wildcard_match(sqlite_adapter):
    """Test policy evaluation with wildcard matching"""
    # Create policy with wildcards
    await sqlite_adapter.create_policy(
        PolicyDefinition(
            policy_name="wildcard-policy",
            rules=[
                PolicyRule(
                    principal="sales-*", resource="*-kb", action="*", effect="allow"
                )
            ],
            precedence=100,
            active=True,
            metadata={},
        )
    )

    # Evaluate matching requests
    result = await sqlite_adapter.evaluate_policy(
        "sales-agent-1", "customer-kb", "read"
    )
    assert result["effect"] == "allow"

    result = await sqlite_adapter.evaluate_policy(
        "sales-agent-2", "product-kb", "write"
    )
    assert result["effect"] == "allow"

    # Evaluate non-matching request
    result = await sqlite_adapter.evaluate_policy(
        "engineering-agent", "customer-kb", "read"
    )
    assert result["effect"] == "deny"


# ============================================
# AUDIT LOG TESTS
# ============================================


@pytest.mark.asyncio
async def test_log_and_query_audit_events(sqlite_adapter):
    """Test audit logging and querying"""
    # Log multiple events
    event1_id = await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="sales-agent-1",
            target_id="sales-kb-1",
            outcome=AuditOutcome.SUCCESS,
            request_metadata={"query_type": "sql", "table": "customers"},
            masked_fields=["email", "phone"],
        )
    )

    event2_id = await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.INVOKE,
            source_id="sales-agent-1",
            target_id="engineering-agent-1",
            outcome=AuditOutcome.SUCCESS,
            request_metadata={"action": "prioritize_feature"},
        )
    )

    event3_id = await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="marketing-agent-1",
            target_id="sales-kb-1",
            outcome=AuditOutcome.DENIED,
            policy_decision={
                "matched_policy": "cross-team-restriction",
                "reason": "insufficient_permissions",
            },
        )
    )

    assert all([event1_id, event2_id, event3_id])

    # Query all events
    all_events = await sqlite_adapter.query_audit_logs(AuditQuery(limit=100))
    assert len(all_events) == 3

    # Query by source
    agent1_events = await sqlite_adapter.query_audit_logs(
        AuditQuery(source_id="sales-agent-1")
    )
    assert len(agent1_events) == 2

    # Query by event type
    query_events = await sqlite_adapter.query_audit_logs(
        AuditQuery(event_type=AuditEventType.QUERY)
    )
    assert len(query_events) == 2

    # Query by outcome
    denied_events = await sqlite_adapter.query_audit_logs(
        AuditQuery(outcome=AuditOutcome.DENIED)
    )
    assert len(denied_events) == 1
    assert denied_events[0].source_id == "marketing-agent-1"


@pytest.mark.asyncio
async def test_audit_event_with_full_payload(sqlite_adapter):
    """Test logging heavy-weight audit events"""
    _ = await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="sales-agent-1",
            target_id="sales-kb-1",
            outcome=AuditOutcome.SUCCESS,
            request_metadata={"query_type": "sql"},
            policy_decision={"effect": "allow", "matched_policy": "sales-read"},
            masked_fields=["email", "phone"],
            # Heavy-weight fields
            full_request={"query": "SELECT * FROM customers WHERE region='west'"},
            full_response={"rows": 150, "columns": ["id", "name", "region"]},
            provenance_chain=["sales-agent-1", "sales-kb-1", "postgres-connection"],
        )
    )

    # Query and verify
    events = await sqlite_adapter.query_audit_logs(AuditQuery(limit=1))
    assert len(events) == 1

    event = events[0]
    assert event.full_request is not None
    assert event.full_request["query"] == "SELECT * FROM customers WHERE region='west'"
    assert event.full_response["rows"] == 150
    assert len(event.provenance_chain) == 3


@pytest.mark.asyncio
async def test_audit_query_with_time_filters(sqlite_adapter):
    """Test querying audit logs with time filters"""
    now = datetime.now(UTC)

    # Log event in the "past"
    await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="agent-1",
            target_id="kb-1",
            outcome=AuditOutcome.SUCCESS,
            timestamp=now - timedelta(hours=2),
        )
    )

    # Log event "now"
    await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="agent-1",
            target_id="kb-1",
            outcome=AuditOutcome.SUCCESS,
            timestamp=now,
        )
    )

    # Query events from last hour
    recent_events = await sqlite_adapter.query_audit_logs(
        AuditQuery(start_time=now - timedelta(hours=1))
    )
    assert len(recent_events) == 1

    # Query events from last 3 hours
    all_events = await sqlite_adapter.query_audit_logs(
        AuditQuery(start_time=now - timedelta(hours=3))
    )
    assert len(all_events) == 2


@pytest.mark.asyncio
async def test_get_audit_stats(sqlite_adapter):
    """Test getting audit statistics"""
    # Log various events
    await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="agent-1",
            target_id="kb-1",
            outcome=AuditOutcome.SUCCESS,
        )
    )

    await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.QUERY,
            source_id="agent-1",
            target_id="kb-1",
            outcome=AuditOutcome.DENIED,
        )
    )

    await sqlite_adapter.log_event(
        AuditEvent(
            event_type=AuditEventType.INVOKE,
            source_id="agent-2",
            target_id="agent-1",
            outcome=AuditOutcome.SUCCESS,
        )
    )

    # Get overall stats
    stats = await sqlite_adapter.get_audit_stats()
    assert stats["outcome_counts"]["success"] == 2
    assert stats["outcome_counts"]["denied"] == 1
    assert stats["event_type_counts"]["query"] == 2
    assert stats["event_type_counts"]["invoke"] == 1

    # Get stats for specific agent
    agent_stats = await sqlite_adapter.get_audit_stats(source_id="agent-1")
    assert agent_stats["outcome_counts"]["success"] == 1
    assert agent_stats["outcome_counts"]["denied"] == 1


# ============================================
# FILE-BASED DB TESTS
# ============================================


@pytest.mark.asyncio
async def test_file_based_persistence(file_based_sqlite_adapter):
    """Test that data persists to file"""
    adapter = file_based_sqlite_adapter

    # Register an agent
    await adapter.register_agent(
        AgentRegistration(
            identity="persistent-agent",
            version="1.0.0",
            capabilities=["test"],
            operations=["query"],
            schemas={},
            health_endpoint="http://localhost:8000/health",
            metadata={},
        )
    )

    # Verify it exists
    agent = await adapter.get_agent("persistent-agent")
    assert agent is not None
    assert agent.identity == "persistent-agent"
