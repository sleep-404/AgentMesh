"""Real OpenAI Agent implementation using OpenAI SDK."""
import os
from typing import Any

from openai import OpenAI

from dummy_agents.base import BaseAgent


class OpenAIAgent(BaseAgent):
    """Real OpenAI agent implementation."""

    def __init__(
        self, task: str, api_key: str | None = None, model: str = "gpt-4o-mini"
    ):
        """Initialize OpenAI agent.

        Args:
            task: The task to execute
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o-mini)
        """
        super().__init__(task)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable or api_key parameter is required"
            )
        self.model = model

    @property
    def agent_type(self) -> str:
        """Return the type of agent."""
        return "openai"

    def execute(self) -> dict[str, Any]:
        """Execute the agent's task using OpenAI API."""
        execution_log = []

        execution_log.append(f"Initializing OpenAI client with model: {self.model}")
        client = OpenAI(api_key=self.api_key)

        execution_log.append("Preparing prompt")
        prompt = f"Task: {self.task}\n\nPlease complete this task concisely."

        execution_log.append("Calling OpenAI API")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that completes tasks.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
        )

        execution_log.append("Parsing API response")
        result = response.choices[0].message.content

        return {
            "agent_type": self.agent_type,
            "task": self.task,
            "prompt": prompt,
            "result": result,
            "execution_log": execution_log,
            "model": self.model,
            "status": "completed",
        }
