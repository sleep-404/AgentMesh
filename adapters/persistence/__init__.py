"""
Persistence adapters for AgentMesh.

This package provides adapters for persisting mesh state (agent registry,
KB registry, policies, audit logs) to various storage backends.
"""

from .base import BasePersistenceAdapter
from .schemas import (
    AgentRecord,
    # Agent schemas
    AgentRegistration,
    # Audit schemas
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditQuery,
    AuditRecord,
    # Enums
    HealthStatus,
    KBRecord,
    # KB schemas
    KBRegistration,
    PolicyDefinition,
    PolicyRecord,
    # Policy schemas
    PolicyRule,
    # Query schemas
    RegistryQuery,
)

__all__ = [
    "BasePersistenceAdapter",
    "HealthStatus",
    "AuditEventType",
    "AuditOutcome",
    "AgentRegistration",
    "AgentRecord",
    "KBRegistration",
    "KBRecord",
    "PolicyRule",
    "PolicyDefinition",
    "PolicyRecord",
    "AuditEvent",
    "AuditRecord",
    "RegistryQuery",
    "AuditQuery",
]
