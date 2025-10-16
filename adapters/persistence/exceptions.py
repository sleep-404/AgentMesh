"""
Persistence-specific exceptions for AgentMesh.
"""


class PersistenceException(Exception):
    """Base exception for persistence layer"""

    pass


class ConnectionError(PersistenceException):
    """Raised when connection to storage fails"""

    pass


class MigrationError(PersistenceException):
    """Raised when migration fails"""

    pass


class RecordNotFoundError(PersistenceException):
    """Raised when a requested record doesn't exist"""

    pass


class DuplicateRecordError(PersistenceException):
    """Raised when trying to create a duplicate record"""

    pass


class QueryError(PersistenceException):
    """Raised when a query fails"""

    pass


class PolicyEvaluationError(PersistenceException):
    """Raised when policy evaluation fails"""

    pass
