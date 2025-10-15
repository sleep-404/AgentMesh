"""Common schemas for Knowledge Base adapters."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """Health check response."""

    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None


class AdapterResponse(BaseModel):
    """Minimal envelope for adapter responses."""

    data: Any
    metadata: dict[str, Any] | None = None  # Keep this extensible


class OperationMetadata(BaseModel):
    """Metadata for an adapter operation."""

    name: str
    description: str
    input_schema: dict[str, Any]  # Pydantic model schema or dict
    output_schema: dict[str, Any]
