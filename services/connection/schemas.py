"""
Schemas for agent connection to mesh.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentConnectionRequest(BaseModel):
    """Request from agent to connect to the mesh"""

    endpoint: str = Field(..., description="Agent's gRPC/REST endpoint URL")
    token: str = Field(..., description="Authentication token (simple hardcoded token)")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional agent metadata"
    )


class AgentConnectionResponse(BaseModel):
    """Response after successful connection"""

    agent_id: str = Field(..., description="Unique ID assigned by mesh")
    private_subject: str = Field(
        ..., description="Private NATS subject for this agent (agent.<agent_id>)"
    )
    global_subjects: list[str] = Field(
        ..., description="Global subjects this agent is subscribed to"
    )
    connection_status: str = Field(default="connected")
    connected_at: datetime
    message: str = Field(
        default="Successfully connected to mesh", description="Confirmation message"
    )
    instructions: list[str] = Field(
        default_factory=lambda: [
            "Listen on your private_subject for direct messages",
            "Monitor global_subjects for mesh updates (new agents/KBs)",
            "Use request-reply pattern for synchronous communication",
            "Publish to other agents' private subjects for direct communication",
        ]
    )


class MeshUpdate(BaseModel):
    """Update notification sent to agents on global subjects"""

    update_type: str = Field(
        ...,
        description="Type of update (agent_registered, kb_registered, agent_disconnected, kb_removed)",
    )
    timestamp: datetime
    data: dict[str, Any] = Field(..., description="Update details")


class DirectMessage(BaseModel):
    """Message sent to an agent's private subject"""

    from_agent_id: str = Field(..., description="ID of sender agent")
    to_agent_id: str = Field(..., description="ID of recipient agent")
    message_type: str = Field(
        ..., description="Type of message (request, notification, reply)"
    )
    payload: dict[str, Any] = Field(..., description="Message payload")
    timestamp: datetime
    requires_reply: bool = Field(
        default=False, description="If true, sender expects a response"
    )


class AgentHeartbeat(BaseModel):
    """Heartbeat message from connected agent"""

    agent_id: str
    timestamp: datetime
    status: str = Field(default="active")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentDisconnectRequest(BaseModel):
    """Request to disconnect from mesh"""

    agent_id: str
    reason: str = Field(default="Normal disconnect")
