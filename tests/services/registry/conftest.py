"""
Pytest fixtures for registry service tests.
"""
import tempfile
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from services.registry import (
    AgentService,
    DirectoryService,
    HealthService,
    KBService,
)


@pytest.fixture(scope="function")
async def temp_db():
    """Create a temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        config_path = Path(tmpdir) / "config.yaml"

        # Create test config
        config = {
            "adapter": {"type": "sqlite", "version": "1.0.0"},
            "database": {
                "path": str(db_path),
                "journal_mode": "WAL",
                "synchronous": "NORMAL",
            },
            "audit": {"retention_days": 90, "default_level": "lightweight"},
        }

        with open(config_path, "w") as f:
            yaml.dump(config, f)

        yield str(config_path), str(db_path)


@pytest.fixture
async def persistence_adapter(temp_db):
    """Create and initialize persistence adapter"""
    config_path, _ = temp_db
    adapter = SQLitePersistenceAdapter(config_path)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


@pytest.fixture
async def agent_service(persistence_adapter):
    """Create agent service"""
    return AgentService(persistence_adapter)


@pytest.fixture
async def kb_service(persistence_adapter):
    """Create KB service"""
    return KBService(persistence_adapter)


@pytest.fixture
async def directory_service(persistence_adapter):
    """Create directory service"""
    return DirectoryService(persistence_adapter)


@pytest.fixture
async def health_service(persistence_adapter):
    """Create health service"""
    return HealthService(persistence_adapter)


@pytest.fixture
def sample_agent_registration():
    """Sample agent registration data"""
    from services.registry.schemas import AgentRegistrationRequest

    return AgentRegistrationRequest(
        identity="test-agent-1",
        version="1.0.0",
        capabilities=["query_kb", "analyze_data"],
        operations=["query", "invoke"],
        health_endpoint="http://localhost:8001/health",
        schemas={"input": {"type": "object"}, "output": {"type": "object"}},
        metadata={"team": "test-team", "region": "us-west"},
    )


@pytest.fixture
def sample_kb_registration():
    """Sample KB registration data"""
    from services.registry.schemas import KBRegistrationRequest

    return KBRegistrationRequest(
        kb_id="test-kb-1",
        kb_type="postgres",
        endpoint="postgres://localhost:5432/testdb",
        operations=["sql_query"],
        kb_schema={"tables": ["users", "orders"]},
        metadata={"owner": "test-owner", "description": "Test KB"},
    )
