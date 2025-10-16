"""Real Langraph Agent implementation using langgraph with mesh connectivity."""
import asyncio
import logging
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from dummy_agents.base import BaseAgent
from sdk.agent_client import AgentCallbacks, AgentClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the Langraph agent."""

    task: str
    steps: list[str]
    result: str
    status: str
    mesh_data: dict[str, Any]  # Data from mesh (agents, KBs, etc.)


class LangraphMeshCallbacks(AgentCallbacks):
    """Callbacks for handling mesh events."""

    def __init__(self, agent: "LangraphAgent"):
        self.agent = agent
        self.registered_agents: list[dict] = []
        self.registered_kbs: list[dict] = []

    async def on_agent_registered(self, agent_data: dict[str, Any]) -> None:
        """Handle new agent registration."""
        logger.info(f"[MESH] New agent registered: {agent_data}")
        self.registered_agents.append(agent_data)

    async def on_kb_registered(self, kb_data: dict[str, Any]) -> None:
        """Handle new KB registration."""
        logger.info(f"[MESH] New KB registered: {kb_data}")
        self.registered_kbs.append(kb_data)

    async def on_agent_disconnected(self, agent_data: dict[str, Any]) -> None:
        """Handle agent disconnection."""
        logger.info(f"[MESH] Agent disconnected: {agent_data}")

    async def on_direct_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle direct messages from other agents."""
        logger.info(f"[MESH] Received direct message: {message}")

        # Echo back for testing
        return {
            "status": "received",
            "original_message": message.get("payload", {}),
            "agent_type": "langraph",
        }


class LangraphAgent(BaseAgent):
    """Real Langraph agent implementation with mesh connectivity."""

    def __init__(self, task: str, connect_to_mesh: bool = False):
        """Initialize agent with optional mesh connection."""
        super().__init__(task)
        self.connect_to_mesh = connect_to_mesh
        self.mesh_client: AgentClient | None = None
        self.mesh_callbacks: LangraphMeshCallbacks | None = None
        self.mesh_tools: dict[str, Any] = {}
        self.available_agents: list[dict] = []
        self.available_kbs: list[dict] = []

    @property
    def agent_type(self) -> str:
        """Return the type of agent."""
        return "langraph"

    async def connect_to_mesh_async(self) -> None:
        """Connect to the mesh and discover capabilities."""
        logger.info("[MESH] Connecting to AgentMesh...")

        self.mesh_callbacks = LangraphMeshCallbacks(self)
        self.mesh_client = AgentClient(
            mesh_endpoint="http://localhost:8080/connect",
            agent_endpoint="http://localhost:8001",
            token="demo-token",
            callbacks=self.mesh_callbacks,
            metadata={"type": "langraph", "version": "1.0.0"},
        )

        # Connect
        connection_response = await self.mesh_client.connect()
        logger.info(f"[MESH] Connected as: {connection_response['agent_id']}")
        logger.info(f"[MESH] Private subject: {connection_response['private_subject']}")

        # Query available agents and KBs from mesh via MCP
        await self._discover_mesh_capabilities()

    async def _discover_mesh_capabilities(self) -> None:
        """Discover agents and KBs registered with mesh."""
        import aiohttp

        logger.info("[MESH] Discovering mesh capabilities...")

        # We need to query the MCP server for agents and KBs
        # For simplicity, we'll use direct HTTP calls to the connection API
        try:
            async with aiohttp.ClientSession() as session:
                # Get connected agents
                async with session.get("http://localhost:8080/agents") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.available_agents = data.get("agents", [])
                        logger.info(
                            f"[MESH] Found {len(self.available_agents)} connected agents"
                        )

                # For KBs, we'll need to use NATS to query the mesh registry
                # For now, let's assume we have postgres and neo4j from the mesh setup
                self.available_kbs = [
                    {"kb_id": "postgres-kb-1", "kb_type": "postgres"},
                    {"kb_id": "neo4j-kb-1", "kb_type": "neo4j"},
                ]
                logger.info(f"[MESH] Registered {len(self.available_kbs)} KBs as tools")

        except Exception as e:
            logger.error(f"[MESH] Failed to discover capabilities: {e}")

    async def query_kb_via_mesh(self, kb_id: str, operation: str, params: dict) -> Any:
        """Query a KB through the mesh."""
        logger.info(f"[MESH] Querying KB '{kb_id}' with operation '{operation}'")

        # Use NATS to send request to KB through mesh
        if self.mesh_client and self.mesh_client.nats.is_connected:
            # Publish to KB's NATS subject (format: <kb_id>.adapter.query)
            kb_subject = f"{kb_id}.adapter.query"

            try:
                response = await self.mesh_client.nats.request(
                    kb_subject,
                    {
                        "operation": operation,
                        "params": params,
                    },
                    timeout=10,
                )
                logger.info(f"[MESH] KB query response: {response}")
                return response
            except Exception as e:
                logger.error(f"[MESH] KB query failed: {e}")
                return {"error": str(e)}

        return {"error": "Not connected to mesh"}

    def _parse_input(self, state: AgentState) -> AgentState:
        """Parse the input task."""
        state["steps"].append("Parsed input task")
        state["mesh_data"] = {
            "agents": self.available_agents,
            "kbs": self.available_kbs,
            "tools": list(self.mesh_tools.keys()),
        }
        return state

    def _process_task(self, state: AgentState) -> AgentState:
        """Process the task through graph nodes."""
        state["steps"].append("Processing task through graph nodes")

        # If connected to mesh, use mesh capabilities
        if self.connect_to_mesh and self.mesh_client:
            state["steps"].append(
                f"Using mesh with {len(self.available_agents)} agents and {len(self.available_kbs)} KBs"
            )

            # Try to query a KB
            if self.available_kbs:
                kb = self.available_kbs[0]
                logger.info(f"[MESH] Attempting to query {kb['kb_type']} KB")

                # Run async query in sync context
                try:
                    loop = asyncio.get_event_loop()
                    if kb["kb_type"] == "postgres":
                        result = loop.run_until_complete(
                            self.query_kb_via_mesh(
                                kb["kb_id"],
                                "sql_query",
                                {"query": "SELECT 1 as test"},
                            )
                        )
                    elif kb["kb_type"] == "neo4j":
                        result = loop.run_until_complete(
                            self.query_kb_via_mesh(
                                kb["kb_id"],
                                "cypher_query",
                                {"query": "RETURN 1 as test"},
                            )
                        )
                    else:
                        result = {"error": "Unknown KB type"}

                    state["steps"].append(f"KB query result: {result}")
                    state["mesh_data"]["kb_query_result"] = result
                except Exception as e:
                    logger.error(f"[MESH] Error querying KB: {e}")
                    state["steps"].append(f"KB query error: {e}")

        processed = f"Langraph processed task: {state['task']}"
        if self.connect_to_mesh:
            processed += f" (with mesh: {len(self.available_agents)} agents, {len(self.available_kbs)} KBs)"

        state["result"] = processed
        return state

    def _generate_output(self, state: AgentState) -> AgentState:
        """Generate the final output."""
        state["steps"].append("Generated output")
        state["status"] = "completed"
        return state

    def execute(self) -> dict[str, Any]:
        """Execute the agent's task using Langraph workflow.

        This uses actual langgraph StateGraph to orchestrate the workflow.
        """
        # Connect to mesh if requested
        if self.connect_to_mesh:
            loop = asyncio.get_event_loop()
            try:
                loop.run_until_complete(self.connect_to_mesh_async())
            except Exception as e:
                logger.error(f"[MESH] Failed to connect: {e}")

        # Define the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("parse_input", self._parse_input)
        workflow.add_node("process_task", self._process_task)
        workflow.add_node("generate_output", self._generate_output)

        # Define edges (workflow)
        workflow.set_entry_point("parse_input")
        workflow.add_edge("parse_input", "process_task")
        workflow.add_edge("process_task", "generate_output")
        workflow.add_edge("generate_output", END)

        # Compile the graph
        app = workflow.compile()

        # Initialize state
        initial_state: AgentState = {
            "task": self.task,
            "steps": [],
            "result": "",
            "status": "running",
            "mesh_data": {},
        }

        # Execute the workflow
        final_state = app.invoke(initial_state)

        # Disconnect from mesh if connected
        if self.connect_to_mesh and self.mesh_client:
            loop = asyncio.get_event_loop()
            try:
                loop.run_until_complete(self.mesh_client.disconnect())
                logger.info("[MESH] Disconnected from mesh")
            except Exception as e:
                logger.error(f"[MESH] Error disconnecting: {e}")

        return {
            "agent_type": self.agent_type,
            "task": final_state["task"],
            "result": final_state["result"],
            "steps_executed": final_state["steps"],
            "status": final_state["status"],
            "mesh_data": final_state.get("mesh_data", {}),
        }
