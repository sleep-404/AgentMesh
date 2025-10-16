"""
Request/response schemas for registration services.

These Pydantic models define the structure of data flowing through the services.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ============================================
# AGENT REGISTRATION SCHEMAS
# ============================================


class AgentRegistrationRequest(BaseModel):
    """Request to register a new agent"""

    identity: str = Field(..., description="Unique agent identifier")
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")
    capabilities: list[str] = Field(..., description="What the agent can do")
    operations: list[str] = Field(
        ..., description="Supported operations (publish, query, subscribe, invoke)"
    )
    health_endpoint: str = Field(..., description="URL for health checks")
    schemas: dict[str, Any] = Field(
        default_factory=dict, description="Input/output schemas"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (team, region, etc.)"
    )


class AgentRegistrationResponse(BaseModel):
    """Response after successful agent registration"""

    agent_id: str = Field(..., description="System-generated agent ID")
    identity: str
    version: str
    status: str = Field(..., description="Initial health status")
    registered_at: datetime
    message: str = Field(
        default="Agent registered successfully",
        description="Confirmation message",
    )
    next_steps: list[str] = Field(
        default_factory=lambda: [
            "Use list_agents to view all registered agents",
            "Use check_health to manually verify agent health",
            "Agent will be automatically health checked periodically",
        ]
    )


class AgentDetailsResponse(BaseModel):
    """Detailed agent information"""

    agent_id: str
    identity: str
    version: str
    capabilities: list[str]
    operations: list[str]
    schemas: dict[str, Any]
    health_endpoint: str
    status: str
    registered_at: datetime
    last_heartbeat: datetime | None
    metadata: dict[str, Any]


# ============================================
# KB REGISTRATION SCHEMAS
# ============================================


class KBRegistrationRequest(BaseModel):
    """Request to register a knowledge base"""

    kb_id: str = Field(..., description="Unique KB identifier")
    kb_type: str = Field(..., description="KB type (postgres, neo4j, etc.)")
    endpoint: str = Field(..., description="Connection string")
    operations: list[str] = Field(..., description="Supported operations")
    kb_schema: dict[str, Any] = Field(
        default_factory=dict, description="Data structure schema"
    )
    credentials: dict[str, str] | None = Field(
        default=None, description="Optional credentials (handled securely)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Owner, description, etc."
    )


class KBRegistrationResponse(BaseModel):
    """Response after successful KB registration"""

    kb_record_id: str = Field(..., description="System-generated KB record ID")
    kb_id: str
    kb_type: str
    status: str = Field(..., description="Initial connectivity status")
    registered_at: datetime
    message: str = Field(
        default="KB registered successfully", description="Confirmation message"
    )
    next_steps: list[str] = Field(
        default_factory=lambda: [
            "Use list_kbs to view all registered knowledge bases",
            "Use get_kb_details to see full KB configuration",
            "KB operations are now available as MCP tools",
        ]
    )


class KBDetailsResponse(BaseModel):
    """Detailed KB information"""

    kb_record_id: str
    kb_id: str
    kb_type: str
    endpoint: str
    operations: list[str]
    kb_schema: dict[str, Any]
    health_endpoint: str | None
    status: str
    registered_at: datetime
    last_health_check: datetime | None
    metadata: dict[str, Any]


# ============================================
# DIRECTORY QUERY SCHEMAS
# ============================================


class AgentListRequest(BaseModel):
    """Request to list agents with optional filters"""

    capability_filter: str | None = Field(
        default=None, description="Filter by capability"
    )
    status_filter: str | None = Field(
        default=None, description="Filter by status (active/degraded/offline)"
    )
    limit: int = Field(default=100, description="Maximum results to return")


class AgentListResponse(BaseModel):
    """Response with list of agents"""

    agents: list[AgentDetailsResponse]
    total_count: int
    filters_applied: dict[str, Any]


class KBListRequest(BaseModel):
    """Request to list KBs with optional filters"""

    type_filter: str | None = Field(default=None, description="Filter by KB type")
    status_filter: str | None = Field(
        default=None, description="Filter by health status"
    )
    limit: int = Field(default=100, description="Maximum results to return")


class KBListResponse(BaseModel):
    """Response with list of KBs"""

    kbs: list[KBDetailsResponse]
    total_count: int
    filters_applied: dict[str, Any]


# ============================================
# HEALTH CHECK SCHEMAS
# ============================================


class HealthCheckRequest(BaseModel):
    """Request to check health of an entity"""

    entity_id: str = Field(..., description="Agent identity or KB ID")
    entity_type: str = Field(..., description="'agent' or 'kb'")


class HealthCheckResponse(BaseModel):
    """Response with health check results"""

    entity_id: str
    entity_type: str
    status: str = Field(..., description="Current health status")
    last_check: datetime
    latency_ms: float | None = Field(default=None, description="Response time")
    error: str | None = Field(default=None, description="Error details if unhealthy")
    message: str


# ============================================
# ERROR RESPONSE SCHEMA
# ============================================


class ErrorResponse(BaseModel):
    """Standardized error response"""

    error_type: str = Field(..., description="Type of error")
    field: str | None = Field(default=None, description="Field that failed")
    message: str = Field(..., description="Error message")
    suggestion: str | None = Field(default=None, description="How to fix")
