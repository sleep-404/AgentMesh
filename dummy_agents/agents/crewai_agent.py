"""Real CrewAI Agent implementation using crewai."""
import os
from typing import Any

from crewai import Agent, Crew, Task

from dummy_agents.base import BaseAgent


class CrewAIAgent(BaseAgent):
    """Real CrewAI agent implementation."""

    def __init__(self, task: str, api_key: str | None = None):
        """Initialize CrewAI agent.

        Args:
            task: The task to execute
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        """
        super().__init__(task)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable or api_key parameter is required"
            )

    @property
    def agent_type(self) -> str:
        """Return the type of agent."""
        return "crewai"

    def execute(self) -> dict[str, Any]:
        """Execute the agent's task using CrewAI."""
        crew_steps = []

        crew_steps.append("Initializing CrewAI")

        # Set OpenAI API key
        os.environ["OPENAI_API_KEY"] = str(self.api_key)

        crew_steps.append("Creating agent with role: Task Executor")
        agent = Agent(
            role="Task Executor",
            goal="Complete the given task efficiently",
            backstory="You are an experienced task executor who completes tasks accurately.",
            verbose=False,
            allow_delegation=False,
        )
        role = str(agent.role)

        crew_steps.append("Creating task")
        task = Task(
            description=self.task,
            agent=agent,
            expected_output="A concise completion of the task",
        )

        crew_steps.append("Creating crew")
        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        crew_steps.append("Executing crew")
        crew_result = crew.kickoff()
        result = str(crew_result)

        return {
            "agent_type": self.agent_type,
            "task": self.task,
            "role": role,
            "result": result,
            "crew_steps": crew_steps,
            "status": "completed",
        }
