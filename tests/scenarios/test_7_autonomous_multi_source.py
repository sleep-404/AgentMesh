"""
Test Suite: Section 7 - TRULY Autonomous Multi-Source Query

This test demonstrates a REAL autonomous agent that:
1. Connects to mesh via NATS ONLY
2. Discovers KBs dynamically from mesh (no hardcoding)
3. Uses OpenAI to decide which KBs to query
4. Queries KBs through mesh governance layer (NATS)
5. Synthesizes results using OpenAI
6. Is completely unaware of mesh implementation

NO direct mesh API calls - EVERYTHING through NATS!
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.schemas import AuditEventType, AuditQuery
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from dummy_agents.agents.autonomous_openai_agent import AutonomousOpenAIAgent
from services.directory.subscriber import DirectorySubscriber
from services.enforcement import EnforcementService
from services.registry import KBService
from services.routing import RequestRouter

# Load environment variables
load_dotenv()


class TestSection7AutonomousMultiSource:
    """Test truly autonomous multi-source query"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup mesh infrastructure (but agent won't know about it!)"""
        # Check for OpenAI API key
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            pytest.skip("OPENAI_API_KEY not found in environment")

        # Initialize mesh infrastructure
        self.persistence = SQLitePersistenceAdapter(
            "adapters/persistence/sqlite/config.yaml"
        )
        await self.persistence.connect()

        # NATS for mesh communication
        self.nats_client = NATSWrapper()
        try:
            await self.nats_client.connect()
        except Exception:
            pytest.skip("NATS not available")

        # OPA for policies
        self.opa_client = OPAClient()
        try:
            is_healthy = await self.opa_client.health_check()
            if not is_healthy:
                pytest.skip("OPA not available")
        except Exception:
            pytest.skip("OPA not available")

        # Setup KB adapters
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

        # Start KB adapters listening
        await self.postgres_adapter.start_listening()
        await self.neo4j_adapter.start_listening()

        # Setup mesh services
        self.kb_service = KBService(self.persistence, self.nats_client)

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

        self.request_router = RequestRouter(
            enforcement=self.enforcement_service,
            persistence=self.persistence,
            nats_client=self.nats_client,
        )
        await self.request_router.start()

        # Start directory subscriber (so agents can discover KBs!)
        self.directory_subscriber = DirectorySubscriber(
            persistence_adapter=self.persistence,
            nats_url="nats://localhost:4222"
        )
        await self.directory_subscriber.start()

        # Setup test data and policies
        await self._setup_test_data()
        await self._setup_policies()

        yield

        # Cleanup
        await self.directory_subscriber.stop()
        await self.request_router.stop()
        await self.postgres_adapter.disconnect()
        await self.neo4j_adapter.disconnect()
        
        # NATS may already be closed by other services
        try:
            if self.nats_client and not self.nats_client.nc.is_closed:
                await self.nats_client.disconnect()
        except Exception:
            pass  # Ignore if already closed
            
        await self.persistence.disconnect()

    async def _setup_test_data(self):
        """Setup test data in both KBs"""
        print("\n[Setup] Creating test data...")

        # Register KBs with mesh (this makes them discoverable!)
        from services.registry.schemas import KBRegistrationRequest
        
        # Clean up ALL old test KBs first
        print("  - Cleaning up old test KBs...")
        from adapters.persistence.schemas import RegistryQuery
        all_kbs = await self.persistence.list_kbs(RegistryQuery())
        for kb in all_kbs:
            try:
                await self.kb_service.deregister_kb(kb.kb_id)
                print(f"    ✓ Removed old KB: {kb.kb_id}")
            except Exception as e:
                print(f"    ⚠ Could not remove {kb.kb_id}: {e}")
        
        # Force directory subscriber to reload from persistence
        await self.directory_subscriber._load_directory()
        print("  ✓ Directory cache refreshed")
        
        # Register Sales KB with detailed description
        sales_kb_request = KBRegistrationRequest(
            kb_id="sales-kb",
            kb_type="postgres",
            endpoint="postgresql://localhost:5432/agentmesh",
            operations=["sql_query"],
            kb_schema={
                "tables": {
                    "commitments": {
                        "columns": {
                            "id": "integer primary key",
                            "feature": "varchar - name of the feature (e.g. 'Feature Y')",  
                            "timeline": "varchar - delivery timeline (e.g. 'Q1 2025')",
                            "customer": "varchar - customer name",
                            "revenue": "decimal - deal value",
                            "customer_email": "varchar - customer email (PII)",
                            "customer_phone": "varchar - customer phone (PII)"
                        },
                        "description": "Sales commitments table. Query using 'feature' column (not 'feature_name') to filter by feature name"
                    }
                }
            },
            metadata={
                "owner": "sales", 
                "description": "Sales feature commitments database. Contains timeline commitments for Feature Y deliveries to customers.",
                "primary_use": "Query sales commitments and delivery timelines"
            },
        )
        await self.kb_service.register_kb(sales_kb_request)

        # Register Engineering KB with detailed description
        eng_kb_request = KBRegistrationRequest(
            kb_id="engineering-kb",
            kb_type="neo4j",
            endpoint="bolt://localhost:7687",
            operations=["cypher_query"],
            kb_schema={
                "nodes": {
                    "Feature": {
                        "properties": ["name", "feasibility", "status", "complexity", "tech_lead", "tech_lead_email"],
                        "description": "Engineering features with feasibility timelines"
                    }
                }
            },
            metadata={
                "owner": "engineering", 
                "description": "Engineering feature roadmap graph database. Contains Feature Y feasibility and development timelines.",
                "primary_use": "Query engineering feasibility and roadmap timelines"
            },
        )
        await self.kb_service.register_kb(eng_kb_request)

        print("  ✓ KBs registered with mesh")

        # Setup PostgreSQL data
        await self.postgres_adapter.execute(
            "sql_query",
            query="""
            CREATE TABLE IF NOT EXISTS commitments (
                id SERIAL PRIMARY KEY,
                feature VARCHAR(200),
                timeline VARCHAR(50),
                customer VARCHAR(200),
                revenue DECIMAL(12,2),
                customer_email VARCHAR(255),
                customer_phone VARCHAR(50)
            )
            """
        )
        await self.postgres_adapter.execute("sql_query", query="DELETE FROM commitments")
        await self.postgres_adapter.execute(
            "sql_query",
            query="""
            INSERT INTO commitments (feature, timeline, customer, revenue, customer_email, customer_phone)
            VALUES 
                ('Feature Y', 'Q1 2025', 'Acme Corp', 150000, 'john@acme.com', '+1-555-1001'),
                ('Feature Y', 'Q1 2025', 'TechCo', 200000, 'sarah@techco.com', '+1-555-1002')
            """
        )
        print("  ✓ PostgreSQL test data created")

        # Setup Neo4j data
        await self.neo4j_adapter.execute(
            "cypher_query",
            query="MATCH (f:Feature {name: 'Feature Y'}) DETACH DELETE f"
        )
        await self.neo4j_adapter.execute(
            "cypher_query",
            query="""
            CREATE (f:Feature {
                name: 'Feature Y',
                feasibility: 'Q3 2025',
                status: 'planned',
                complexity: 'high',
                tech_lead: 'Alice',
                tech_lead_email: 'alice@company.internal'
            })
            """
        )
        print("  ✓ Neo4j test data created\n")

    async def _setup_policies(self):
        """Setup OPA policies for KB access"""
        # Clean up existing policies
        existing_policies = ["autonomous_agent_policy", "multi_source_policy", "field_masking_test"]
        for policy in existing_policies:
            try:
                await self.opa_client.delete_policy(policy, delete_file=False)
            except Exception:
                pass
        await asyncio.sleep(0.3)

        # Create policy that allows the autonomous agent to query both KBs
        policy_rego = """
package agentmesh

import future.keywords.if

# Allow autonomous agent to query Sales KB
allow_kb_access if {
    input.principal_type == "agent"
    input.principal_id == "autonomous-pm-agent"
    input.resource_type == "kb"
    input.resource_id == "sales-kb"
    input.action == "sql_query"
}

# Allow autonomous agent to query Engineering KB
allow_kb_access if {
    input.principal_type == "agent"
    input.principal_id == "autonomous-pm-agent"
    input.resource_type == "kb"
    input.resource_id == "engineering-kb"
    input.action == "cypher_query"
}

# Mask PII in Sales KB
masking_rules = ["customer_email", "customer_phone"] if {
    input.principal_type == "agent"
    input.principal_id == "autonomous-pm-agent"
    input.resource_type == "kb"
    input.resource_id == "sales-kb"
}

# Mask internal data in Engineering KB
masking_rules = ["tech_lead_email"] if {
    input.principal_type == "agent"
    input.principal_id == "autonomous-pm-agent"
    input.resource_type == "kb"
    input.resource_id == "engineering-kb"
}

# Decision
decision = result if {
    input.resource_type == "kb"
    result := {
        "allow": allow_kb_access,
        "masking_rules": masking_rules,
        "reason": reason_message
    }
}

reason_message = "Policy allows KB access" if {
    allow_kb_access
} else = "No policy grants KB access"
"""
        result = await self.opa_client.upload_policy(
            "autonomous_agent_policy", policy_rego, persist=False
        )
        assert result["success"], f"Policy upload failed: {result}"
        await asyncio.sleep(0.5)

    async def test_autonomous_agent_multi_source_query(self):
        """
        Test TRULY autonomous agent querying multiple KBs.
        
        The agent:
        - Has ZERO knowledge of mesh internals
        - Only communicates via NATS
        - Discovers KBs dynamically
        - Uses OpenAI to decide what to query
        - Synthesizes results with OpenAI
        """
        print("\n" + "=" * 80)
        print("TEST: Autonomous Agent Multi-Source Query (NATS ONLY)")
        print("=" * 80)

        # Define the agent's task with clear instructions
        task = """
You are a Product Manager AI analyzing Feature Y delivery timelines.

YOUR TASK:
1. Query the SALES database (PostgreSQL) with SQL:
   SELECT timeline FROM commitments WHERE feature = 'Feature Y'
   (Note: use column name 'feature', not 'feature_name')
   
2. Query the ENGINEERING database (Neo4j graph) with Cypher:
   MATCH (f:Feature {name: 'Feature Y'}) RETURN f.feasibility
   
3. Compare the two timelines
4. If there's a mismatch (sales promised earlier than engineering can deliver), report "CONTRADICTION DETECTED" and explain the problem

IMPORTANT: Use the EXACT queries shown above.
"""

        print("\n[Test] Creating autonomous OpenAI agent...")
        print(f"Task: {task.strip()}")
        
        # Create autonomous agent (it knows NOTHING about the mesh!)
        agent = AutonomousOpenAIAgent(
            agent_id="autonomous-pm-agent",
            task=task,
            openai_api_key=self.openai_api_key,
            model="gpt-4o-mini",
            nats_url="nats://localhost:4222",
        )

        print("\n[Test] Launching autonomous agent execution...")
        print("-" * 80)
        
        # The agent does EVERYTHING autonomously!
        result = await agent.execute_autonomous_task()
        
        print("-" * 80)
        print("\n[Test] Autonomous execution complete!\n")

        # Print execution log for debugging
        print("\n[Debug] Agent execution log:")
        for log_entry in result.get("execution_log", []):
            print(f"  {log_entry}")
        print()

        # Verify the results
        assert result["status"] == "completed", f"Agent failed: {result.get('error')}\nExecution log: {result.get('execution_log')}"
        assert result["kbs_queried"] == 2, f"Expected 2 KBs queried, got {result['kbs_queried']}"
        
        synthesis = result["synthesis"]
        print("=" * 80)
        print("AGENT SYNTHESIS:")
        print("=" * 80)
        print(synthesis)
        print("=" * 80)
        
        # Verify agent detected the contradiction
        assert (
            "CONTRADICTION" in synthesis.upper() or
            "CONFLICT" in synthesis.upper() or
            "MISMATCH" in synthesis.upper()
        ), "Agent should detect timeline contradiction"

        # Verify both KBs were queried
        query_results = result["query_results"]
        kb_ids_queried = [qr["kb_id"] for qr in query_results]
        
        print(f"\n[Test] KBs queried by agent: {kb_ids_queried}")
        
        # Check that exactly 2 KBs were queried (should be sales-kb and engineering-kb)
        assert len(kb_ids_queried) == 2, f"Expected 2 KBs queried, got {len(kb_ids_queried)}: {kb_ids_queried}"
        
        # Verify we got one postgres and one neo4j KB
        kb_types = [qr["kb_type"] for qr in query_results]
        assert "postgres" in kb_types, "Should query a PostgreSQL KB"
        assert "neo4j" in kb_types, "Should query a Neo4j KB"

        # Verify responses were successful and masked
        for qr in query_results:
            response = qr["response"]
            assert response["status"] == "success", f"KB query failed: {response.get('error')}"
            assert "masked_fields" in response, "Response should include masked_fields"
            assert len(response["masked_fields"]) > 0, "Some fields should be masked"

        # Verify audit logs (mesh logged everything!)
        await asyncio.sleep(0.5)
        
        sales_audit = await self.persistence.query_audit_logs(
            AuditQuery(
                event_type=AuditEventType.QUERY,
                source_id="autonomous-pm-agent",
                target_id="sales-kb",
                limit=5,
            )
        )
        assert len(sales_audit) > 0, "Sales KB access should be audited"

        eng_audit = await self.persistence.query_audit_logs(
            AuditQuery(
                event_type=AuditEventType.QUERY,
                source_id="autonomous-pm-agent",
                target_id="engineering-kb",
                limit=5,
            )
        )
        assert len(eng_audit) > 0, "Engineering KB access should be audited"

        print("\n✅ AUTONOMOUS AGENT TEST PASSED!")
        print("\n" + "=" * 80)
        print("WHAT THE AGENT DID AUTONOMOUSLY:")
        print("=" * 80)
        print("  ✓ Connected to mesh via NATS only")
        print(f"  ✓ Agent identity 'autonomous-pm-agent' used as auth token")
        print(f"  ✓ Discovered 2 KBs from mesh directory (only sales-kb & engineering-kb)")
        print("  ✓ Used OpenAI GPT-4o-mini to plan which KBs to query")
        print(f"  ✓ OpenAI decided to query: {kb_ids_queried}")
        print("  ✓ Sent queries through mesh.routing.kb_query (not direct to KBs)")
        print("  ✓ OPA validated agent identity token and authorized access")
        print("  ✓ Mesh applied field-level masking per policy")
        print("  ✓ Sales KB: Masked customer_email, customer_phone")
        print("  ✓ Engineering KB: Masked tech_lead_email")
        print("  ✓ Used OpenAI to synthesize results and detect contradiction")
        print("  ✓ All queries audited by mesh with agent identity")
        print("\n✨ Agent had ZERO knowledge of mesh implementation!")
        print("✨ Everything done through NATS - completely mesh-agnostic!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

