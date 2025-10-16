"""
Mesh-defined schemas for persistence layer.

These are storage-agnostic Pydantic models.
Adapters translate these to their native storage formats.
"""
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health status for agents and KBs"""

    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"


# ============================================
# AGENT REGISTRY SCHEMAS
# ============================================


class AgentRegistration(BaseModel):
    """Agent registration data"""

    identity: str = Field(..., description="Stable capability identity")
    version: str = Field(..., description="Agent version")
    capabilities: list[str] = Field(..., description="Declared capabilities")
    operations: list[str] = Field(..., description="Supported operations")
    schemas: dict[str, Any] = Field(default_factory=dict, description="I/O schemas")
    health_endpoint: str = Field(..., description="Health check endpoint")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class AgentRecord(BaseModel):
    """Agent record in registry (includes system fields)"""

    id: str = Field(..., description="System-generated ID")
    identity: str
    version: str
    capabilities: list[str]
    operations: list[str]
    schemas: dict[str, Any]
    health_endpoint: str
    status: HealthStatus = HealthStatus.OFFLINE
    registered_at: datetime
    last_heartbeat: datetime | None = None
    metadata: dict[str, Any]


# ============================================
# KB REGISTRY SCHEMAS
# ============================================


class KBRegistration(BaseModel):
    """Knowledge base registration data"""

    kb_id: str = Field(..., description="KB identifier")
    kb_type: str = Field(..., description="KB type (postgres, neo4j, etc.)")
    endpoint: str = Field(..., description="Connection endpoint")
    operations: list[str] = Field(..., description="Supported operations")
    kb_schema: dict[str, Any] = Field(
        default_factory=dict, description="KB schema definition"
    )
    health_endpoint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KBRecord(BaseModel):
    """KB record in registry"""

    id: str
    kb_id: str
    kb_type: str
    endpoint: str
    operations: list[str]
    kb_schema: dict[str, Any]
    health_endpoint: str | None
    status: HealthStatus = HealthStatus.OFFLINE
    registered_at: datetime
    last_health_check: datetime | None = None
    metadata: dict[str, Any]


# ============================================
# POLICY SCHEMAS
# ============================================


class PolicyRule(BaseModel):
    """Individual policy rule"""

    principal: str = Field(..., description="Who (user/agent/role)")
    resource: str = Field(..., description="What (KB/agent)")
    action: str = Field(..., description="Operation (read/write/invoke)")
    effect: str = Field(..., description="allow/deny")
    conditions: dict[str, Any] = Field(default_factory=dict)
    masking_rules: list[str] = Field(default_factory=list, description="Fields to mask")


class PolicyDefinition(BaseModel):
    """Policy definition"""

    policy_name: str
    rules: list[PolicyRule]
    precedence: int = Field(default=100, description="Lower = higher precedence")
    active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyRecord(BaseModel):
    """Policy record in storage"""

    id: str
    policy_name: str
    rules: list[PolicyRule]
    precedence: int
    active: bool
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


# ============================================
# AUDIT LOG SCHEMAS
# ============================================


class AuditEventType(str, Enum):
    """Types of audit events"""

    QUERY = "query"
    INVOKE = "invoke"
    REGISTER = "register"
    POLICY_UPDATE = "policy_update"
    WRITE = "write"


class AuditOutcome(str, Enum):
    """Outcome of audit events"""

    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"


class AuditEvent(BaseModel):
    """Lightweight audit event (extensible to medium/heavy)"""

    event_type: AuditEventType
    source_id: str = Field(..., description="Requester (user/agent ID)")
    target_id: str | None = Field(None, description="Target (KB/agent ID)")
    outcome: AuditOutcome
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Optional medium-weight fields
    request_metadata: dict[str, Any] | None = None
    policy_decision: dict[str, Any] | None = None
    masked_fields: list[str] | None = None

    # Optional heavy-weight fields (opt-in)
    full_request: dict[str, Any] | None = None
    full_response: dict[str, Any] | None = None
    provenance_chain: list[str] | None = None


class AuditRecord(BaseModel):
    """Audit record in storage (includes system ID)"""

    id: str
    event_type: AuditEventType
    source_id: str
    target_id: str | None
    outcome: AuditOutcome
    timestamp: datetime
    request_metadata: dict[str, Any] | None
    policy_decision: dict[str, Any] | None
    masked_fields: list[str] | None
    full_request: dict[str, Any] | None
    full_response: dict[str, Any] | None
    provenance_chain: list[str] | None


# ============================================
# QUERY FILTERS
# ============================================


class RegistryQuery(BaseModel):
    """Query filters for registry lookups"""

    identity: str | None = None
    kb_id: str | None = None
    capabilities: list[str] | None = None
    kb_type: str | None = None
    status: HealthStatus | None = None
    limit: int = 100


class AuditQuery(BaseModel):
    """Query filters for audit logs"""

    event_type: AuditEventType | None = None
    source_id: str | None = None
    target_id: str | None = None
    outcome: AuditOutcome | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = 100
