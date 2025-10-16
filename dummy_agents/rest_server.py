"""REST API server for CrewAI and OpenAI agents."""
import sys
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Load environment variables from project root .env file
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Add parent directory to path for imports
sys.path.insert(0, str(project_root))

from dummy_agents.agents.crewai_agent import CrewAIAgent
from dummy_agents.agents.openai_agent import OpenAIAgent


# Request/Response models
class AgentRequest(BaseModel):
    """Request model for agent execution."""

    task: str


class AgentResponse(BaseModel):
    """Response model for agent execution."""

    agent_type: str
    task: str
    result: str
    details: dict[str, Any]
    status: str


# Create FastAPI app
app = FastAPI(
    title="Agent REST API",
    description="REST API for CrewAI and OpenAI agents",
    version="1.0.0",
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Agent REST API",
        "endpoints": {"crewai": "/api/agents/crewai", "openai": "/api/agents/openai"},
    }


@app.post("/api/agents/crewai", response_model=AgentResponse)
async def execute_crewai_agent(request: AgentRequest):
    """Execute CrewAI agent.

    Args:
        request: AgentRequest with task

    Returns:
        AgentResponse with execution result
    """
    try:
        # Spawn agent
        agent = CrewAIAgent(task=request.task)

        # Execute task
        result = agent.execute()

        # Format response
        return AgentResponse(
            agent_type=result["agent_type"],
            task=result["task"],
            result=result["result"],
            details={
                "role": result.get("role"),
                "crew_steps": result.get("crew_steps", []),
            },
            status=result["status"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error executing CrewAI agent: {str(e)}"
        )


@app.post("/api/agents/openai", response_model=AgentResponse)
async def execute_openai_agent(request: AgentRequest):
    """Execute OpenAI agent.

    Args:
        request: AgentRequest with task

    Returns:
        AgentResponse with execution result
    """
    try:
        # Spawn agent
        agent = OpenAIAgent(task=request.task)

        # Execute task
        result = agent.execute()

        # Format response
        return AgentResponse(
            agent_type=result["agent_type"],
            task=result["task"],
            result=result["result"],
            details={
                "prompt": result.get("prompt"),
                "execution_log": result.get("execution_log", []),
                "model": result.get("model"),
            },
            status=result["status"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error executing OpenAI agent: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
