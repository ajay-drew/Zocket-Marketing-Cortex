"""Fast evaluation metrics for agent responses: Relevance and ROUGE (no LLM judge)"""

import re
from typing import Dict, Any, Optional
import logging

try:
    from rouge_score import rouge_scorer
    ROUGE_AVAILABLE = True
except ImportError:
    ROUGE_AVAILABLE = False
    logging.warning("rouge-score not installed. ROUGE metrics will not be available.")

logger = logging.getLogger(__name__)


class EvaluationMetrics:
    """Fast evaluation metrics for agent responses - no LLM judge"""
    
    def __init__(self, use_bert_score: bool = False):
        """
        Initialize evaluation metrics
        
        Args:
            use_bert_score: Whether to use BERTScore (slower). Default False for speed.
        """
        self.use_bert_score = False  # Always use fast word overlap for speed
        
        # Initialize ROUGE scorer
        if ROUGE_AVAILABLE:
            self.rouge_scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
        else:
            self.rouge_scorer = None
            logger.warning("ROUGE scorer not available. Install rouge-score package.")
    
    def calculate_relevance(
        self, 
        response: str, 
        ground_truth: str
    ) -> Dict[str, Any]:
        """
        Calculate relevance score using fast word overlap (no LLM)
        
        Args:
            response: Agent response text
            ground_truth: Expected/ideal response text
            
        Returns:
            Dictionary with relevance metrics
        """
        # Fast word-based similarity (Jaccard similarity)
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
    
    def calculate_rouge_scores(
        self,
        response: str,
        ground_truth: str
    ) -> Dict[str, Any]:
        """
        Calculate ROUGE scores for summary evaluation (fast, no LLM)
        
        Args:
            response: Agent response text (summary)
            ground_truth: Expected/ideal response text (reference summary)
            
        Returns:
            Dictionary with ROUGE metrics (ROUGE-1, ROUGE-2, ROUGE-L)
        """
        if not self.rouge_scorer:
            return {
                "rouge1": {"f": 0.0, "p": 0.0, "r": 0.0},
                "rouge2": {"f": 0.0, "p": 0.0, "r": 0.0},
                "rougeL": {"f": 0.0, "p": 0.0, "r": 0.0},
                "available": False,
            }
        
        try:
            scores = self.rouge_scorer.score(ground_truth, response)
            
            return {
                "rouge1": {
                    "f": scores['rouge1'].fmeasure,
                    "p": scores['rouge1'].precision,
                    "r": scores['rouge1'].recall,
                },
                "rouge2": {
                    "f": scores['rouge2'].fmeasure,
                    "p": scores['rouge2'].precision,
                    "r": scores['rouge2'].recall,
                },
                "rougeL": {
                    "f": scores['rougeL'].fmeasure,
                    "p": scores['rougeL'].precision,
                    "r": scores['rougeL'].recall,
                },
                "available": True,
            }
        except Exception as e:
            logger.warning(f"ROUGE calculation failed: {e}")
            return {
                "rouge1": {"f": 0.0, "p": 0.0, "r": 0.0},
                "rouge2": {"f": 0.0, "p": 0.0, "r": 0.0},
                "rougeL": {"f": 0.0, "p": 0.0, "r": 0.0},
                "available": False,
                "error": str(e),
            }
    
    def evaluate(
        self,
        response: str,
        ground_truth: str,
        expected_sources: Optional[list] = None,
        response_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Fast evaluation using only Relevance and ROUGE (no LLM judge)
        
        Args:
            response: Agent response text
            ground_truth: Expected/ideal response text
            expected_sources: Optional (not used)
            response_time: Optional response time in seconds
            
        Returns:
            Dictionary with evaluation metrics
        """
        # Calculate both metrics
        relevance_metrics = self.calculate_relevance(response, ground_truth)
        rouge_metrics = self.calculate_rouge_scores(response, ground_truth)
        
        result = {
            "relevance": relevance_metrics,
            "rouge": rouge_metrics,
        }
        
        if response_time is not None:
            result["response_time"] = response_time
        
        return result


def evaluate_response(
    response: str,
    ground_truth: str,
    expected_sources: Optional[list] = None,
    use_bert_score: bool = False,
    response_time: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a single response
    
    Args:
        response: Agent response text
        ground_truth: Expected/ideal response text
        expected_sources: Optional (not used)
        use_bert_score: Whether to use BERTScore (ignored, always uses fast method)
        response_time: Optional response time in seconds
        
    Returns:
        Dictionary with evaluation metrics
    """
    metrics = EvaluationMetrics(use_bert_score=False)
    return metrics.evaluate(response, ground_truth, expected_sources, response_time=response_time)
