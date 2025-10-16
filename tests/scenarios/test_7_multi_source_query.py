"""
Test Suite: Section 7 - Multi-Source Query (User Synthesis)

Tests scenario:
- 7.1: User Queries Multiple KBs with real agent synthesis

This test uses:
- Real OpenAI agent (requires OPENAI_API_KEY)
- Real PostgreSQL KB (Sales commitments)
- Real Neo4j KB (Engineering roadmap)
- No mocking at any point
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any

import pytest
from dotenv import load_dotenv

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.schemas import AuditEventType, AuditOutcome, AuditQuery
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from dummy_agents.agents.openai_agent import OpenAIAgent
from services.enforcement import EnforcementService
from services.registry import AgentService, HealthService, KBService
from services.registry.schemas import (
    AgentRegistrationRequest,
    KBRegistrationRequest,
)
from services.routing import KBQueryRequest, RequestRouter


# Load environment variables
load_dotenv()


class TestSection7MultiSourceQuery:
    """Test Multi-Source Query scenarios with real agents and KBs"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test fixtures with real agents and KBs"""
        # Check for OpenAI API key
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            pytest.skip("OPENAI_API_KEY not found in environment")

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
            pytest.skip("NATS not available - required for multi-source query tests")

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
            kb_id="sales-kb",
        )
        await self.postgres_adapter.connect()

        self.neo4j_adapter = Neo4jAdapter(
            "adapters/knowledge_base/neo4j/config.yaml",
            nats_client=self.nats_client,
            kb_id="engineering-kb",
        )
        await self.neo4j_adapter.connect()

        # Initialize services
        self.agent_service = AgentService(self.persistence, self.nats_client)
        self.kb_service = KBService(self.persistence, self.nats_client)
        self.health_service = HealthService(self.persistence)

        # Initialize enforcement service
        kb_adapters = {
            "postgres": self.postgres_adapter,
            "neo4j": self.neo4j_adapter,
        }
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
        await self.neo4j_adapter.start_listening()

        # Clean up test entities
        await self._cleanup_test_entities()

        # Setup test data in both KBs
        await self._setup_test_data()

        yield

        # Cleanup
        await self.postgres_adapter.disconnect()
        await self.neo4j_adapter.disconnect()
        await self.request_router.stop()
        if self.nats_client:
            try:
                await self.nats_client.disconnect()
            except Exception:
                pass
        await self.persistence.disconnect()

    async def _cleanup_test_entities(self):
        """Clean up test entities that might exist from previous runs"""
        test_agents = ["product-manager-ai-1", "sales-kb-agent", "engineering-kb-agent"]
        test_kbs = ["sales-kb", "engineering-kb"]

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
        """Setup test data in both PostgreSQL and Neo4j"""
        print("\n[Setup] Creating test data in both KBs...")

        # Setup PostgreSQL Sales commitments data
        try:
            print("  - Setting up PostgreSQL Sales KB...")
            # Create commitments table
            await self.postgres_adapter.execute(
                "sql_query",
                query="""
                CREATE TABLE IF NOT EXISTS commitments (
                    id SERIAL PRIMARY KEY,
                    feature VARCHAR(200) NOT NULL,
                    timeline VARCHAR(50) NOT NULL,
                    customer VARCHAR(200) NOT NULL,
                    revenue DECIMAL(12,2),
                    sales_rep VARCHAR(100),
                    customer_email VARCHAR(255),
                    customer_phone VARCHAR(50),
                    commitment_date DATE DEFAULT CURRENT_DATE
                )
                """,
            )

            # Clear existing data
            await self.postgres_adapter.execute(
                "sql_query", query="DELETE FROM commitments"
            )

            # Insert test data - Feature Y committed for Q1
            await self.postgres_adapter.execute(
                "sql_query",
                query="""
                INSERT INTO commitments (feature, timeline, customer, revenue, sales_rep, customer_email, customer_phone)
                VALUES 
                    ('Feature Y', 'Q1 2025', 'Acme Corp', 150000.00, 'John Sales', 'john@acme.com', '+1-555-1001'),
                    ('Feature Y', 'Q1 2025', 'TechCo Inc', 200000.00, 'Sarah Sales', 'sarah@techco.com', '+1-555-1002'),
                    ('Feature Z', 'Q2 2025', 'DataCorp', 100000.00, 'Mike Sales', 'mike@datacorp.com', '+1-555-1003'),
                    ('Feature X', 'Q4 2024', 'GlobalTech', 250000.00, 'Lisa Sales', 'lisa@globaltech.com', '+1-555-1004')
                """,
            )
            print("    ✓ PostgreSQL test data created (Sales commitments)")
        except Exception as e:
            print(f"    ⚠ Error setting up PostgreSQL data: {e}")
            raise

        # Setup Neo4j Engineering roadmap data
        try:
            print("  - Setting up Neo4j Engineering KB...")
            
            # Clear existing test data
            await self.neo4j_adapter.execute(
                "cypher_query",
                query="""
                MATCH (f:Feature) WHERE f.name IN ['Feature X', 'Feature Y', 'Feature Z']
                DETACH DELETE f
                """,
            )

            # Create Feature Y node with Q3 feasibility (contradiction!)
            await self.neo4j_adapter.execute(
                "cypher_query",
                query="""
                CREATE (y:Feature {
                    name: 'Feature Y',
                    feasibility: 'Q3 2025',
                    status: 'planned',
                    complexity: 'high',
                    dependencies: ['Platform Upgrade', 'API v2'],
                    team: 'Backend Engineering',
                    tech_lead: 'Alice Engineer',
                    tech_lead_email: 'alice@company.internal'
                })
                """,
            )

            # Create Feature Z node with Q2 feasibility (matches sales)
            await self.neo4j_adapter.execute(
                "cypher_query",
                query="""
                CREATE (z:Feature {
                    name: 'Feature Z',
                    feasibility: 'Q2 2025',
                    status: 'in_progress',
                    complexity: 'medium',
                    dependencies: [],
                    team: 'Frontend Engineering',
                    tech_lead: 'Bob Engineer',
                    tech_lead_email: 'bob@company.internal'
                })
                """,
            )

            # Create Feature X node
            await self.neo4j_adapter.execute(
                "cypher_query",
                query="""
                CREATE (x:Feature {
                    name: 'Feature X',
                    feasibility: 'Q4 2024',
                    status: 'completed',
                    complexity: 'low',
                    dependencies: [],
                    team: 'Full Stack',
                    tech_lead: 'Charlie Engineer',
                    tech_lead_email: 'charlie@company.internal'
                })
                """,
            )

            print("    ✓ Neo4j test data created (Engineering roadmap)")
        except Exception as e:
            print(f"    ⚠ Error setting up Neo4j data: {e}")
            raise

        print("  ✓ All test data setup complete\n")

    async def test_scenario_7_1_user_queries_multiple_kbs(self):
        """
        Scenario 7.1: User Queries Multiple KBs with AI Agent Synthesis

        Given: User's AI agent connected via MCP
        When: AI agent queries both KB-Sales and KB-Engineering for Feature Y
        Then:
          ✓ Mesh routes both queries to respective KBs
          ✓ Policies applied independently per KB
          ✓ Both responses returned (masked per policy)
          ✓ AI agent synthesizes: "Contradiction detected: Sales Q1, Engineering Q3"
          ✓ Audit logs both accesses separately
        """
        print("\n" + "=" * 80)
        print("TEST SCENARIO 7.1: User Queries Multiple KBs with Real AI Agent")
        print("=" * 80)

        # Step 1: Register Product Manager AI Agent (simulates user's LLM)
        print("\n[Step 1] Registering Product Manager AI Agent...")
        agent_request = AgentRegistrationRequest(
            identity="product-manager-ai-1",
            version="1.0.0",
            capabilities=["query_kb", "synthesize_data", "detect_conflicts"],
            operations=["query"],
            health_endpoint="http://localhost:9001/health",
            metadata={
                "type": "openai",
                "model": "gpt-4o-mini",
                "role": "product_manager",
                "team": "product",
            },
        )
        agent_response = await self.agent_service.register_agent(agent_request)
        assert agent_response.identity == "product-manager-ai-1"
        print(f"✓ AI Agent registered: {agent_response.identity}")
        print(f"  - Type: OpenAI GPT-4o-mini")
        print(f"  - Role: Product Manager AI")

        # Step 2: Register Sales KB (PostgreSQL)
        print("\n[Step 2] Registering Sales KB (PostgreSQL)...")
        sales_kb_request = KBRegistrationRequest(
            kb_id="sales-kb",
            kb_type="postgres",
            endpoint="postgresql://localhost:5432/agentmesh",
            operations=["sql_query"],
            kb_schema={
                "tables": {
                    "commitments": {
                        "columns": [
                            "id",
                            "feature",
                            "timeline",
                            "customer",
                            "revenue",
                            "sales_rep",
                            "customer_email",
                            "customer_phone",
                            "commitment_date",
                        ]
                    }
                }
            },
            metadata={
                "owner": "sales",
                "description": "Sales feature commitments database",
                "contains_pii": True,
            },
        )
        sales_kb_response = await self.kb_service.register_kb(sales_kb_request)
        assert sales_kb_response.kb_id == "sales-kb"
        print(f"✓ Sales KB registered: {sales_kb_response.kb_id}")
        print(f"  - Type: PostgreSQL")
        print(f"  - Contains: Feature commitments with PII")

        # Step 3: Register Engineering KB (Neo4j)
        print("\n[Step 3] Registering Engineering KB (Neo4j)...")
        eng_kb_request = KBRegistrationRequest(
            kb_id="engineering-kb",
            kb_type="neo4j",
            endpoint="bolt://localhost:7687",
            operations=["cypher_query"],
            kb_schema={
                "nodes": {
                    "Feature": {
                        "properties": [
                            "name",
                            "feasibility",
                            "status",
                            "complexity",
                            "dependencies",
                            "team",
                            "tech_lead",
                            "tech_lead_email",
                        ]
                    }
                }
            },
            metadata={
                "owner": "engineering",
                "description": "Engineering feature roadmap graph",
                "contains_internal_data": True,
            },
        )
        eng_kb_response = await self.kb_service.register_kb(eng_kb_request)
        assert eng_kb_response.kb_id == "engineering-kb"
        print(f"✓ Engineering KB registered: {eng_kb_response.kb_id}")
        print(f"  - Type: Neo4j")
        print(f"  - Contains: Feature roadmap and feasibility")

        # Step 4: Create field-level policies for both KBs
        print("\n[Step 4] Creating field-level masking policies...")

        # Clean up ALL existing policies to avoid conflicts
        existing_policies = ["multi_source_policy", "field_masking_test", "offline_kb_policy", "no_masking_policy"]
        for policy in existing_policies:
            try:
                await self.opa_client.delete_policy(policy, delete_file=False)
            except Exception:
                pass
        await asyncio.sleep(0.5)

        # Create unified policy for both KBs with different masking rules
        policy_rego = """
package agentmesh

import future.keywords.if

# Allow product manager AI to query Sales KB (PostgreSQL)
allow_kb_access if {
    input.principal_type == "agent"
    input.principal_id == "product-manager-ai-1"
    input.resource_type == "kb"
    input.resource_id == "sales-kb"
    input.action == "sql_query"
}

# Allow product manager AI to query Engineering KB (Neo4j)
allow_kb_access if {
    input.principal_type == "agent"
    input.principal_id == "product-manager-ai-1"
    input.resource_type == "kb"
    input.resource_id == "engineering-kb"
    input.action == "cypher_query"
}

# Mask PII fields in Sales KB (customer contact info)
masking_rules = ["customer_email", "customer_phone"] if {
    input.principal_type == "agent"
    input.principal_id == "product-manager-ai-1"
    input.resource_type == "kb"
    input.resource_id == "sales-kb"
    input.action == "sql_query"
}

# Mask internal fields in Engineering KB (tech lead email)
masking_rules = ["tech_lead_email"] if {
    input.principal_type == "agent"
    input.principal_id == "product-manager-ai-1"
    input.resource_type == "kb"
    input.resource_id == "engineering-kb"
    input.action == "cypher_query"
}

# Main decision point for KB access
decision = result if {
    input.resource_type == "kb"
    result := {
        "allow": allow_kb_access,
        "masking_rules": masking_rules,
        "reason": reason_message
    }
}

# Reason for decision
reason_message = "Policy allows KB access" if {
    allow_kb_access
} else = "No policy grants KB access"
"""
        policy_result = await self.opa_client.upload_policy(
            "multi_source_policy", policy_rego, persist=False
        )
        assert policy_result["success"]
        print("✓ Multi-source policies created:")
        print("  - Sales KB: Mask customer_email, customer_phone")
        print("  - Engineering KB: Mask tech_lead_email")

        # Wait for policy to propagate
        await asyncio.sleep(0.5)

        # Step 5: Query Sales KB for Feature Y commitments
        print("\n[Step 5] Querying Sales KB for Feature Y timeline...")
        sales_query_request = KBQueryRequest(
            requester_id="product-manager-ai-1",
            kb_id="sales-kb",
            operation="sql_query",
            params={
                "query": "SELECT feature, timeline, customer, revenue, customer_email, customer_phone FROM commitments WHERE feature='Feature Y'"
            },
        )

        sales_query_response = await self.request_router.route_kb_query(
            sales_query_request
        )

        # Verify Sales KB response
        assert (
            sales_query_response.status == "success"
        ), f"Sales query failed: {sales_query_response.error}"
        print(f"✓ Sales KB query successful")

        sales_rows = (
            sales_query_response.data.get("rows", sales_query_response.data)
            if isinstance(sales_query_response.data, dict)
            else sales_query_response.data
        )
        assert len(sales_rows) > 0, "No sales commitments found for Feature Y"
        print(f"  - Found {len(sales_rows)} commitment(s)")
        
        # Extract timeline from sales
        sales_timeline = sales_rows[0].get("timeline", "Unknown")
        print(f"  - Sales Timeline: {sales_timeline}")
        print(f"  - Masked fields: {sales_query_response.masked_fields}")

        # Verify masking was applied
        assert "customer_email" in sales_query_response.masked_fields
        assert "customer_phone" in sales_query_response.masked_fields
        for row in sales_rows:
            if "customer_email" in row:
                assert row["customer_email"] == "[REDACTED]"
            if "customer_phone" in row:
                assert row["customer_phone"] == "[REDACTED]"
        print("  ✓ PII fields masked correctly")

        # Step 6: Query Engineering KB for Feature Y feasibility
        print("\n[Step 6] Querying Engineering KB for Feature Y feasibility...")
        eng_query_request = KBQueryRequest(
            requester_id="product-manager-ai-1",
            kb_id="engineering-kb",
            operation="cypher_query",
            params={
                "query": "MATCH (f:Feature {name: 'Feature Y'}) RETURN f.name as feature, f.feasibility as feasibility, f.status as status, f.complexity as complexity, f.tech_lead as tech_lead, f.tech_lead_email as tech_lead_email"
            },
        )

        eng_query_response = await self.request_router.route_kb_query(eng_query_request)

        # Verify Engineering KB response
        assert (
            eng_query_response.status == "success"
        ), f"Engineering query failed: {eng_query_response.error}"
        print(f"✓ Engineering KB query successful")

        # Neo4j returns data in a different format with 'records' key
        if isinstance(eng_query_response.data, dict) and 'records' in eng_query_response.data:
            eng_rows = eng_query_response.data['records']
        else:
            eng_rows = (
                eng_query_response.data.get("rows", eng_query_response.data)
                if isinstance(eng_query_response.data, dict)
                else eng_query_response.data
            )
        
        assert len(eng_rows) > 0, "No engineering roadmap found for Feature Y"
        print(f"  - Found {len(eng_rows)} roadmap item(s)")
        
        # Extract feasibility from engineering
        eng_feasibility = eng_rows[0].get("feasibility", "Unknown") if eng_rows else "Unknown"
        print(f"  - Engineering Feasibility: {eng_feasibility}")
        print(f"  - Masked fields: {eng_query_response.masked_fields}")

        # Verify masking was applied
        assert "tech_lead_email" in eng_query_response.masked_fields
        for row in eng_rows:
            if "tech_lead_email" in row:
                assert row["tech_lead_email"] == "[REDACTED]"
        print("  ✓ Internal fields masked correctly")

        # Step 7: Use Real OpenAI Agent to synthesize results
        print("\n[Step 7] Using Real OpenAI Agent to synthesize results...")
        print("  - Model: GPT-4o-mini")
        print("  - Task: Detect conflicts between Sales and Engineering timelines")

        # Prepare synthesis task for OpenAI agent
        synthesis_task = f"""
You are a Product Manager AI analyzing feature delivery data.

SALES COMMITMENTS for Feature Y:
{json.dumps(sales_rows, indent=2)}
Sales Timeline: {sales_timeline}

ENGINEERING ROADMAP for Feature Y:
{json.dumps(eng_rows, indent=2)}
Engineering Feasibility: {eng_feasibility}

TASK:
1. Compare the Sales timeline with Engineering feasibility
2. Identify any contradictions or misalignments
3. Provide a concise analysis (2-3 sentences)
4. If there's a contradiction, clearly state "CONTRADICTION DETECTED"

Format: Start with "CONTRADICTION DETECTED" if timelines don't match, otherwise "ALIGNED".
"""

        # Execute real OpenAI agent
        try:
            openai_agent = OpenAIAgent(
                task=synthesis_task,
                api_key=self.openai_api_key,
                model="gpt-4o-mini",
            )
            agent_result = openai_agent.execute()

            assert agent_result["status"] == "completed"
            synthesis_result = agent_result["result"]

            print(f"\n  ✓ AI Agent Analysis Complete:")
            print(f"  {'-' * 70}")
            print(f"  {synthesis_result}")
            print(f"  {'-' * 70}")

            # Verify the agent detected the contradiction
            assert (
                "CONTRADICTION" in synthesis_result.upper()
                or "CONFLICT" in synthesis_result.upper()
                or "MISMATCH" in synthesis_result.upper()
            ), "AI should detect the timeline contradiction"
            print("\n  ✓ AI successfully detected timeline contradiction!")

        except Exception as e:
            pytest.fail(f"OpenAI Agent execution failed: {e}")

        # Step 8: Verify audit logs for both queries
        print("\n[Step 8] Verifying audit logs for both KB queries...")
        await asyncio.sleep(0.5)

        # Check Sales KB audit log
        sales_audit_query = AuditQuery(
            event_type=AuditEventType.QUERY,
            source_id="product-manager-ai-1",
            target_id="sales-kb",
            limit=5,
        )
        sales_audit_events = await self.persistence.query_audit_logs(sales_audit_query)

        assert len(sales_audit_events) > 0, "No audit events found for Sales KB query"
        sales_audit = sales_audit_events[0]
        assert sales_audit.source_id == "product-manager-ai-1"
        assert sales_audit.target_id == "sales-kb"
        assert sales_audit.outcome == AuditOutcome.SUCCESS
        print(f"✓ Sales KB audit log created:")
        print(f"  - Source: {sales_audit.source_id}")
        print(f"  - Target: {sales_audit.target_id}")
        print(f"  - Outcome: {sales_audit.outcome}")
        print(f"  - Masked: {sales_audit.masked_fields}")

        # Check Engineering KB audit log
        eng_audit_query = AuditQuery(
            event_type=AuditEventType.QUERY,
            source_id="product-manager-ai-1",
            target_id="engineering-kb",
            limit=5,
        )
        eng_audit_events = await self.persistence.query_audit_logs(eng_audit_query)

        assert (
            len(eng_audit_events) > 0
        ), "No audit events found for Engineering KB query"
        eng_audit = eng_audit_events[0]
        assert eng_audit.source_id == "product-manager-ai-1"
        assert eng_audit.target_id == "engineering-kb"
        assert eng_audit.outcome == AuditOutcome.SUCCESS
        print(f"\n✓ Engineering KB audit log created:")
        print(f"  - Source: {eng_audit.source_id}")
        print(f"  - Target: {eng_audit.target_id}")
        print(f"  - Outcome: {eng_audit.outcome}")
        print(f"  - Masked: {eng_audit.masked_fields}")

        # Step 9: Verify independent policy application
        print("\n[Step 9] Verifying independent policy application...")
        # Sales KB should have different masked fields than Engineering KB
        assert set(sales_audit.masked_fields or []) != set(
            eng_audit.masked_fields or []
        ), "Policies should be applied independently"
        print("✓ Policies applied independently per KB:")
        print(f"  - Sales KB masked: {sales_audit.masked_fields}")
        print(f"  - Engineering KB masked: {eng_audit.masked_fields}")

        # Final summary
        print("\n" + "=" * 80)
        print("✅ SCENARIO 7.1 PASSED: Multi-Source Query with Real AI Agent")
        print("=" * 80)
        print("\nSUMMARY:")
        print(f"  ✓ Queried 2 different KBs (PostgreSQL + Neo4j)")
        print(f"  ✓ Applied independent field-level policies")
        print(f"  ✓ Real OpenAI Agent detected timeline contradiction")
        print(f"  ✓ Both queries logged separately in audit trail")
        print(f"  ✓ Sales Timeline: {sales_timeline}")
        print(f"  ✓ Engineering Feasibility: {eng_feasibility}")
        print(f"  ✓ AI Synthesis: CONTRADICTION DETECTED ✨")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

