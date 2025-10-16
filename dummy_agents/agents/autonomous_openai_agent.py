"""
Autonomous OpenAI Agent with full mesh connectivity.

This agent:
1. Connects to mesh via NATS only
2. Discovers available KBs dynamically from mesh registry
3. Queries KBs through mesh governance layer
4. Uses OpenAI for decision-making and synthesis
5. Is completely unaware of mesh implementation details
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from openai import OpenAI

from adapters.messaging.nats_client import NATSWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutonomousOpenAIAgent:
    """
    Fully autonomous OpenAI agent that discovers and queries KBs through mesh.
    
    The agent only knows about NATS subjects, not about the mesh implementation.
    """

    def __init__(
        self,
        agent_id: str,
        task: str,
        openai_api_key: str,
        model: str = "gpt-4o-mini",
        nats_url: str = "nats://localhost:4222",
    ):
        """Initialize autonomous agent.
        
        Args:
            agent_id: Unique agent identifier
            task: The task to accomplish
            openai_api_key: OpenAI API key
            model: OpenAI model to use
            nats_url: NATS server URL
        """
        self.agent_id = agent_id
        self.task = task
        self.model = model
        self.openai_client = OpenAI(api_key=openai_api_key)
        
        # NATS connection (only interface to mesh)
        self.nats = NATSWrapper(url=nats_url)
        
        # Discovered capabilities (learned from mesh)
        self.available_kbs: list[dict[str, Any]] = []
        self.available_agents: list[dict[str, Any]] = []
        
        # Execution log
        self.execution_log: list[str] = []

    async def connect_to_mesh(self) -> None:
        """Connect to mesh via NATS."""
        self.log(f"[{self.agent_id}] Connecting to mesh via NATS...")
        await self.nats.connect()
        self.log(f"[{self.agent_id}] Connected to NATS successfully")

    async def discover_mesh_capabilities(self) -> None:
        """Discover available agents and KBs from mesh directory."""
        self.log(f"[{self.agent_id}] Querying mesh directory for available KBs...")
        
        # Query mesh directory via NATS
        request = {
            "request_id": str(uuid.uuid4()),
            "filter": None,  # Get both agents and KBs
        }
        
        try:
            response = await self.nats.request(
                "mesh.directory.query",
                request,
                timeout=5
            )
            
            if response and "error" not in response:
                self.available_agents = response.get("agents", [])
                self.available_kbs = response.get("kbs", [])
                
                self.log(f"[{self.agent_id}] Discovery complete:")
                self.log(f"  - Found {len(self.available_agents)} agents")
                self.log(f"  - Found {len(self.available_kbs)} KBs")
                
                for kb in self.available_kbs:
                    kb_id = kb.get("kb_id", "unknown")
                    kb_type = kb.get("kb_type", "unknown")
                    operations = kb.get("operations", [])
                    self.log(f"    • {kb_id} ({kb_type}): {operations}")
            else:
                error = response.get("error", "Unknown error") if response else "No response"
                self.log(f"[{self.agent_id}] ❌ Discovery failed: {error}")
                
        except Exception as e:
            self.log(f"[{self.agent_id}] ❌ Discovery error: {e}")
            raise

    async def query_kb_via_mesh(
        self,
        kb_id: str,
        operation: str,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Query a KB through the mesh governance layer.
        
        This sends the query to mesh.routing.kb_query which handles:
        - Policy evaluation
        - KB routing
        - Response masking
        - Audit logging
        
        Args:
            kb_id: Target KB identifier
            operation: Operation to perform
            params: Operation parameters
            
        Returns:
            Query response from mesh
        """
        self.log(f"[{self.agent_id}] Sending KB query via mesh...")
        self.log(f"  - KB: {kb_id}")
        self.log(f"  - Operation: {operation}")
        
        # Construct governed query request
        # NOTE: agent_id serves as the authentication token that OPA validates
        request = {
            "request_id": str(uuid.uuid4()),
            "requester_id": self.agent_id,  # This is our auth token!
            "kb_id": kb_id,
            "operation": operation,
            "params": params,
        }
        
        try:
            # Send to mesh routing layer (NOT directly to KB!)
            response = await self.nats.request(
                "mesh.routing.kb_query",
                request,
                timeout=10
            )
            
            if response:
                status = response.get("status", "unknown")
                self.log(f"[{self.agent_id}] ✓ Query response: {status}")
                
                if status == "success":
                    masked_fields = response.get("masked_fields", [])
                    if masked_fields:
                        self.log(f"  - Masked fields: {masked_fields}")
                    return response
                elif status == "denied":
                    error = response.get("error", "Access denied")
                    self.log(f"[{self.agent_id}] ❌ Query denied: {error}")
                    return response
                else:
                    error = response.get("error", "Unknown error")
                    self.log(f"[{self.agent_id}] ❌ Query failed: {error}")
                    return response
            else:
                self.log(f"[{self.agent_id}] ❌ No response from mesh")
                return {"status": "error", "error": "No response from mesh"}
                
        except Exception as e:
            self.log(f"[{self.agent_id}] ❌ Query error: {e}")
            return {"status": "error", "error": str(e)}

    def use_openai_for_planning(self, discovered_kbs: list[dict]) -> dict[str, Any]:
        """
        Use OpenAI to plan which KBs to query based on the task.
        
        Args:
            discovered_kbs: List of available KBs from mesh
            
        Returns:
            Query plan from OpenAI
        """
        self.log(f"[{self.agent_id}] Using OpenAI to plan KB queries...")
        
        planning_prompt = f"""
You are an AI agent connected to a data mesh. Your task is:

{self.task}

Available Knowledge Bases:
{json.dumps(discovered_kbs, indent=2)}

Your job:
1. Determine which KBs you need to query to complete the task
2. For each KB, determine what specific query to run
3. Return a JSON plan with the structure:
{{
  "kbs_to_query": [
    {{
      "kb_id": "...",
      "kb_type": "postgres|neo4j",
      "reason": "why this KB is needed",
      "query": "the actual SQL or Cypher query"
    }}
  ]
}}

Return ONLY the JSON, no other text.
"""

        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a data mesh planning agent. Return only JSON."},
                {"role": "user", "content": planning_prompt}
            ],
            temperature=0.3,
        )
        
        plan_text = response.choices[0].message.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()
            
        plan = json.loads(plan_text)
        self.log(f"[{self.agent_id}] ✓ Query plan created: {len(plan['kbs_to_query'])} KB(s) to query")
        
        return plan

    def use_openai_for_synthesis(self, query_results: list[dict]) -> str:
        """
        Use OpenAI to synthesize results from multiple KBs.
        
        Args:
            query_results: Results from all KB queries
            
        Returns:
            Synthesized analysis
        """
        self.log(f"[{self.agent_id}] Using OpenAI to synthesize results...")
        
        synthesis_prompt = f"""
You are an AI agent analyzing data from multiple knowledge bases. Your original task was:

{self.task}

Query Results:
{json.dumps(query_results, indent=2)}

Your job:
1. Analyze all the data received
2. Look for patterns, contradictions, or insights
3. If there are timeline mismatches or conflicts, clearly identify them
4. Provide a concise analysis (3-4 sentences)
5. Start with "CONTRADICTION DETECTED" if you find conflicting information
6. Start with "ALIGNED" if everything is consistent

Be specific about what you found.
"""

        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a data analysis agent."},
                {"role": "user", "content": synthesis_prompt}
            ],
            temperature=0.5,
        )
        
        synthesis = response.choices[0].message.content.strip()
        self.log(f"[{self.agent_id}] ✓ Synthesis complete")
        
        return synthesis

    async def execute_autonomous_task(self) -> dict[str, Any]:
        """
        Autonomously execute the task by:
        1. Connecting to mesh
        2. Discovering available KBs
        3. Planning which KBs to query (using OpenAI)
        4. Executing queries through mesh
        5. Synthesizing results (using OpenAI)
        
        Returns:
            Execution result with synthesis
        """
        try:
            # Step 1: Connect to mesh
            await self.connect_to_mesh()
            
            # Step 2: Discover capabilities
            await self.discover_mesh_capabilities()
            
            if not self.available_kbs:
                return {
                    "status": "error",
                    "error": "No KBs available in mesh",
                    "execution_log": self.execution_log,
                }
            
            # Step 3: Use OpenAI to plan queries
            query_plan = self.use_openai_for_planning(self.available_kbs)
            
            # Step 4: Execute queries through mesh
            query_results = []
            for kb_query in query_plan["kbs_to_query"]:
                kb_id = kb_query["kb_id"]
                kb_type = kb_query["kb_type"]
                query = kb_query["query"]
                reason = kb_query.get("reason", "")
                
                self.log(f"\n[{self.agent_id}] Executing query on {kb_id}:")
                self.log(f"  Reason: {reason}")
                self.log(f"  Query: {query[:100]}...")
                
                # Determine operation based on KB type
                if kb_type == "postgres":
                    operation = "sql_query"
                    params = {"query": query}
                elif kb_type == "neo4j":
                    operation = "cypher_query"
                    params = {"query": query}
                else:
                    self.log(f"[{self.agent_id}] ⚠ Unknown KB type: {kb_type}")
                    continue
                
                # Query through mesh
                response = await self.query_kb_via_mesh(kb_id, operation, params)
                
                query_results.append({
                    "kb_id": kb_id,
                    "kb_type": kb_type,
                    "reason": reason,
                    "query": query,
                    "response": response,
                })
            
            # Step 5: Use OpenAI to synthesize results
            synthesis = self.use_openai_for_synthesis(query_results)
            
            return {
                "status": "completed",
                "agent_id": self.agent_id,
                "task": self.task,
                "kbs_queried": len(query_results),
                "synthesis": synthesis,
                "query_results": query_results,
                "execution_log": self.execution_log,
            }
            
        except Exception as e:
            self.log(f"[{self.agent_id}] ❌ Execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "execution_log": self.execution_log,
            }
        finally:
            # Clean up
            await self.nats.disconnect()
            self.log(f"[{self.agent_id}] Disconnected from mesh")

    def log(self, message: str) -> None:
        """Log a message to execution log and stdout."""
        self.execution_log.append(message)
        logger.info(message)

