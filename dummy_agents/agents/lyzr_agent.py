"""Lyzr Agent implementation.

Note: lyzr-automata has dependency conflicts with other packages (requires openai==1.3.4).
This implementation is a placeholder that explains the incompatibility.
To use real Lyzr, install lyzr-automata in a separate virtual environment.
"""
import os
from typing import Any

from dummy_agents.base import BaseAgent


class LyzrAgent(BaseAgent):
    """Lyzr agent implementation.

    Due to lyzr-automata requiring openai==1.3.4 (which conflicts with langchain, crewai, and openai>=1.100),
    this agent cannot be used in the same environment as the other agents.

    To use Lyzr:
    1. Create a separate virtual environment
    2. Install: pip install lyzr-automata
    3. Run this agent in that environment
    """

    def __init__(self, task: str, api_key: str | None = None):
        """Initialize Lyzr agent.

        Args:
            task: The task to execute
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        """
        super().__init__(task)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        # Check if lyzr is available
        self._lyzr_available = False
