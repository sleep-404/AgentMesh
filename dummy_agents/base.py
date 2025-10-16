"""Base agent interface for all dummy agents."""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, task: str):
        """Initialize agent with a task.

        Args:
            task: The task description for the agent to execute
        """
        self.task = task

    @abstractmethod
    def execute(self) -> dict[str, Any]:
        """Execute the agent's task.

        Returns:
            Dict containing the result of the agent's execution
        """
        pass

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Return the type of agent."""
        pass
