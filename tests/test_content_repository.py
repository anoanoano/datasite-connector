"""
Tests for Content Repository functionality.
"""

import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from src.content_repository import ContentRepository
from src.config import Config
from src.datasite_manager import DatasetMetadata

@pytest.fixture
def temp_config():
    """Create a temporary configuration for testing."""
    with TemporaryDirectory() as temp_dir:
        config = Config(
            content_storage_path=Path(temp_dir) / "content",
            encryption_key_path=Path(temp_dir) / "keys" / "test.key"
        )
        yield config

@pytest.fixture
Async def content_repo(temp_config):
    """Create and initialize a content repository for testing."""
    repo = ContentRepository(temp_config)
    await repo.initialize()
    return repo

@pytest.fixture
def sample_metadata():
    """Create sample dataset metadata."""
    return DatasetMetadata(
        name="test_dataset",
        description="Test dataset for unit tests",
        content_type="text/plain",
        size=100,
        created_at="2024-01-01T00:00:00",
        tags=["test", "sample"],
        access_level="private",
        owner_email="test@example.com"
    )

@pytest.mark.asyncio
Async def test_store_and_retrieve_content(content_repo, sample_metadata):
    """Test storing and retrieving content."""
    content = b"This is test content for the repository."
    
    # Store content
    content_id = await content_repo.store_content(
        name="test_file",
        content=content,
        metadata=sample_metadata
    )
    
    assert content_id is not None
    assert "test_file" in content_repo.content_items
    
    # Retrieve content
    retrieved_content = await content_repo.get_content("test_file")
    assert retrieved_content == content

@pytest.mark.asyncio
Async def test_content_encryption(content_repo, sample_metadata):
    """Test that content is properly encrypted in storage."""
    original_content = b"Secret content that should be encrypted"
    
    await content_repo.store_content(
        name="encrypted_test",
        content=original_content,
        metadata=sample_metadata
    )
    
    # Check that stored content is encrypted (different from original)
    content_item = content_repo.content_items["encrypted_test"]
    assert content_item.encrypted_content != original_content
    
    # But decrypted content should match original
    retrieved_content = await content_repo.get_content("encrypted_test")
    assert retrieved_content == original_content

@pytest.mark.asyncio
Async def test_search_functionality(content_repo, sample_metadata):
    """Test content search functionality."""
    # Store multiple test items
    test_items = [
        ("doc1", b"Python programming tutorial", ["python", "tutorial"]),
        ("doc2", b"Machine learning basics", ["ml", "basics"]),
        ("doc3", b"Advanced Python concepts", ["python", "advanced"]),
    ]
    
    for name, content, tags in test_items:
        metadata = DatasetMetadata(
            name=name,
            description=f"Description for {name}",
            content_type="text/plain",
            size=len(content),
            created_at="2024-01-01T00:00:00",
            tags=tags,
            access_level="private",
            owner_email="test@example.com"
        )
        await content_repo.store_content(name, content, metadata)
    
    # Test search
    results = await content_repo.search_content("python")
    assert len(results) == 2  # doc1 and doc3 should match
    
    result_names = [r["name"] for r in results]
    assert "doc1" in result_names
    assert "doc3" in result_names

@pytest.mark.asyncio
Async def test_list_datasets_with_filters(content_repo):
    """Test listing datasets with tag and content type filters."""
    # Create test datasets with different tags and content types
    test_data = [
        ("json_data", "application/json", ["data", "json"]),
        ("csv_data", "text/csv", ["data", "csv"]),
        ("text_doc", "text/plain", ["document", "text"]),
    ]
    
    for name, content_type, tags in test_data:
        metadata = DatasetMetadata(
            name=name,
            description=f"Test {content_type} data",
            content_type=content_type,
            size=100,
            created_at="2024-01-01T00:00:00",
            tags=tags,
            access_level="private",
            owner_email="test@example.com"
        )
        await content_repo.store_content(name, b"test content", metadata)
    
    # Test filtering by tags
    data_datasets = await content_repo.list_datasets(tags_filter=["data"])
    assert len(data_datasets) == 2
    assert "json_data" in data_datasets
    assert "csv_data" in data_datasets
    
    # Test filtering by content type
    json_datasets = await content_repo.list_datasets(
        content_type_filter="application/json"
    )
    assert len(json_datasets) == 1
    assert "json_data" in json_datasets

@pytest.mark.asyncio
Async def test_content_summaries(content_repo, sample_metadata):
    """Test content summary generation."""
    content = b'{"users": ["alice", "bob"], "count": 2}'
    
    metadata = DatasetMetadata(
        name="json_test",
        description="JSON test data",
        content_type="application/json",
        size=len(content),
        created_at="2024-01-01T00:00:00",
        tags=["json", "test"],
        access_level="private",
        owner_email="test@example.com"
    )
    
    await content_repo.store_content("json_test", content, metadata)
    
    # Test different summary types
    statistical_summary = await content_repo.get_content_summary(
        "json_test", "statistical"
    )
    assert statistical_summary is not None
    assert "application/json" in statistical_summary
    
    semantic_summary = await content_repo.get_content_summary(
        "json_test", "semantic"
    )
    assert semantic_summary is not None
    
    structural_summary = await content_repo.get_content_summary(
        "json_test", "structural"
    )
    assert structural_summary is not None
    assert "JSON structure" in structural_summary