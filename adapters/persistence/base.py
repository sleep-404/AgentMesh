"""
Base persistence adapter interface.

Mesh uses this interface; adapters implement storage logic.
"""
from abc import ABC, abstractmethod
from typing import Any

from .schemas import (
    AgentRecord,
    AgentRegistration,
    AuditEvent,
    AuditQuery,
    AuditRecord,
    KBRecord,
    KBRegistration,
    PolicyDefinition,
    PolicyRecord,
    RegistryQuery,
)


class BasePersistenceAdapter(ABC):
    """
    Base adapter for mesh persistence.

    Adapters handle:
    - Schema translation (Pydantic → native storage)
    - Migrations (DDL, setup scripts)
    - Query translation
    - Connection management
    """

    def __init__(self, config_path: str):
        """Initialize adapter with config"""
        self.config_path = config_path
        self.config: dict[str, Any] | None = None

    # ============================================
    # CONNECTION LIFECYCLE
    # ============================================

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection and run migrations if needed"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection"""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check adapter health"""
        pass

    # ============================================
    # AGENT REGISTRY
    # ============================================

    @abstractmethod
    async def register_agent(self, agent: AgentRegistration) -> str:
        """
        Register a new agent.
        Returns: agent record ID
        """
        pass

    @abstractmethod
    async def get_agent(self, identity: str) -> AgentRecord | None:
        """Get agent by identity"""
        pass

    @abstractmethod
    async def update_agent_status(self, identity: str, status: str) -> None:
        """Update agent health status"""
        pass

    @abstractmethod
    async def list_agents(self, query: RegistryQuery) -> list[AgentRecord]:
        """Query agent registry"""
        pass

    @abstractmethod
    async def deregister_agent(self, identity: str) -> None:
        """Remove agent from registry"""
        pass

    # ============================================
    # KB REGISTRY
    # ============================================

    @abstractmethod
    async def register_kb(self, kb: KBRegistration) -> str:
        """
        Register a new knowledge base.
        Returns: KB record ID
        """
        pass

    @abstractmethod
    async def get_kb(self, kb_id: str) -> KBRecord | None:
        """Get KB by ID"""
        pass

    @abstractmethod
    async def update_kb_status(self, kb_id: str, status: str) -> None:
        """Update KB health status"""
        pass

    @abstractmethod
    async def list_kbs(self, query: RegistryQuery) -> list[KBRecord]:
        """Query KB registry"""
        pass

    @abstractmethod
    async def deregister_kb(self, kb_id: str) -> None:
        """Remove KB from registry"""
        pass

    # ============================================
    # POLICY STORE
    # ============================================

    @abstractmethod
    async def create_policy(self, policy: PolicyDefinition) -> str:
        """
        Create a new policy.
        Returns: policy record ID
        """
        pass

    @abstractmethod
    async def get_policy(self, policy_name: str) -> PolicyRecord | None:
        """Get policy by name"""
        pass

    @abstractmethod
    async def list_policies(self, active_only: bool = True) -> list[PolicyRecord]:
        """List all policies"""
        pass

    @abstractmethod
    async def update_policy(self, policy_name: str, policy: PolicyDefinition) -> None:
        """Update existing policy"""
        pass

    @abstractmethod
    async def delete_policy(self, policy_name: str) -> None:
        """Delete policy"""
        pass

    @abstractmethod
    async def evaluate_policy(self, principal: str, resource: str, action: str) -> dict:
        """
        Evaluate policy for a request.
        Returns: {"effect": "allow|deny", "masking_rules": [...], "matched_policy": "..."}
        """
        pass

    # ============================================
    # AUDIT LOGS
    # ============================================

    @abstractmethod
    async def log_event(self, event: AuditEvent) -> str:
        """
        Log an audit event.
        Returns: event record ID
        """
        pass

    @abstractmethod
    async def query_audit_logs(self, query: AuditQuery) -> list[AuditRecord]:
        """Query audit logs"""
        pass

    @abstractmethod
    async def get_audit_stats(self, source_id: str | None = None) -> dict:
        """Get audit statistics (count by outcome, event type, etc.)"""
        pass
