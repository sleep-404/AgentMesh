"""
Pytest fixtures for persistence adapter tests.
"""
import tempfile
from pathlib import Path

import pytest

from adapters.persistence.sqlite import SQLitePersistenceAdapter


@pytest.fixture
async def sqlite_adapter():
    """Create test adapter with in-memory DB"""
    # Create temp config
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir) / "test_config.yaml"

    config_content = """
adapter:
  type: "sqlite"
  version: "1.0.0"

database:
  path: ":memory:"  # In-memory for tests
  journal_mode: "WAL"
  synchronous: "NORMAL"

audit:
  retention_days: 90
  default_level: "lightweight"
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    adapter = SQLitePersistenceAdapter(str(config_path))
    await adapter.connect()

    yield adapter

    await adapter.disconnect()

    # Cleanup
    if config_path.exists():
        config_path.unlink()
    if Path(temp_dir).exists():
        Path(temp_dir).rmdir()


@pytest.fixture
async def file_based_sqlite_adapter():
    """Create test adapter with file-based DB"""
    # Create temp config with file-based DB
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test.db"
    config_path = Path(temp_dir) / "test_config.yaml"

    config_content = f"""
adapter:
  type: "sqlite"
  version: "1.0.0"

database:
  path: "{db_file}"
  journal_mode: "WAL"
  synchronous: "NORMAL"

audit:
  retention_days: 90
  default_level: "lightweight"
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    adapter = SQLitePersistenceAdapter(str(config_path))
    await adapter.connect()

    yield adapter

    await adapter.disconnect()

    # Cleanup
    if db_file.exists():
        db_file.unlink()
    if config_path.exists():
        config_path.unlink()
    if Path(temp_dir).exists():
        try:
            Path(temp_dir).rmdir()
        except OSError:
            pass
