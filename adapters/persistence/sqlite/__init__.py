"""
SQLite persistence adapter for AgentMesh.

Provides a lightweight, file-based persistence layer suitable for
development, testing, and small deployments.
"""

from .adapter import SQLitePersistenceAdapter

__all__ = ["SQLitePersistenceAdapter"]
