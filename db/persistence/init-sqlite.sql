-- SQLite initialization script for AgentMesh persistence
-- This script creates the initial schema and can be used for manual setup
-- Note: The SQLite adapter automatically runs migrations on connect,
-- so this file is mainly for reference and manual initialization if needed.

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Set journal mode to WAL for better concurrency
PRAGMA journal_mode = WAL;

-- Set synchronous mode
PRAGMA synchronous = NORMAL;

-- Migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Agent registry table
CREATE TABLE IF NOT EXISTS agents (
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
);

CREATE INDEX IF NOT EXISTS idx_agents_identity ON agents(identity);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);

-- Knowledge base registry table
CREATE TABLE IF NOT EXISTS knowledge_bases (
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
);

CREATE INDEX IF NOT EXISTS idx_kbs_kb_id ON knowledge_bases(kb_id);
CREATE INDEX IF NOT EXISTS idx_kbs_type ON knowledge_bases(kb_type);

-- Policy store table
CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    policy_name TEXT UNIQUE NOT NULL,
    rules TEXT NOT NULL,          -- JSON array of PolicyRule
    precedence INTEGER NOT NULL,
    active INTEGER NOT NULL,      -- 1=true, 0=false
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT NOT NULL        -- JSON object
);

CREATE INDEX IF NOT EXISTS idx_policies_name ON policies(policy_name);
CREATE INDEX IF NOT EXISTS idx_policies_active ON policies(active);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
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
);

CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_source ON audit_logs(source_id);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_logs(outcome);

-- Sample data (optional - for testing/demo purposes)
-- Uncomment to populate with sample data

-- INSERT INTO agents (id, identity, version, capabilities, operations, schemas, health_endpoint, status, registered_at, metadata)
-- VALUES (
--     'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
--     'sample-agent',
--     '1.0.0',
--     '["query_kb", "generate_report"]',
--     '["publish", "query", "subscribe"]',
--     '{}',
--     'http://localhost:8001/health',
--     'offline',
--     datetime('now'),
--     '{"environment": "development"}'
-- );
