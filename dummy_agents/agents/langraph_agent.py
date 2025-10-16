"""Real Langraph Agent implementation using langgraph."""
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from dummy_agents.base import BaseAgent


class AgentState(TypedDict):
    """State for the Langraph agent."""

    task: str
    steps: list[str]
    result: str
    status: str


class LangraphAgent(BaseAgent):
    """Real Langraph agent implementation."""

    @property
    def agent_type(self) -> str:
        """Return the type of agent."""
        return "langraph"

    def _parse_input(self, state: AgentState) -> AgentState:
        """Parse the input task."""
        state["steps"].append("Parsed input task")
        return state

    def _process_task(self, state: AgentState) -> AgentState:
        """Process the task through graph nodes."""
        state["steps"].append("Processing task through graph nodes")
        # Simple processing - in a real scenario, this could call LLMs, tools, etc.
        processed = f"Langraph processed task: {state['task']}"
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
        }

        # Execute the workflow
        final_state = app.invoke(initial_state)

        return {
            "agent_type": self.agent_type,
            "task": final_state["task"],
            "result": final_state["result"],
            "steps_executed": final_state["steps"],
            "status": final_state["status"],
        }
