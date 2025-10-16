"""
Tests for KB registration service.
"""
import pytest

from services.registry.exceptions import (
    DuplicateKBError,
    InvalidOperationError,
    UnsupportedKBTypeError,
)
from services.registry.schemas import KBRegistrationRequest


@pytest.mark.asyncio
async def test_register_kb_success(kb_service, sample_kb_registration):
    """Test successful KB registration"""
    response = await kb_service.register_kb(sample_kb_registration)

    assert response.kb_record_id is not None
    assert response.kb_id == sample_kb_registration.kb_id
    assert response.kb_type == sample_kb_registration.kb_type
    assert response.status in ["active", "offline"]
    assert response.message is not None


@pytest.mark.asyncio
async def test_register_kb_duplicate_id(kb_service, sample_kb_registration):
    """Test that duplicate KB IDs are rejected"""
    # Register first time
    await kb_service.register_kb(sample_kb_registration)

    # Try to register again with same ID
    with pytest.raises(DuplicateKBError):
        await kb_service.register_kb(sample_kb_registration)


@pytest.mark.asyncio
async def test_register_kb_unsupported_type(kb_service):
    """Test that unsupported KB types are rejected"""
    invalid_request = KBRegistrationRequest(
        kb_id="test-kb-2",
        kb_type="unsupported_type",
        endpoint="some://endpoint",
        operations=["test"],
    )

    with pytest.raises(UnsupportedKBTypeError):
        await kb_service.register_kb(invalid_request)


@pytest.mark.asyncio
async def test_register_kb_invalid_operation(kb_service):
    """Test that invalid operations for KB type are rejected"""
    invalid_request = KBRegistrationRequest(
        kb_id="test-kb-3",
        kb_type="postgres",
        endpoint="postgres://localhost:5432/test",
        operations=["invalid_operation"],  # Not valid for postgres
    )

    with pytest.raises(InvalidOperationError):
        await kb_service.register_kb(invalid_request)


@pytest.mark.asyncio
async def test_get_kb_details(kb_service, sample_kb_registration):
    """Test retrieving KB details"""
    # Register KB
    await kb_service.register_kb(sample_kb_registration)

    # Get details
    details = await kb_service.get_kb_details(sample_kb_registration.kb_id)

    assert details.kb_id == sample_kb_registration.kb_id
    assert details.kb_type == sample_kb_registration.kb_type
    assert details.operations == sample_kb_registration.operations


@pytest.mark.asyncio
async def test_get_kb_details_not_found(kb_service):
    """Test getting details for non-existent KB"""
    from services.registry.exceptions import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        await kb_service.get_kb_details("non-existent-kb")


@pytest.mark.asyncio
async def test_deregister_kb(kb_service, sample_kb_registration):
    """Test deregistering a KB"""
    # Register KB
    await kb_service.register_kb(sample_kb_registration)

    # Deregister
    await kb_service.deregister_kb(sample_kb_registration.kb_id)

    # Verify it's gone
    from services.registry.exceptions import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        await kb_service.get_kb_details(sample_kb_registration.kb_id)


@pytest.mark.asyncio
async def test_register_neo4j_kb(kb_service):
    """Test registering a Neo4j KB"""
    neo4j_request = KBRegistrationRequest(
        kb_id="test-neo4j-kb",
        kb_type="neo4j",
        endpoint="bolt://localhost:7687",
        operations=["cypher_query", "create_node"],
        kb_schema={"nodes": ["Person", "Product"]},
        metadata={"description": "Test Neo4j KB"},
    )

    response = await kb_service.register_kb(neo4j_request)

    assert response.kb_id == neo4j_request.kb_id
    assert response.kb_type == "neo4j"
