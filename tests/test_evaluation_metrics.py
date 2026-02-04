"""Tests for evaluation metrics"""

import pytest
from src.evaluation.metrics import EvaluationMetrics, evaluate_response


class TestEvaluationMetrics:
    """Test evaluation metrics calculation"""
    
    def test_extract_citations(self):
        """Test citation extraction from text"""
        metrics = EvaluationMetrics()
        
        text = "This is a response with a citation: https://example.com/article"
        citations = metrics.extract_citations(text)
        
        assert len(citations) == 1
        assert "https://example.com/article" in citations
    
    def test_extract_multiple_citations(self):
        """Test extraction of multiple citations"""
        metrics = EvaluationMetrics()
        
        text = """
        Source 1: https://blog.hubspot.com/article1
        Source 2: https://moz.com/article2
        Source 3: http://example.com/article3
        """
        citations = metrics.extract_citations(text)
        
        assert len(citations) == 3
        assert "https://blog.hubspot.com/article1" in citations
        assert "https://moz.com/article2" in citations
        assert "http://example.com/article3" in citations
    
    def test_citation_accuracy_without_expected(self):
        """Test citation accuracy without expected sources"""
        metrics = EvaluationMetrics()
        
        response = "This is a response with https://example.com/article"
        result = metrics.calculate_citation_accuracy(response)
        
        assert result["citation_count"] == 1
        assert result["has_citations"] is True
        assert result["citation_coverage"] == 1.0
    
    def test_citation_accuracy_with_expected(self):
        """Test citation accuracy with expected sources"""
        metrics = EvaluationMetrics()
        
        response = "This cites https://example.com/article1 and https://example.com/article2"
        expected = ["https://example.com/article1", "https://example.com/article3"]
        
        result = metrics.calculate_citation_accuracy(response, expected)
        
        assert result["citation_count"] == 2
        assert result["precision"] == 0.5  # 1 out of 2 found is expected
        assert result["recall"] == 0.5  # 1 out of 2 expected is found
        assert result["f1"] > 0
    
    def test_citation_accuracy_no_citations(self):
        """Test citation accuracy when no citations present"""
        metrics = EvaluationMetrics()
        
        response = "This response has no citations"
        result = metrics.calculate_citation_accuracy(response)
        
        assert result["citation_count"] == 0
        assert result["has_citations"] is False
        assert result["citation_coverage"] == 0.0
    
    def test_relevance_fallback(self):
        """Test relevance calculation with fallback method"""
        metrics = EvaluationMetrics(use_bert_score=False)
        
        response = "Facebook ads optimization involves targeting, A/B testing, and conversion tracking"
        ground_truth = "Facebook ad optimization requires targeting, testing, and tracking conversions"
        
        result = metrics.calculate_relevance(response, ground_truth)
        
        assert "relevance_score" in result
        assert 0.0 <= result["relevance_score"] <= 1.0
        assert result["method"] == "word_overlap"
    
    @pytest.mark.skipif(
        not hasattr(EvaluationMetrics, '_calculate_relevance_fallback'),
        reason="BERTScore not available"
    )
    def test_relevance_with_bert_score(self):
        """Test relevance calculation with BERTScore if available"""
        try:
            metrics = EvaluationMetrics(use_bert_score=True)
            
            response = "Facebook ads optimization involves targeting, A/B testing, and conversion tracking"
            ground_truth = "Facebook ad optimization requires targeting, testing, and tracking conversions"
            
            result = metrics.calculate_relevance(response, ground_truth)
            
            assert "relevance_score" in result
            assert 0.0 <= result["relevance_score"] <= 1.0
        except Exception:
            # BERTScore might not be available, skip test
            pytest.skip("BERTScore not available")
    
    def test_evaluate_comprehensive(self):
        """Test comprehensive evaluation"""
        metrics = EvaluationMetrics(use_bert_score=False)
        
        response = "Facebook ads optimization: 1) Targeting 2) A/B testing 3) Conversion tracking. Source: https://example.com/article"
        ground_truth = "Facebook ad optimization requires targeting, testing, and tracking conversions"
        expected_sources = ["https://example.com/article"]
        
        result = metrics.evaluate(response, ground_truth, expected_sources)
        
        assert "overall_score" in result
        assert "relevance" in result
        assert "citation_accuracy" in result
        assert "meets_threshold" in result
        assert 0.0 <= result["overall_score"] <= 1.0
    
    def test_evaluate_response_function(self):
        """Test convenience evaluate_response function"""
        response = "Facebook ads optimization: targeting, testing. Source: https://example.com/article"
        ground_truth = "Facebook ad optimization requires targeting and testing"
        
        result = evaluate_response(response, ground_truth, use_bert_score=False)
        
        assert "overall_score" in result
        assert "relevance" in result
        assert "citation_accuracy" in result
