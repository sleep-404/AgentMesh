"""PostgreSQL-specific operations and schemas."""

from typing import Any

from pydantic import BaseModel

# Input schemas


class SQLQueryInput(BaseModel):
    """Input schema for SQL query operation."""

    query: str
    params: dict[str, Any] | None = None


class InsertInput(BaseModel):
    """Input schema for insert operation."""

    table: str
    data: dict[str, Any]


class UpdateInput(BaseModel):
    """Input schema for update operation."""

    table: str
    data: dict[str, Any]
    where: dict[str, Any]


class DeleteInput(BaseModel):
    """Input schema for delete operation."""

    table: str
    where: dict[str, Any]


# Output schemas


class SQLQueryOutput(BaseModel):
    """Output schema for SQL query operation."""

    rows: list[dict[str, Any]]
    row_count: int


class InsertOutput(BaseModel):
    """Output schema for insert operation."""

    inserted_id: Any | None
    success: bool


class UpdateOutput(BaseModel):
    """Output schema for update operation."""

    updated_count: int
    success: bool


class DeleteOutput(BaseModel):
    """Output schema for delete operation."""

    deleted_count: int
    success: bool
