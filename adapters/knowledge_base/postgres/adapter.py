"""PostgreSQL adapter implementation."""

import time
from typing import Any

import asyncpg

from ..base import BaseKBAdapter
from ..schemas import HealthResponse, HealthStatus, OperationMetadata
from .operations import (
    DeleteInput,
    DeleteOutput,
    InsertInput,
    InsertOutput,
    SQLQueryInput,
    SQLQueryOutput,
    UpdateInput,
    UpdateOutput,
)


class PostgresAdapter(BaseKBAdapter):
    """PostgreSQL adapter for Knowledge Base operations."""

    def __init__(self, config_path: str, nats_client=None, kb_id: str | None = None):
        """Initialize PostgreSQL adapter.

        Args:
            config_path: Path to the configuration file
            nats_client: Optional NATS client for message broker pattern
            kb_id: Optional KB identifier for NATS subject routing
        """
        self.pool: asyncpg.Pool | None = None
        super().__init__(config_path, nats_client, kb_id)

    async def connect(self):
        """Establish connection pool to PostgreSQL."""
        self.pool = await asyncpg.create_pool(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            database=self.config["database"],
            min_size=self.config.get("pool_min_size", 1),
            max_size=self.config.get("pool_max_size", 10),
        )

    async def disconnect(self):
        """Close connection pool to PostgreSQL."""
        if self.pool:
            await self.pool.close()

    async def health(self) -> HealthResponse:
        """Check PostgreSQL health and connectivity.

        Returns:
            Health response with status and latency
        """
        if not self.pool:
            return HealthResponse(
                status=HealthStatus.UNHEALTHY, message="Connection pool not initialized"
            )

        try:
            start = time.time()
            async with self.pool.acquire() as conn:  # type: ignore[union-attr]
                await conn.fetchval("SELECT 1")
            latency = (time.time() - start) * 1000  # Convert to milliseconds

            return HealthResponse(status=HealthStatus.HEALTHY, latency_ms=latency)
        except Exception as e:
            return HealthResponse(status=HealthStatus.UNHEALTHY, message=str(e))

    def _register_operations(self):
        """Register PostgreSQL-specific operations."""

        # Operation 1: SQL Query
        self.operation_registry.register(
            OperationMetadata(
                name="sql_query",
                description="Execute raw SQL query",
                input_schema=SQLQueryInput.model_json_schema(),
                output_schema=SQLQueryOutput.model_json_schema(),
            ),
            handler=self._sql_query,
        )

        # Operation 2: Insert
        self.operation_registry.register(
            OperationMetadata(
                name="insert",
                description="Insert data into table",
                input_schema=InsertInput.model_json_schema(),
                output_schema=InsertOutput.model_json_schema(),
            ),
            handler=self._insert,
        )

        # Operation 3: Update
        self.operation_registry.register(
            OperationMetadata(
                name="update",
                description="Update data in table",
                input_schema=UpdateInput.model_json_schema(),
                output_schema=UpdateOutput.model_json_schema(),
            ),
            handler=self._update,
        )

        # Operation 4: Delete
        self.operation_registry.register(
            OperationMetadata(
                name="delete",
                description="Delete data from table",
                input_schema=DeleteInput.model_json_schema(),
                output_schema=DeleteOutput.model_json_schema(),
            ),
            handler=self._delete,
        )

    # Operation implementations

    async def _sql_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> SQLQueryOutput:
        """Execute a raw SQL query.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            Query results with row count
        """
        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(query, *(params.values() if params else []))
            return SQLQueryOutput(rows=[dict(row) for row in rows], row_count=len(rows))

    async def _insert(self, table: str, data: dict[str, Any]) -> InsertOutput:
        """Insert data into a table.

        Args:
            table: Table name
            data: Data to insert

        Returns:
            Insert result with inserted ID
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"

        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            try:
                result = await conn.fetchval(query, *data.values())
                return InsertOutput(inserted_id=result, success=True)
            except Exception:
                # If table doesn't have an 'id' column, run without RETURNING
                query_no_return = (
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
                )
                await conn.execute(query_no_return, *data.values())
                return InsertOutput(inserted_id=None, success=True)

    async def _update(
        self, table: str, data: dict[str, Any], where: dict[str, Any]
    ) -> UpdateOutput:
        """Update data in a table.

        Args:
            table: Table name
            data: Data to update
            where: WHERE clause conditions

        Returns:
            Update result with updated count
        """
        set_clause = ", ".join(f"{key} = ${i+1}" for i, key in enumerate(data.keys()))
        where_clause = " AND ".join(
            f"{key} = ${i+1+len(data)}" for i, key in enumerate(where.keys())
        )
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            result = await conn.execute(query, *data.values(), *where.values())
            # Extract count from result string like "UPDATE 5"
            updated_count = int(result.split()[-1]) if result else 0
            return UpdateOutput(updated_count=updated_count, success=True)

    async def _delete(self, table: str, where: dict[str, Any]) -> DeleteOutput:
        """Delete data from a table.

        Args:
            table: Table name
            where: WHERE clause conditions

        Returns:
            Delete result with deleted count
        """
        where_clause = " AND ".join(
            f"{key} = ${i+1}" for i, key in enumerate(where.keys())
        )
        query = f"DELETE FROM {table} WHERE {where_clause}"

        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            result = await conn.execute(query, *where.values())
            # Extract count from result string like "DELETE 3"
            deleted_count = int(result.split()[-1]) if result else 0
            return DeleteOutput(deleted_count=deleted_count, success=True)
