"""
REST API Server for Agent Connections.

Provides REST endpoints for agents to connect to the mesh.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from adapters.messaging.nats_client import NATSWrapper
from services.connection import (
    AgentConnectionRequest,
    AgentConnectionService,
)
from services.connection.schemas import AgentDisconnectRequest, AgentHeartbeat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
nats_client: NATSWrapper | None = None
connection_service: AgentConnectionService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    global nats_client, connection_service

    # Startup
    logger.info("Starting AgentMesh REST API server...")

    # Initialize NATS
    nats_client = NATSWrapper()
    try:
        await nats_client.connect()
        logger.info("Connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        raise

    # Initialize connection service
    connection_service = AgentConnectionService(nats_client)
    await connection_service.start_monitoring(check_interval=30)
    logger.info("Connection service initialized")

    logger.info("REST API server ready")

    yield

    # Shutdown
    logger.info("Shutting down REST API server...")
    if connection_service:
        await connection_service.stop_monitoring()
    if nats_client:
        await nats_client.disconnect()
    logger.info("REST API server stopped")


app = FastAPI(
    title="AgentMesh Connection API",
    description="REST API for agents to connect to the mesh",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AgentMesh Connection API",
        "version": "1.0.0",
        "endpoints": {
            "/connect": "POST - Connect an agent to the mesh",
            "/disconnect": "POST - Disconnect an agent from the mesh",
            "/heartbeat": "POST - Send heartbeat from agent",
            "/agents": "GET - List connected agents",
            "/health": "GET - Health check",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    nats_status = (
        "connected" if nats_client and nats_client.is_connected else "disconnected"
    )
    return {
        "status": "healthy",
        "nats": nats_status,
        "service": "connection-api",
    }


@app.post("/connect")
async def connect_agent(request: AgentConnectionRequest):
    """
    Connect an agent to the mesh.

    Returns:
        Connection response with agent_id, private_subject, and global_subjects
    """
    if not connection_service:
        raise HTTPException(status_code=503, detail="Connection service not available")

    try:
        response = await connection_service.connect_agent(request)
        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode="json"),
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error connecting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/disconnect")
async def disconnect_agent(request: AgentDisconnectRequest):
    """
    Disconnect an agent from the mesh.
    """
    if not connection_service:
        raise HTTPException(status_code=503, detail="Connection service not available")

    try:
        await connection_service.disconnect_agent(request.agent_id, request.reason)
        return {
            "status": "success",
            "message": f"Agent '{request.agent_id}' disconnected",
        }
    except Exception as e:
        logger.error(f"Error disconnecting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/heartbeat")
async def heartbeat(request: AgentHeartbeat):
    """
    Receive heartbeat from agent.
    """
    if not connection_service:
        raise HTTPException(status_code=503, detail="Connection service not available")

    try:
        response = await connection_service.handle_heartbeat(request)
        return response
    except Exception as e:
        logger.error(f"Error handling heartbeat: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/agents")
async def list_agents():
    """
    List all connected agents.
    """
    if not connection_service:
        raise HTTPException(status_code=503, detail="Connection service not available")

    try:
        agents = await connection_service.get_connected_agents()
        return {
            "agents": agents,
            "count": len(agents),
        }
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/send-message/{target_agent_id}")
async def send_message(target_agent_id: str, message: dict):
    """
    Send a direct message to a connected agent (for testing).

    Args:
        target_agent_id: ID of the target agent
        message: Message payload
    """
    if not connection_service:
        raise HTTPException(status_code=503, detail="Connection service not available")

    try:
        success = await connection_service.send_direct_message(
            target_agent_id, message, from_agent_id="api"
        )
        if success:
            return {"status": "success", "message": "Message sent"}
        raise HTTPException(status_code=404, detail="Agent not found or message failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


def main():
    """Run the REST API server"""
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )


if __name__ == "__main__":
    main()
