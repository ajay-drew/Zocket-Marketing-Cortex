"""Evaluation metrics for agent responses"""

import re
from typing import List, Dict, Any, Optional
import logging

try:
    from bert_score import score as bert_score
    BERTSCORE_AVAILABLE = True
except ImportError:
    BERTSCORE_AVAILABLE = False
    logging.warning("bert-score not installed. Relevance metric will use fallback method.")

logger = logging.getLogger(__name__)


class EvaluationMetrics:
    """Evaluation metrics for agent responses"""
    
    def __init__(self, use_bert_score: bool = True):
        """
        Initialize evaluation metrics
        
        Args:
            use_bert_score: Whether to use BERTScore for relevance (requires bert-score package)
        """
        self.use_bert_score = use_bert_score and BERTSCORE_AVAILABLE
        if use_bert_score and not BERTSCORE_AVAILABLE:
            logger.warning("BERTScore not available. Using fallback semantic similarity.")
    
    def extract_citations(self, text: str) -> List[str]:
        """
        Extract URLs from response text
        
        Args:
            text: Response text to extract citations from
            
        Returns:
            List of URLs found in the text
        """
        url_pattern = r'(https?://[^\s\)]+)'
        matches = re.findall(url_pattern, text)
        # Clean up URLs (remove trailing punctuation)
        cleaned_urls = [url.rstrip('.,;:!?)') for url in matches]
        return cleaned_urls
    
    def calculate_citation_accuracy(
        self, 
        response: str, 
        expected_sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Calculate citation accuracy metrics
        
        Args:
            response: Agent response text
            expected_sources: Optional list of expected source URLs
            
        Returns:
            Dictionary with citation accuracy metrics
        """
        citations = self.extract_citations(response)
        
        metrics = {
            "citation_count": len(citations),
            "has_citations": len(citations) > 0,
            "citations": citations,
        }
        
        # If expected sources provided, calculate precision/recall
        if expected_sources:
            expected_set = set(expected_sources)
            found_set = set(citations)
            
            # Precision: citations that are in expected sources
            if len(found_set) > 0:
                precision = len(found_set & expected_set) / len(found_set)
            else:
                precision = 0.0
            
            # Recall: expected sources that were cited
            if len(expected_set) > 0:
                recall = len(found_set & expected_set) / len(expected_set)
            else:
                recall = 0.0
            
            # F1 score
            if precision + recall > 0:
                f1 = 2 * (precision * recall) / (precision + recall)
            else:
                f1 = 0.0
            
            metrics.update({
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "expected_sources": expected_sources,
            })
        
        # Citation coverage: percentage of response that has citations
        # Simple heuristic: if response has citations, consider it covered
        metrics["citation_coverage"] = 1.0 if len(citations) > 0 else 0.0
        
        return metrics
    
    def calculate_relevance(
        self, 
        response: str, 
        ground_truth: str
    ) -> Dict[str, Any]:
        """
        Calculate relevance score using BERTScore or fallback method
        
        Args:
            response: Agent response text
            ground_truth: Expected/ideal response text
            
        Returns:
            Dictionary with relevance metrics
        """
        if self.use_bert_score:
            try:
                # BERTScore calculation
                P, R, F1 = bert_score(
                    [response],
                    [ground_truth],
                    lang='en',
                    verbose=False,
                    device='cpu'  # Use CPU for compatibility
                )
                
                return {
                    "relevance_score": float(F1[0].item()),
                    "precision": float(P[0].item()),
                    "recall": float(R[0].item()),
                    "method": "bert_score",
                }
            except Exception as e:
                logger.warning(f"BERTScore calculation failed: {e}. Using fallback.")
                return self._calculate_relevance_fallback(response, ground_truth)
        else:
            return self._calculate_relevance_fallback(response, ground_truth)
    
    def _calculate_relevance_fallback(
        self, 
        response: str, 
        ground_truth: str
    ) -> Dict[str, Any]:
        """
        Fallback relevance calculation using simple word overlap
        
        Args:
            response: Agent response text
            ground_truth: Expected/ideal response text
            
        Returns:
            Dictionary with relevance metrics
        """
        # Simple word-based similarity (Jaccard similarity)
        response_words = set(response.lower().split())
        ground_truth_words = set(ground_truth.lower().split())
        
        if len(ground_truth_words) == 0:
            return {
                "relevance_score": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "method": "word_overlap",
            }
        
        intersection = response_words & ground_truth_words
        union = response_words | ground_truth_words
        
        if len(union) > 0:
            jaccard = len(intersection) / len(union)
        else:
            jaccard = 0.0
        
        # Precision: relevant words in response
        if len(response_words) > 0:
            precision = len(intersection) / len(response_words)
        else:
            precision = 0.0
        
        # Recall: relevant words found
        recall = len(intersection) / len(ground_truth_words)
        
        return {
            "relevance_score": jaccard,
            "precision": precision,
            "recall": recall,
            "method": "word_overlap",
        }
    
    def evaluate(
        self,
        response: str,
        ground_truth: str,
        expected_sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive evaluation of agent response
        
        Args:
            response: Agent response text
            ground_truth: Expected/ideal response text
            expected_sources: Optional list of expected source URLs
            
        Returns:
            Dictionary with all evaluation metrics
        """
        relevance_metrics = self.calculate_relevance(response, ground_truth)
        citation_metrics = self.calculate_citation_accuracy(response, expected_sources)
        
        # Overall score (weighted combination)
        relevance_weight = 0.7
        citation_weight = 0.3
        
        citation_score = citation_metrics.get("citation_coverage", 0.0)
        if expected_sources and "f1" in citation_metrics:
            citation_score = citation_metrics["f1"]
        
        overall_score = (
            relevance_metrics["relevance_score"] * relevance_weight +
            citation_score * citation_weight
        )
        
        return {
            "overall_score": overall_score,
            "relevance": relevance_metrics,
            "citation_accuracy": citation_metrics,
            "meets_threshold": (
                relevance_metrics["relevance_score"] >= 0.85 and
                citation_metrics["has_citations"]
            ),
        }


def evaluate_response(
    response: str,
    ground_truth: str,
    expected_sources: Optional[List[str]] = None,
    use_bert_score: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a single response
    
    Args:
        response: Agent response text
        ground_truth: Expected/ideal response text
        expected_sources: Optional list of expected source URLs
        use_bert_score: Whether to use BERTScore for relevance
        
    Returns:
        Dictionary with evaluation metrics
    """
    metrics = EvaluationMetrics(use_bert_score=use_bert_score)
    return metrics.evaluate(response, ground_truth, expected_sources)
