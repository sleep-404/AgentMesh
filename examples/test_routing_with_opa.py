"""
Example demonstrating the full governance flow with OPA.

This script:
1. Registers agents and KBs
2. Tests governed KB queries (with policy enforcement and masking)
3. Tests governed agent invocations (with policy checks)
4. Shows audit logs

Prerequisites:
- Run docker-compose up -d to start all services
- Ensure OPA, NATS, PostgreSQL, Neo4j are running
"""

import asyncio
import json

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.schemas import AgentRegistration, KBRegistration
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from services.enforcement import EnforcementService
from services.routing import KBQueryRequest, RequestRouter


async def main():
    print("=" * 80)
    print("AgentMesh Governance Demo with OPA")
    print("=" * 80)

    # Initialize adapters
    print("\n📦 Initializing adapters...")
    persistence = SQLitePersistenceAdapter("adapters/persistence/sqlite/config.yaml")
    await persistence.connect()

    postgres_adapter = PostgresAdapter("adapters/knowledge_base/postgres/config.yaml")
    await postgres_adapter.connect()

    neo4j_adapter = Neo4jAdapter("adapters/knowledge_base/neo4j/config.yaml")
    await neo4j_adapter.connect()

    nats_client = NATSWrapper()
    await nats_client.connect()

    opa_client = OPAClient()
    print("✅ All adapters connected")

    # Initialize services
    print("\n🔧 Initializing services...")
    kb_adapters = {"postgres": postgres_adapter, "neo4j": neo4j_adapter}

    enforcement = EnforcementService(
        opa_client=opa_client,
        persistence=persistence,
        kb_adapters=kb_adapters,
    )

    router = RequestRouter(
        enforcement=enforcement,
        persistence=persistence,
        nats_client=nats_client,
    )
    await router.start()
    print("✅ Services initialized")

    # Register agents
    print("\n👥 Registering agents...")
    agent_ids = {}
    for agent_name in ["sales-agent-1", "marketing-agent-2", "engineering-agent-3"]:
        agent_id = await persistence.register_agent(
            AgentRegistration(
                identity=agent_name,
                version="1.0.0",
                capabilities=["query_kb", "invoke_agent"],
                operations=["query", "invoke"],
                schemas={},
                health_endpoint=f"http://localhost:8000/{agent_name}/health",
                metadata={"team": agent_name.split("-")[0]},
            )
        )
        agent_ids[agent_name] = agent_id
        print(f"  ✓ Registered {agent_name} (ID: {agent_id})")

    # Register KBs
    print("\n💾 Registering knowledge bases...")
    kb_ids = {}
    kb_configs = [
        (
            "sales-kb-1",
            "postgres",
            "postgres://admin:admin123@localhost:5432/agentmesh",
        ),
        ("engineering-kb-1", "neo4j", "bolt://neo4j:admin123@localhost:7687"),
    ]

    for kb_name, kb_type, endpoint in kb_configs:
        kb_id = await persistence.register_kb(
            KBRegistration(
                kb_id=kb_name,
                kb_type=kb_type,
                endpoint=endpoint,
                operations=["query", "insert"],
                kb_schema={},
                metadata={"owner": kb_name.split("-")[0]},
            )
        )
        kb_ids[kb_name] = kb_id
        print(f"  ✓ Registered {kb_name} (Type: {kb_type})")

    # Test 1: Sales agent queries sales-kb-1 (SHOULD BE ALLOWED with minimal masking)
    print("\n" + "=" * 80)
    print("Test 1: Sales Agent → Sales KB (Allowed, masks SSN & credit card)")
    print("=" * 80)

    request = KBQueryRequest(
        requester_id="sales-agent-1",
        kb_id="sales-kb-1",
        operation="sql_query",
        params={"query": "SELECT * FROM customers LIMIT 1"},
    )

    response = await router.route_kb_query(request)
    print(f"\nResponse Status: {response.status}")
    print(f"Masked Fields: {response.masked_fields}")
    print(f"Policy: {response.policy}")
    if response.data:
        print(f"Data: {json.dumps(response.data, indent=2)}")
    if response.error:
        print(f"❌ Error: {response.error}")

    # Test 2: Marketing agent queries sales-kb-1 (SHOULD BE ALLOWED with more masking)
    print("\n" + "=" * 80)
    print(
        "Test 2: Marketing Agent → Sales KB (Allowed, masks email, phone, SSN, credit card)"
    )
    print("=" * 80)

    request = KBQueryRequest(
        requester_id="marketing-agent-2",
        kb_id="sales-kb-1",
        operation="sql_query",
        params={"query": "SELECT * FROM customers LIMIT 1"},
    )

    response = await router.route_kb_query(request)
    print(f"\nResponse Status: {response.status}")
    print(f"Masked Fields: {response.masked_fields}")
    print(f"Policy: {response.policy}")
    if response.data:
        print(f"Data: {json.dumps(response.data, indent=2)}")
    if response.error:
        print(f"❌ Error: {response.error}")

    # Test 3: Engineering agent queries sales-kb-1 (SHOULD BE DENIED)
    print("\n" + "=" * 80)
    print("Test 3: Engineering Agent → Sales KB (Should be DENIED)")
    print("=" * 80)

    request = KBQueryRequest(
        requester_id="engineering-agent-3",
        kb_id="sales-kb-1",
        operation="sql_query",
        params={"query": "SELECT * FROM customers LIMIT 1"},
    )

    response = await router.route_kb_query(request)
    print(f"\nResponse Status: {response.status}")
    print(f"Policy: {response.policy}")
    if response.error:
        print(f"❌ Error: {response.error}")

    # Test 4: Engineering agent queries engineering-kb-1 (SHOULD BE ALLOWED)
    print("\n" + "=" * 80)
    print("Test 4: Engineering Agent → Engineering KB (Allowed)")
    print("=" * 80)

    request = KBQueryRequest(
        requester_id="engineering-agent-3",
        kb_id="engineering-kb-1",
        operation="cypher_query",
        params={"query": "MATCH (n:Feature) RETURN n LIMIT 1"},
    )

    response = await router.route_kb_query(request)
    print(f"\nResponse Status: {response.status}")
    print(f"Masked Fields: {response.masked_fields}")
    print(f"Policy: {response.policy}")
    if response.data:
        print(f"Data: {json.dumps(response.data, indent=2)}")
    if response.error:
        print(f"❌ Error: {response.error}")

    # Test 5: Test OPA directly
    print("\n" + "=" * 80)
    print("Test 5: Direct OPA Policy Evaluation")
    print("=" * 80)

    decision = await opa_client.evaluate_policy(
        principal_type="agent",
        principal_id="sales-agent-1",
        resource_type="kb",
        resource_id="sales-kb-1",
        action="query",
    )
    print("\nOPA Decision for sales-agent-1 → sales-kb-1:")
    print(f"  Allow: {decision.get('allow')}")
    print(f"  Masking Rules: {decision.get('masking_rules')}")
    print(f"  Reason: {decision.get('reason')}")

    # Query audit logs
    print("\n" + "=" * 80)
    print("Audit Trail")
    print("=" * 80)

    from adapters.persistence.schemas import AuditQuery

    logs = await persistence.query_audit_logs(
        AuditQuery(limit=10, source_id="sales-agent-1")
    )
    print(f"\nFound {len(logs)} audit events for sales-agent-1:")
    for log in logs:
        print(
            f"  [{log.timestamp}] {log.event_type.value} → {log.target_id}: {log.outcome.value}"
        )
        if log.masked_fields:
            print(f"    Masked fields: {log.masked_fields}")

    # Cleanup
    print("\n🧹 Cleaning up...")
    await router.stop()
    await opa_client.close()
    await nats_client.disconnect()
    await postgres_adapter.disconnect()
    await neo4j_adapter.disconnect()
    await persistence.disconnect()
    print("✅ Cleanup complete")

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
