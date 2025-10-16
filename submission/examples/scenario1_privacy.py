#!/usr/bin/env python3
"""
Scenario 1: Cross-Team Privacy-Preserving Query

This script demonstrates:
1. Registering a marketing agent
2. Registering a sales PostgreSQL KB
3. Uploading a privacy policy (marketing can query, but PII is masked)
4. Querying the KB with field-level masking applied
5. Viewing the audit trail

Prerequisites:
- Docker services running (docker-compose up -d)
- MCP server running (or run directly via Python imports)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.registry.agent_service import AgentService
from services.registry.kb_service import KBService
from services.registry.schemas import (
    AgentRegistrationRequest,
    KBRegistrationRequest,
)
from services.enforcement.enforcement_service import EnforcementService
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from adapters.messaging.nats_client import NATSWrapper
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter


async def main():
    print("=" * 70)
    print("Scenario 1: Cross-Team Privacy-Preserving Query")
    print("=" * 70)
    print()

    # Initialize services
    print("📦 Initializing services...")
    persistence = SQLitePersistenceAdapter("adapters/persistence/sqlite/config.yaml")
    await persistence.connect()
    
    agent_service = AgentService(persistence)
    kb_service = KBService(persistence)
    
    opa_client = OPAClient()
    nats_client = NATSWrapper()
    await nats_client.connect()
    
    # Initialize KB adapters
    postgres_adapter = PostgresAdapter("adapters/knowledge_base/postgres/config.yaml")
    await postgres_adapter.connect()
    
    neo4j_adapter = Neo4jAdapter("adapters/knowledge_base/neo4j/config.yaml")
    await neo4j_adapter.connect()
    
    kb_adapters = {
        "postgres": postgres_adapter,
        "neo4j": neo4j_adapter
    }
    
    # Note: Not passing nats_client to use direct adapter fallback for simplicity
    # In production, KB adapters would be listening on NATS subjects
    enforcement_service = EnforcementService(
        opa_client=opa_client,
        persistence=persistence,
        kb_adapters=kb_adapters,
        nats_client=None  # Use direct adapter fallback
    )
    
    print("✅ Services initialized\n")

    # Step 1: Register marketing agent
    print("Step 1: Register Marketing Agent")
    print("-" * 70)
    
    agent_req = AgentRegistrationRequest(
        identity="marketing-agent-2",
        version="1.0.0",
        capabilities=["query_kb", "analyze_data"],
        operations=["query", "subscribe"],
        health_endpoint="http://localhost:8002/health",
        metadata={"team": "marketing", "department": "customer_insights"}
    )
    
    try:
        agent_response = await agent_service.register_agent(agent_req)
        print(f"✅ Agent registered: {agent_response.agent_id}")
        print(f"   Status: {agent_response.status}")
        print()
    except Exception as e:
        print(f"⚠️  Agent may already exist: {e}")
        print()

    # Step 2: Register sales KB
    print("Step 2: Register Sales Knowledge Base (PostgreSQL)")
    print("-" * 70)
    
    kb_req = KBRegistrationRequest(
        kb_id="sales-kb-1",
        kb_type="postgres",
        endpoint="postgresql://admin:admin123@localhost:5432/agentmesh",
        operations=["sql_query"],
        metadata={
            "description": "Sales CRM database",
            "owner": "sales-team",
            "sensitive_fields": ["customer_email", "customer_phone", "ssn"]
        }
    )
    
    try:
        kb_response = await kb_service.register_kb(kb_req)
        print(f"✅ KB registered: {kb_response.kb_id}")
        print(f"   Status: {kb_response.status}")
        print()
    except Exception as e:
        print(f"⚠️  KB may already exist: {e}")
        print()

    # Step 3: Upload privacy policy
    print("Step 3: Upload Privacy Policy")
    print("-" * 70)
    
    policy_rego = """
package agentmesh

# Allow marketing to query sales KB
allow if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    input.action == "query"
}

# Define field masks for marketing (PII protection)
field_masks contains mask if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    mask := "customer_email"
}

field_masks contains mask if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    mask := "customer_phone"
}

# Deny marketing from writing
deny if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    input.action == "write"
}
"""
    
    try:
        policy_response = await opa_client.upload_policy(
            policy_id="agentmesh",
            policy_content=policy_rego
        )
        print(f"✅ Policy uploaded: {policy_response.get('result', {}).get('id', 'agentmesh')}")
        print()
    except Exception as e:
        print(f"⚠️  Policy may already exist: {e}")
        print()

    # Step 4: Query KB with governed access
    print("Step 4: Marketing Queries Sales KB (Governed)")
    print("-" * 70)
    
    query_params = {
        "requester_id": "marketing-agent-2",
        "kb_id": "sales-kb-1",
        "operation": "sql_query",
        "params": {
            "query": "SELECT customer_name, customer_email, customer_phone, objection, region FROM customer_feedback WHERE region='APAC' LIMIT 5",
            "params": None
        }
    }
    
    print(f"Query: {query_params['params']['query']}")
    print()
    
    try:
        response = await enforcement_service.enforce_kb_access(**query_params)
        
        print("📊 Query Response (Field-Level Masking Applied):")
        print("-" * 70)
        
        # Response is a dict with 'status', 'data' (SQLQueryOutput), 'masked_fields', 'policy'
        if response.get("status") == "success":
            print(f"✅ Query executed successfully")
            
            data = response.get("data")  # This is the SQLQueryOutput Pydantic model
            masked_fields = response.get("masked_fields", [])
            
            # Get rows from the Pydantic model
            rows = data.rows if hasattr(data, 'rows') else []
            
            print(f"   Rows returned: {len(rows)}")
            print(f"   Fields Masked: {masked_fields}")
            print()
            
            if rows:
                print("Sample rows:")
                for i, row in enumerate(rows[:3], 1):
                    print(f"\n   Row {i}:")
                    for key, value in row.items():
                        is_masked = key in masked_fields and value == "***"
                        masked = "🔒 MASKED" if is_masked else value
                        print(f"      {key}: {masked}")
            
            # Show masked fields
            if masked_fields:
                print(f"\n🔍 Fields Masked by Policy: {masked_fields}")
        else:
            print(f"❌ Query failed: {response.get('message')}")
    
    except Exception as e:
        print(f"❌ Error querying KB: {e}")
        import traceback
        traceback.print_exc()
    
    print()

    # Step 5: Query audit logs
    print("Step 5: View Audit Trail")
    print("-" * 70)
    
    from adapters.persistence.schemas import AuditQuery, AuditEventType
    
    audit_query = AuditQuery(
        source_id="marketing-agent-2",
        event_type=AuditEventType.QUERY,
        limit=5
    )
    
    try:
        audit_logs = await persistence.query_audit_logs(audit_query)
        
        print(f"📋 Recent audit logs for marketing-agent-2:")
        print()
        
        for log in audit_logs:
            print(f"   Event ID: {log.id}")
            print(f"   Type: {log.event_type}")
            print(f"   Target: {log.target_id}")
            print(f"   Outcome: {log.outcome}")
            print(f"   Masked Fields: {log.masked_fields or 'None'}")
            print(f"   Timestamp: {log.timestamp}")
            print()
    
    except Exception as e:
        print(f"❌ Error querying audit logs: {e}")
    
    # Cleanup
    await persistence.disconnect()
    await nats_client.disconnect()
    await postgres_adapter.disconnect()
    await neo4j_adapter.disconnect()
    
    print("=" * 70)
    print("✅ Scenario 1 Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("1. Marketing agent can query Sales KB (policy allows)")
    print("2. PII fields (email, phone) are automatically masked")
    print("3. All access is logged in audit trail")
    print("4. Mesh enforces governance without storing customer data")


if __name__ == "__main__":
    asyncio.run(main())

