"""Tests for benchmark dataset"""

import pytest
import tempfile
from pathlib import Path
from src.evaluation.benchmark import (
    BenchmarkQuery,
    BenchmarkDataset,
    create_default_benchmark,
    load_benchmark_dataset
)


class TestBenchmarkQuery:
    """Test BenchmarkQuery class"""
    
    def test_create_query(self):
        """Test creating a benchmark query"""
        query = BenchmarkQuery(
            query="Test query",
            ground_truth="Test ground truth",
            expected_sources=["https://example.com"],
            category="test",
            metadata={"difficulty": "easy"}
        )
        
        assert query.query == "Test query"
        assert query.ground_truth == "Test ground truth"
        assert len(query.expected_sources) == 1
        assert query.category == "test"
        assert query.metadata["difficulty"] == "easy"
    
    def test_to_dict(self):
        """Test converting query to dictionary"""
        query = BenchmarkQuery(
            query="Test query",
            ground_truth="Test ground truth"
        )
        
        data = query.to_dict()
        
        assert data["query"] == "Test query"
        assert data["ground_truth"] == "Test ground truth"
        assert "expected_sources" in data
    
    def test_from_dict(self):
        """Test creating query from dictionary"""
        data = {
            "query": "Test query",
            "ground_truth": "Test ground truth",
            "expected_sources": ["https://example.com"],
            "category": "test"
        }
        
        query = BenchmarkQuery.from_dict(data)
        
        assert query.query == "Test query"
        assert query.ground_truth == "Test ground truth"
        assert len(query.expected_sources) == 1
        assert query.category == "test"


class TestBenchmarkDataset:
    """Test BenchmarkDataset class"""
    
    def test_create_dataset(self):
        """Test creating a benchmark dataset"""
        queries = [
            BenchmarkQuery("Query 1", "Truth 1"),
            BenchmarkQuery("Query 2", "Truth 2"),
        ]
        
        dataset = BenchmarkDataset(queries)
        
        assert len(dataset) == 2
        assert dataset[0].query == "Query 1"
        assert dataset[1].query == "Query 2"
    
    def test_save_and_load(self):
        """Test saving and loading dataset"""
        queries = [
            BenchmarkQuery("Query 1", "Truth 1", category="test"),
            BenchmarkQuery("Query 2", "Truth 2", category="test"),
        ]
        
        dataset = BenchmarkDataset(queries)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_benchmark.json"
            
            # Save
            dataset.save(str(filepath))
            assert filepath.exists()
            
            # Load
            loaded = BenchmarkDataset.load(str(filepath))
            
            assert len(loaded) == 2
            assert loaded[0].query == "Query 1"
            assert loaded[1].query == "Query 2"
    
    def test_get_by_category(self):
        """Test getting queries by category"""
        queries = [
            BenchmarkQuery("Query 1", "Truth 1", category="seo"),
            BenchmarkQuery("Query 2", "Truth 2", category="seo"),
            BenchmarkQuery("Query 3", "Truth 3", category="email"),
        ]
        
        dataset = BenchmarkDataset(queries)
        
        seo_queries = dataset.get_by_category("seo")
        assert len(seo_queries) == 2
        
        email_queries = dataset.get_by_category("email")
        assert len(email_queries) == 1
    
    def test_get_categories(self):
        """Test getting all categories"""
        queries = [
            BenchmarkQuery("Query 1", "Truth 1", category="seo"),
            BenchmarkQuery("Query 2", "Truth 2", category="email"),
            BenchmarkQuery("Query 3", "Truth 3", category="seo"),
        ]
        
        dataset = BenchmarkDataset(queries)
        
        categories = dataset.get_categories()
        assert "seo" in categories
        assert "email" in categories
        assert len(categories) == 2


class TestDefaultBenchmark:
    """Test default benchmark dataset creation"""
    
    def test_create_default_benchmark(self):
        """Test creating default benchmark dataset"""
        dataset = create_default_benchmark()
        
        assert len(dataset) == 20
        assert all(isinstance(q, BenchmarkQuery) for q in dataset.queries)
    
    def test_default_benchmark_categories(self):
        """Test default benchmark has various categories"""
        dataset = create_default_benchmark()
        
        categories = dataset.get_categories()
        assert len(categories) > 0
    
    def test_load_default_benchmark(self):
        """Test loading default benchmark"""
        dataset = load_benchmark_dataset()
        
        assert len(dataset) == 20
        assert all(q.query for q in dataset.queries)
        assert all(q.ground_truth for q in dataset.queries)
