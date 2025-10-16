"""
Migration logic for SQLite adapter.

The adapter owns these migrations - mesh doesn't know about them.
"""
from datetime import UTC, datetime

import aiosqlite


async def run_migrations(conn: aiosqlite.Connection) -> None:
    """Run all migrations"""
    # Create migrations table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """
    )

    # Get current version
    cursor = await conn.execute("SELECT MAX(version) as version FROM schema_migrations")
    row = await cursor.fetchone()
    current_version = row[0] if row[0] else 0

    # Apply migrations
    migrations = [
        (1, create_agent_registry_table),
        (2, create_kb_registry_table),
        (3, create_policy_tables),
        (4, create_audit_log_table),
    ]

    for version, migration_func in migrations:
        if version > current_version:
            await migration_func(conn)
            await conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            await conn.commit()
            print(f"Applied migration v{version}: {migration_func.__name__}")


async def create_agent_registry_table(conn: aiosqlite.Connection):
    """Migration 1: Agent registry"""
    await conn.execute(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            identity TEXT UNIQUE NOT NULL,
            version TEXT NOT NULL,
            capabilities TEXT NOT NULL,  -- JSON array
            operations TEXT NOT NULL,     -- JSON array
            schemas TEXT NOT NULL,        -- JSON object
            health_endpoint TEXT NOT NULL,
            status TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            last_heartbeat TEXT,
            metadata TEXT NOT NULL        -- JSON object
        )
    """
    )
    await conn.execute("CREATE INDEX idx_agents_identity ON agents(identity)")
    await conn.execute("CREATE INDEX idx_agents_status ON agents(status)")


async def create_kb_registry_table(conn: aiosqlite.Connection):
    """Migration 2: KB registry"""
    await conn.execute(
        """
        CREATE TABLE knowledge_bases (
            id TEXT PRIMARY KEY,
            kb_id TEXT UNIQUE NOT NULL,
            kb_type TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            operations TEXT NOT NULL,     -- JSON array
            schema TEXT NOT NULL,         -- JSON object
            health_endpoint TEXT,
            status TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            last_health_check TEXT,
            metadata TEXT NOT NULL        -- JSON object
        )
    """
    )
    await conn.execute("CREATE INDEX idx_kbs_kb_id ON knowledge_bases(kb_id)")
    await conn.execute("CREATE INDEX idx_kbs_type ON knowledge_bases(kb_type)")


async def create_policy_tables(conn: aiosqlite.Connection):
    """Migration 3: Policy store"""
    await conn.execute(
        """
        CREATE TABLE policies (
            id TEXT PRIMARY KEY,
            policy_name TEXT UNIQUE NOT NULL,
            rules TEXT NOT NULL,          -- JSON array of PolicyRule
            precedence INTEGER NOT NULL,
            active INTEGER NOT NULL,      -- 1=true, 0=false
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL        -- JSON object
        )
    """
    )
    await conn.execute("CREATE INDEX idx_policies_name ON policies(policy_name)")
    await conn.execute("CREATE INDEX idx_policies_active ON policies(active)")


async def create_audit_log_table(conn: aiosqlite.Connection):
    """Migration 4: Audit logs"""
    await conn.execute(
        """
        CREATE TABLE audit_logs (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT,
            outcome TEXT NOT NULL,
            timestamp TEXT NOT NULL,

            -- Medium-weight fields
            request_metadata TEXT,        -- JSON object
            policy_decision TEXT,         -- JSON object
            masked_fields TEXT,           -- JSON array

            -- Heavy-weight fields (opt-in)
            full_request TEXT,            -- JSON object
            full_response TEXT,           -- JSON object
            provenance_chain TEXT         -- JSON array
        )
    """
    )
    await conn.execute("CREATE INDEX idx_audit_event_type ON audit_logs(event_type)")
    await conn.execute("CREATE INDEX idx_audit_source ON audit_logs(source_id)")
    await conn.execute("CREATE INDEX idx_audit_target ON audit_logs(target_id)")
    await conn.execute("CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp)")
    await conn.execute("CREATE INDEX idx_audit_outcome ON audit_logs(outcome)")
