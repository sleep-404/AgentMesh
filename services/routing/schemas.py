"""Request and response schemas for routing service."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ============================================
# KB QUERY SCHEMAS
# ============================================


class KBQueryRequest(BaseModel):
    """Request to query a knowledge base through the mesh."""

    requester_id: str = Field(..., description="Agent/user requesting access")
    kb_id: str = Field(..., description="Target KB identifier")
    operation: str = Field(
        ..., description="Operation to perform (e.g., 'sql_query', 'cypher_query')"
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Operation parameters"
    )


class KBQueryResponse(BaseModel):
    """Response from KB query through the mesh."""

    status: str = Field(..., description="Status (success, denied, error)")
    data: Any = Field(default=None, description="Response data (masked)")
    masked_fields: list[str] = Field(
        default_factory=list, description="Fields that were masked"
    )
    policy: str = Field(default="", description="Policy decision reason")
    error: str | None = Field(default=None, description="Error message if failed")


# ============================================
# AGENT INVOCATION SCHEMAS
# ============================================


class InvocationStatus(str, Enum):
    """Status of agent invocation."""

    AUTHORIZED = "authorized"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"


class AgentInvokeRequest(BaseModel):
    """Request to invoke an agent through the mesh."""

    source_agent_id: str = Field(..., description="Agent requesting invocation")
    target_agent_id: str = Field(..., description="Target agent to invoke")
    operation: str = Field(..., description="Operation to perform on target")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Operation payload"
    )


class AgentInvokeResponse(BaseModel):
    """Response from agent invocation request."""

    tracking_id: str = Field(..., description="Unique tracking ID for this invocation")
    status: InvocationStatus = Field(..., description="Current invocation status")
    source: str = Field(..., description="Source agent ID")
    target: str = Field(..., description="Target agent ID")
    operation: str = Field(..., description="Operation being performed")
    policy: str = Field(default="", description="Policy decision reason")
    error: str | None = Field(default=None, description="Error message if failed")
    result: dict[str, Any] | None = Field(
        default=None, description="Result data when completed"
    )
    started_at: datetime | None = Field(
        default=None, description="When invocation started"
    )
    completed_at: datetime | None = Field(
        default=None, description="When invocation completed"
    )


# ============================================
# INVOCATION TRACKING
# ============================================


class InvocationRecord(BaseModel):
    """Internal record for tracking invocations."""

    tracking_id: str
    source_agent_id: str
    target_agent_id: str
    operation: str
    payload: dict[str, Any]
    status: InvocationStatus
    started_at: datetime
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
