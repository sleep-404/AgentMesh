"""
SQLite persistence adapter implementation.

Handles schema translation and migrations internally.
"""
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import yaml  # type: ignore[import-untyped]

from ..base import BasePersistenceAdapter
from ..exceptions import (
    ConnectionError as PersistenceConnectionError,
)
from ..exceptions import (
    DuplicateRecordError,
    QueryError,
)
from ..schemas import (
    AgentRecord,
    AgentRegistration,
    AuditEvent,
    AuditQuery,
    AuditRecord,
    HealthStatus,
    KBRecord,
    KBRegistration,
    PolicyDefinition,
    PolicyRecord,
    PolicyRule,
    RegistryQuery,
)
from .migrations import run_migrations


class SQLitePersistenceAdapter(BasePersistenceAdapter):
    """SQLite implementation of persistence adapter"""

    def __init__(self, config_path: str):
        super().__init__(config_path)
        self.db_path: Path | None = None
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to SQLite and run migrations"""
        try:
            # Load config
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)

            assert self.config is not None, "Config is None after loading"
            assert "database" in self.config, "Config missing database section"

            self.db_path = Path(self.config["database"]["path"])
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect
            self.conn = await aiosqlite.connect(str(self.db_path))
            self.conn.row_factory = aiosqlite.Row

            # Set SQLite pragmas
            await self.conn.execute(
                f"PRAGMA journal_mode={self.config['database'].get('journal_mode', 'WAL')}"
            )
            await self.conn.execute(
                f"PRAGMA synchronous={self.config['database'].get('synchronous', 'NORMAL')}"
            )

            # Run migrations (adapter handles schema setup)
            await run_migrations(self.conn)

        except Exception as e:
            raise PersistenceConnectionError(f"Failed to connect to SQLite: {e}") from e

    async def disconnect(self) -> None:
        """Close connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def health_check(self) -> dict:
        """Check adapter health"""
        assert self.conn is not None, "Adapter not connected"
        try:
            cursor = await self.conn.execute("SELECT 1")
            await cursor.fetchone()
            return {"status": "healthy", "database": str(self.db_path)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # ============================================
    # AGENT REGISTRY
    # ============================================

    async def register_agent(self, agent: AgentRegistration) -> str:
        """Register agent - translate Pydantic to SQL"""
        assert self.conn is not None, "Adapter not connected"
        agent_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        try:
            await self.conn.execute(
                """
                INSERT INTO agents (
                    id, identity, version, capabilities, operations,
                    schemas, health_endpoint, status, registered_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    agent.identity,
                    agent.version,
                    json.dumps(agent.capabilities),  # List → JSON
                    json.dumps(agent.operations),
                    json.dumps(agent.schemas),  # Dict → JSON
                    agent.health_endpoint,
                    HealthStatus.OFFLINE.value,
                    now,
                    json.dumps(agent.metadata),
                ),
            )
            await self.conn.commit()
            return agent_id
        except aiosqlite.IntegrityError as e:
            raise DuplicateRecordError(
                f"Agent with identity '{agent.identity}' already exists: {e}"
            ) from e
        except Exception as e:
            raise QueryError(f"Failed to register agent: {e}") from e

    async def get_agent(self, identity: str) -> AgentRecord | None:
        """Get agent by identity - translate SQL to Pydantic"""
        assert self.conn is not None, "Adapter not connected"
        try:
            cursor = await self.conn.execute(
                "SELECT * FROM agents WHERE identity = ?", (identity,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return AgentRecord(
                id=row["id"],
                identity=row["identity"],
                version=row["version"],
                capabilities=json.loads(row["capabilities"]),  # JSON → List
                operations=json.loads(row["operations"]),
                schemas=json.loads(row["schemas"]),  # JSON → Dict
                health_endpoint=row["health_endpoint"],
                status=HealthStatus(row["status"]),
                registered_at=datetime.fromisoformat(row["registered_at"]),
                last_heartbeat=datetime.fromisoformat(row["last_heartbeat"])
                if row["last_heartbeat"]
                else None,
                metadata=json.loads(row["metadata"]),
            )
        except Exception as e:
            raise QueryError(f"Failed to get agent: {e}") from e

    async def update_agent_status(self, identity: str, status: str) -> None:
        """Update agent status"""
        assert self.conn is not None, "Adapter not connected"
        now = datetime.now(UTC).isoformat()
        try:
            await self.conn.execute(
                """
                UPDATE agents
                SET status = ?, last_heartbeat = ?
                WHERE identity = ?
                """,
                (status, now, identity),
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to update agent status: {e}") from e

    async def update_agent_capabilities(self, identity: str, capabilities: list[str]) -> None:
        """Update agent capabilities"""
        assert self.conn is not None, "Adapter not connected"
        try:
            capabilities_json = json.dumps(capabilities)
            await self.conn.execute(
                """
                UPDATE agents
                SET capabilities = ?
                WHERE identity = ?
                """,
                (capabilities_json, identity),
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to update agent capabilities: {e}") from e

    async def list_agents(self, query: RegistryQuery) -> list[AgentRecord]:
        """Query agents with filters"""
        assert self.conn is not None, "Adapter not connected"
        try:
            conditions = []
            params: list[Any] = []

            if query.identity:
                conditions.append("identity = ?")
                params.append(query.identity)

            if query.status:
                conditions.append("status = ?")
                params.append(query.status.value)

            if query.capabilities:
                # SQLite JSON query - use json_each for proper array membership check
                for cap in query.capabilities:
                    conditions.append(
                        """EXISTS (
                            SELECT 1 FROM json_each(capabilities) 
                            WHERE json_each.value = ?
                        )"""
                    )
                    params.append(cap)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            sql = f"SELECT * FROM agents WHERE {where_clause} LIMIT ?"
            params.append(query.limit)

            cursor = await self.conn.execute(sql, params)
            rows = await cursor.fetchall()

            return [
                AgentRecord(
                    id=row["id"],
                    identity=row["identity"],
                    version=row["version"],
                    capabilities=json.loads(row["capabilities"]),
                    operations=json.loads(row["operations"]),
                    schemas=json.loads(row["schemas"]),
                    health_endpoint=row["health_endpoint"],
                    status=HealthStatus(row["status"]),
                    registered_at=datetime.fromisoformat(row["registered_at"]),
                    last_heartbeat=datetime.fromisoformat(row["last_heartbeat"])
                    if row["last_heartbeat"]
                    else None,
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]
        except Exception as e:
            raise QueryError(f"Failed to list agents: {e}") from e

    async def deregister_agent(self, identity: str) -> None:
        """Remove agent"""
        assert self.conn is not None, "Adapter not connected"
        try:
            await self.conn.execute(
                "DELETE FROM agents WHERE identity = ?", (identity,)
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to deregister agent: {e}") from e

    # ============================================
    # KB REGISTRY
    # ============================================

    async def register_kb(self, kb: KBRegistration) -> str:
        """Register KB"""
        assert self.conn is not None, "Adapter not connected"
        kb_record_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        try:
            await self.conn.execute(
                """
                INSERT INTO knowledge_bases (
                    id, kb_id, kb_type, endpoint, operations,
                    schema, health_endpoint, status, registered_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kb_record_id,
                    kb.kb_id,
                    kb.kb_type,
                    kb.endpoint,
                    json.dumps(kb.operations),
                    json.dumps(kb.kb_schema),
                    kb.health_endpoint,
                    HealthStatus.OFFLINE.value,
                    now,
                    json.dumps(kb.metadata),
                ),
            )
            await self.conn.commit()
            return kb_record_id
        except aiosqlite.IntegrityError as e:
            raise DuplicateRecordError(
                f"KB with id '{kb.kb_id}' already exists: {e}"
            ) from e
        except Exception as e:
            raise QueryError(f"Failed to register KB: {e}") from e

    async def get_kb(self, kb_id: str) -> KBRecord | None:
        """Get KB by ID"""
        assert self.conn is not None, "Adapter not connected"
        try:
            cursor = await self.conn.execute(
                "SELECT * FROM knowledge_bases WHERE kb_id = ?", (kb_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return KBRecord(
                id=row["id"],
                kb_id=row["kb_id"],
                kb_type=row["kb_type"],
                endpoint=row["endpoint"],
                operations=json.loads(row["operations"]),
                kb_schema=json.loads(row["schema"]),
                health_endpoint=row["health_endpoint"],
                status=HealthStatus(row["status"]),
                registered_at=datetime.fromisoformat(row["registered_at"]),
                last_health_check=datetime.fromisoformat(row["last_health_check"])
                if row["last_health_check"]
                else None,
                metadata=json.loads(row["metadata"]),
            )
        except Exception as e:
            raise QueryError(f"Failed to get KB: {e}") from e

    async def update_kb_status(self, kb_id: str, status: str) -> None:
        """Update KB health status"""
        assert self.conn is not None, "Adapter not connected"
        now = datetime.now(UTC).isoformat()
        try:
            await self.conn.execute(
                """
                UPDATE knowledge_bases
                SET status = ?, last_health_check = ?
                WHERE kb_id = ?
                """,
                (status, now, kb_id),
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to update KB status: {e}") from e

    async def update_kb_operations(self, kb_id: str, operations: list[str]) -> None:
        """Update KB operations"""
        assert self.conn is not None, "Adapter not connected"
        try:
            operations_json = json.dumps(operations)
            await self.conn.execute(
                """
                UPDATE knowledge_bases
                SET operations = ?
                WHERE kb_id = ?
                """,
                (operations_json, kb_id),
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to update KB operations: {e}") from e

    async def list_kbs(self, query: RegistryQuery) -> list[KBRecord]:
        """Query KB registry"""
        assert self.conn is not None, "Adapter not connected"
        try:
            conditions = []
            params: list[Any] = []

            if query.kb_id:
                conditions.append("kb_id = ?")
                params.append(query.kb_id)

            if query.kb_type:
                conditions.append("kb_type = ?")
                params.append(query.kb_type)

            if query.status:
                conditions.append("status = ?")
                params.append(query.status.value)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            sql = f"SELECT * FROM knowledge_bases WHERE {where_clause} LIMIT ?"
            params.append(query.limit)

            cursor = await self.conn.execute(sql, params)
            rows = await cursor.fetchall()

            return [
                KBRecord(
                    id=row["id"],
                    kb_id=row["kb_id"],
                    kb_type=row["kb_type"],
                    endpoint=row["endpoint"],
                    operations=json.loads(row["operations"]),
                    kb_schema=json.loads(row["schema"]),
                    health_endpoint=row["health_endpoint"],
                    status=HealthStatus(row["status"]),
                    registered_at=datetime.fromisoformat(row["registered_at"]),
                    last_health_check=datetime.fromisoformat(row["last_health_check"])
                    if row["last_health_check"]
                    else None,
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]
        except Exception as e:
            raise QueryError(f"Failed to list KBs: {e}") from e

    async def deregister_kb(self, kb_id: str) -> None:
        """Remove KB from registry"""
        assert self.conn is not None, "Adapter not connected"
        try:
            await self.conn.execute(
                "DELETE FROM knowledge_bases WHERE kb_id = ?", (kb_id,)
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to deregister KB: {e}") from e

    # ============================================
    # POLICY STORE
    # ============================================

    async def create_policy(self, policy: PolicyDefinition) -> str:
        """Create a new policy"""
        assert self.conn is not None, "Adapter not connected"
        policy_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        try:
            await self.conn.execute(
                """
                INSERT INTO policies (
                    id, policy_name, rules, precedence, active,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    policy.policy_name,
                    json.dumps([rule.model_dump() for rule in policy.rules]),
                    policy.precedence,
                    1 if policy.active else 0,
                    now,
                    now,
                    json.dumps(policy.metadata),
                ),
            )
            await self.conn.commit()
            return policy_id
        except aiosqlite.IntegrityError as e:
            raise DuplicateRecordError(
                f"Policy with name '{policy.policy_name}' already exists: {e}"
            ) from e
        except Exception as e:
            raise QueryError(f"Failed to create policy: {e}") from e

    async def get_policy(self, policy_name: str) -> PolicyRecord | None:
        """Get policy by name"""
        assert self.conn is not None, "Adapter not connected"
        try:
            cursor = await self.conn.execute(
                "SELECT * FROM policies WHERE policy_name = ?", (policy_name,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return PolicyRecord(
                id=row["id"],
                policy_name=row["policy_name"],
                rules=[PolicyRule(**rule) for rule in json.loads(row["rules"])],
                precedence=row["precedence"],
                active=bool(row["active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                metadata=json.loads(row["metadata"]),
            )
        except Exception as e:
            raise QueryError(f"Failed to get policy: {e}") from e

    async def list_policies(self, active_only: bool = True) -> list[PolicyRecord]:
        """List all policies"""
        assert self.conn is not None, "Adapter not connected"
        try:
            if active_only:
                cursor = await self.conn.execute(
                    "SELECT * FROM policies WHERE active = 1 ORDER BY precedence ASC"
                )
            else:
                cursor = await self.conn.execute(
                    "SELECT * FROM policies ORDER BY precedence ASC"
                )

            rows = await cursor.fetchall()

            return [
                PolicyRecord(
                    id=row["id"],
                    policy_name=row["policy_name"],
                    rules=[PolicyRule(**rule) for rule in json.loads(row["rules"])],
                    precedence=row["precedence"],
                    active=bool(row["active"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]
        except Exception as e:
            raise QueryError(f"Failed to list policies: {e}") from e

    async def update_policy(self, policy_name: str, policy: PolicyDefinition) -> None:
        """Update existing policy"""
        assert self.conn is not None, "Adapter not connected"
        now = datetime.now(UTC).isoformat()
        try:
            await self.conn.execute(
                """
                UPDATE policies
                SET rules = ?, precedence = ?, active = ?, updated_at = ?, metadata = ?
                WHERE policy_name = ?
                """,
                (
                    json.dumps([rule.model_dump() for rule in policy.rules]),
                    policy.precedence,
                    1 if policy.active else 0,
                    now,
                    json.dumps(policy.metadata),
                    policy_name,
                ),
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to update policy: {e}") from e

    async def delete_policy(self, policy_name: str) -> None:
        """Delete policy"""
        assert self.conn is not None, "Adapter not connected"
        try:
            await self.conn.execute(
                "DELETE FROM policies WHERE policy_name = ?", (policy_name,)
            )
            await self.conn.commit()
        except Exception as e:
            raise QueryError(f"Failed to delete policy: {e}") from e

    async def evaluate_policy(self, principal: str, resource: str, action: str) -> dict:
        """
        Evaluate policy for a request.
        Returns: {"effect": "allow|deny", "masking_rules": [...], "matched_policy": "..."}
        """
        try:
            # Get all active policies ordered by precedence
            policies = await self.list_policies(active_only=True)

            # Default deny
            result = {"effect": "deny", "masking_rules": [], "matched_policy": None}

            # Evaluate policies in order (lower precedence = higher priority)
            for policy in policies:
                for rule in policy.rules:
                    # Simple wildcard matching
                    principal_match = self._matches(principal, rule.principal)
                    resource_match = self._matches(resource, rule.resource)
                    action_match = self._matches(action, rule.action)

                    if principal_match and resource_match and action_match:
                        result = {
                            "effect": rule.effect,
                            "masking_rules": rule.masking_rules,
                            "matched_policy": policy.policy_name,
                        }
                        # Return first match (highest precedence)
                        return result

            return result
        except Exception as e:
            raise QueryError(f"Failed to evaluate policy: {e}") from e

    def _matches(self, value: str, pattern: str) -> bool:
        """Simple wildcard matching (* = any)"""
        if pattern == "*":
            return True
        if "*" in pattern:
            # Convert wildcard pattern to regex-like matching
            import re

            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(f"^{regex_pattern}$", value))
        return value == pattern

    # ============================================
    # AUDIT LOGS
    # ============================================

    async def log_event(self, event: AuditEvent) -> str:
        """Log audit event"""
        assert self.conn is not None, "Adapter not connected"
        event_id = str(uuid.uuid4())

        try:
            await self.conn.execute(
                """
                INSERT INTO audit_logs (
                    id, event_type, source_id, target_id, outcome, timestamp,
                    request_metadata, policy_decision, masked_fields,
                    full_request, full_response, provenance_chain
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event.event_type.value,
                    event.source_id,
                    event.target_id,
                    event.outcome.value,
                    event.timestamp.isoformat(),
                    json.dumps(event.request_metadata)
                    if event.request_metadata
                    else None,
                    json.dumps(event.policy_decision)
                    if event.policy_decision
                    else None,
                    json.dumps(event.masked_fields) if event.masked_fields else None,
                    json.dumps(event.full_request) if event.full_request else None,
                    json.dumps(event.full_response) if event.full_response else None,
                    json.dumps(event.provenance_chain)
                    if event.provenance_chain
                    else None,
                ),
            )
            await self.conn.commit()
            return event_id
        except Exception as e:
            raise QueryError(f"Failed to log audit event: {e}") from e

    async def query_audit_logs(self, query: AuditQuery) -> list[AuditRecord]:
        """Query audit logs"""
        assert self.conn is not None, "Adapter not connected"
        try:
            conditions = []
            params: list[Any] = []

            if query.event_type:
                conditions.append("event_type = ?")
                params.append(query.event_type.value)

            if query.source_id:
                conditions.append("source_id = ?")
                params.append(query.source_id)

            if query.target_id:
                conditions.append("target_id = ?")
                params.append(query.target_id)

            if query.outcome:
                conditions.append("outcome = ?")
                params.append(query.outcome.value)

            if query.start_time:
                conditions.append("timestamp >= ?")
                params.append(query.start_time.isoformat())

            if query.end_time:
                conditions.append("timestamp <= ?")
                params.append(query.end_time.isoformat())

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            sql = f"SELECT * FROM audit_logs WHERE {where_clause} ORDER BY timestamp DESC LIMIT ?"
            params.append(query.limit)

            cursor = await self.conn.execute(sql, params)
            rows = await cursor.fetchall()

            return [
                AuditRecord(
                    id=row["id"],
                    event_type=row["event_type"],
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    outcome=row["outcome"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    request_metadata=json.loads(row["request_metadata"])
                    if row["request_metadata"]
                    else None,
                    policy_decision=json.loads(row["policy_decision"])
                    if row["policy_decision"]
                    else None,
                    masked_fields=json.loads(row["masked_fields"])
                    if row["masked_fields"]
                    else None,
                    full_request=json.loads(row["full_request"])
                    if row["full_request"]
                    else None,
                    full_response=json.loads(row["full_response"])
                    if row["full_response"]
                    else None,
                    provenance_chain=json.loads(row["provenance_chain"])
                    if row["provenance_chain"]
                    else None,
                )
                for row in rows
            ]
        except Exception as e:
            raise QueryError(f"Failed to query audit logs: {e}") from e

    async def get_audit_stats(self, source_id: str | None = None) -> dict:
        """Get audit statistics"""
        assert self.conn is not None, "Adapter not connected"
        try:
            # Count by outcome
            if source_id:
                cursor = await self.conn.execute(
                    """
                    SELECT outcome, COUNT(*) as count
                    FROM audit_logs
                    WHERE source_id = ?
                    GROUP BY outcome
                    """,
                    (source_id,),
                )
            else:
                cursor = await self.conn.execute(
                    """
                    SELECT outcome, COUNT(*) as count
                    FROM audit_logs
                    GROUP BY outcome
                    """
                )

            outcome_counts = {
                row["outcome"]: row["count"] for row in await cursor.fetchall()
            }

            # Count by event type
            if source_id:
                cursor = await self.conn.execute(
                    """
                    SELECT event_type, COUNT(*) as count
                    FROM audit_logs
                    WHERE source_id = ?
                    GROUP BY event_type
                    """,
                    (source_id,),
                )
            else:
                cursor = await self.conn.execute(
                    """
                    SELECT event_type, COUNT(*) as count
                    FROM audit_logs
                    GROUP BY event_type
                    """
                )

            event_type_counts = {
                row["event_type"]: row["count"] for row in await cursor.fetchall()
            }

            return {
                "outcome_counts": outcome_counts,
                "event_type_counts": event_type_counts,
            }
        except Exception as e:
            raise QueryError(f"Failed to get audit stats: {e}") from e
