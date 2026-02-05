"""Evaluation runner for benchmark dataset"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import json
from datetime import datetime

try:
    import groq
except ImportError:
    groq = None

from .metrics import EvaluationMetrics
from .benchmark import BenchmarkDataset, BenchmarkQuery, load_benchmark_dataset
from ..agents.marketing_strategy_advisor import MarketingStrategyAdvisor

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Runner for evaluating agent on benchmark dataset"""
    
    def __init__(
        self,
        agent: Optional[MarketingStrategyAdvisor] = None,
        use_bert_score: bool = True
    ):
        """
        Initialize evaluation runner
        
        Args:
            agent: MarketingStrategyAdvisor instance. If None, creates new instance.
            use_bert_score: Whether to use BERTScore for relevance
        """
        self.agent = agent or MarketingStrategyAdvisor()
        self.metrics = EvaluationMetrics(use_bert_score=use_bert_score)
    
    async def evaluate_query(
        self,
        benchmark_query: BenchmarkQuery,
        session_id: Optional[str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Evaluate agent response on a single query with retry logic for rate limits
        
        Args:
            benchmark_query: Benchmark query with ground truth
            session_id: Optional session ID for agent memory
            max_retries: Maximum retry attempts for rate limit errors
            
        Returns:
            Dictionary with evaluation results
        """
        query = benchmark_query.query
        ground_truth = benchmark_query.ground_truth
        expected_sources = benchmark_query.expected_sources
        
        logger.info(f"Evaluating query: {query[:50]}...")
        
        # Retry logic for rate limit errors
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # Get agent response with timing
                import time
                start_time = time.time()
                response = await self.agent.get_response(
                    query=query,
                    session_id=session_id or f"eval_{datetime.now().timestamp()}"
                )
                response_time = time.time() - start_time
                
                # Evaluate response
                evaluation = self.metrics.evaluate(
                    response=response,
                    ground_truth=ground_truth,
                    expected_sources=expected_sources,
                    response_time=response_time
                )
                
                return {
                    "query": query,
                    "response": response,
                    "ground_truth": ground_truth,
                    "evaluation": evaluation,
                    "category": benchmark_query.category,
                    "metadata": benchmark_query.metadata,
                    "success": True,
                }
            except Exception as e:
                # Check if it's a rate limit error (Groq or other)
                is_rate_limit = False
                if groq and isinstance(e, groq.RateLimitError):
                    is_rate_limit = True
                elif "rate limit" in str(e).lower() or "429" in str(e) or "RateLimitError" in str(type(e)):
                    is_rate_limit = True
                
                if is_rate_limit:
                    last_error = e
                    error_str = str(e)
                    
                    # Extract retry-after time from error message
                    retry_after = None
                    retry_match = re.search(r'Please try again in ([\d.]+)s', error_str)
                    if retry_match:
                        retry_after = float(retry_match.group(1))
                    else:
                        # Exponential backoff: 30s, 60s, 120s
                        retry_after = 30 * (2 ** (attempt - 1))
                    
                    # Cap at 5 minutes
                    retry_after = min(retry_after, 300)
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Rate limit hit (attempt {attempt}/{max_retries}) for query '{query[:50]}...'. "
                            f"Retrying after {retry_after:.1f}s..."
                        )
                        await asyncio.sleep(retry_after)
                    else:
                        logger.error(
                            f"Rate limit error after {max_retries} attempts for query '{query[:50]}...'"
                        )
                        break
                else:
                    # Non-rate-limit errors: log and return failure immediately
                    logger.error(f"Error evaluating query '{query}': {e}", exc_info=True)
                    return {
                        "query": query,
                        "response": "",
                        "ground_truth": ground_truth,
                        "evaluation": None,
                        "category": benchmark_query.category,
                        "metadata": benchmark_query.metadata,
                        "success": False,
                        "error": str(e),
                    }
        
        # All retries exhausted for rate limit
        return {
            "query": query,
            "response": "",
            "ground_truth": ground_truth,
            "evaluation": None,
            "category": benchmark_query.category,
            "metadata": benchmark_query.metadata,
            "success": False,
            "error": f"Rate limit error after {max_retries} attempts: {str(last_error)}",
        }
    
    async def evaluate_dataset(
        self,
        dataset: BenchmarkDataset,
        max_concurrent: int = 3,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate agent on entire benchmark dataset
        
        Args:
            dataset: Benchmark dataset
            max_concurrent: Maximum concurrent evaluations
            progress_callback: Optional callback function(completed, total, current_query)
            
        Returns:
            Dictionary with evaluation results and summary statistics
        """
        total = len(dataset.queries)
        logger.info(f"Starting evaluation on {total} queries")
        
        # Evaluate queries with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        completed = 0
        
        async def evaluate_with_limit(query: BenchmarkQuery, index: int):
            async with semaphore:
                # Add delay between evaluations to avoid rate limits
                # Stagger evaluations: 0s, 2s, 4s, etc. for first 3, then 1s between
                if index > 0:
                    delay = 2.0 if index < 3 else 1.0
                    await asyncio.sleep(delay)
                
                result = await self.evaluate_query(query, max_retries=3)
                nonlocal completed
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, total, query.query)
                
                return result
        
        tasks = [evaluate_with_limit(query, i) for i, query in enumerate(dataset.queries)]
        results = await asyncio.gather(*tasks)
        
        # Calculate summary statistics
        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]
        
        if successful_results:
            # Extract metrics for each evaluation (only Relevance and ROUGE)
            relevance_scores = [
                r["evaluation"]["relevance"]["relevance_score"]
                for r in successful_results
            ]
            rouge1_scores = [
                r["evaluation"]["rouge"]["rouge1"]["f"]
                for r in successful_results
                if r["evaluation"]["rouge"].get("available", False)
            ]
            rouge2_scores = [
                r["evaluation"]["rouge"]["rouge2"]["f"]
                for r in successful_results
                if r["evaluation"]["rouge"].get("available", False)
            ]
            rougeL_scores = [
                r["evaluation"]["rouge"]["rougeL"]["f"]
                for r in successful_results
                if r["evaluation"]["rouge"].get("available", False)
            ]
            
            # Extract response times if available
            response_times = [
                r["evaluation"].get("response_time")
                for r in successful_results
                if r["evaluation"].get("response_time") is not None
            ]
            
            summary = {
                "total_queries": len(dataset),
                "successful": len(successful_results),
                "failed": len(failed_results),
                "success_rate": len(successful_results) / len(dataset),
                "relevance": {
                    "mean": sum(relevance_scores) / len(relevance_scores),
                    "min": min(relevance_scores),
                    "max": max(relevance_scores),
                },
                "rouge": {
                    "rouge1": {
                        "mean": sum(rouge1_scores) / len(rouge1_scores) if rouge1_scores else 0.0,
                        "min": min(rouge1_scores) if rouge1_scores else 0.0,
                        "max": max(rouge1_scores) if rouge1_scores else 0.0,
                    },
                    "rouge2": {
                        "mean": sum(rouge2_scores) / len(rouge2_scores) if rouge2_scores else 0.0,
                        "min": min(rouge2_scores) if rouge2_scores else 0.0,
                        "max": max(rouge2_scores) if rouge2_scores else 0.0,
                    },
                    "rougeL": {
                        "mean": sum(rougeL_scores) / len(rougeL_scores) if rougeL_scores else 0.0,
                        "min": min(rougeL_scores) if rougeL_scores else 0.0,
                        "max": max(rougeL_scores) if rougeL_scores else 0.0,
                    },
                    "available_count": len(rouge1_scores),
                },
            }
            
            # Add response time statistics if available
            if response_times:
                summary["response_time"] = {
                    "mean": sum(response_times) / len(response_times),
                    "min": min(response_times),
                    "max": max(response_times),
                }
        else:
            summary = {
                "total_queries": len(dataset),
                "successful": 0,
                "failed": len(failed_results),
                "success_rate": 0.0,
                "error": "All evaluations failed",
            }
        
        return {
            "summary": summary,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def save_results(self, results: Dict[str, Any], filepath: str) -> None:
        """Save evaluation results to JSON file"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved evaluation results to {filepath}")


async def run_evaluation(
    dataset_path: Optional[str] = None,
    output_path: Optional[str] = None,
    use_bert_score: bool = True,
    max_concurrent: int = 3
) -> Dict[str, Any]:
    """
    Run evaluation on benchmark dataset
    
    Args:
        dataset_path: Path to benchmark dataset JSON. If None, uses default dataset.
        output_path: Path to save results. If None, saves to evaluation_results.json
        use_bert_score: Whether to use BERTScore for relevance
        max_concurrent: Maximum concurrent evaluations
        
    Returns:
        Evaluation results dictionary
    """
    # Load dataset
    dataset = load_benchmark_dataset(dataset_path)
    total = len(dataset.queries)
    
    # Progress callback
    def progress_callback(completed: int, total: int, current_query: str):
        percentage = int((completed / total) * 100) if total > 0 else 0
        print(f"\r[{completed}/{total}] ({percentage}%) Evaluating: {current_query[:60]}...", end="", flush=True)
    
    # Create runner
    runner = EvaluationRunner(use_bert_score=use_bert_score)
    
    print(f"Starting evaluation of {total} queries...")
    print()
    
    # Run evaluation
    results = await runner.evaluate_dataset(
        dataset, 
        max_concurrent=max_concurrent,
        progress_callback=progress_callback
    )
    
    print()  # New line after progress updates
    
    # Save results
    if output_path is None:
        output_path = "evaluation_results.json"
    
    runner.save_results(results, output_path)
    
    # Print summary
    summary = results["summary"]
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Total Queries: {summary['total_queries']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    
    if "relevance" in summary:
        print(f"\nRelevance Score (Word Overlap - Fast):")
        print(f"  Mean: {summary['relevance']['mean']:.3f}")
        print(f"  Range: {summary['relevance']['min']:.3f} - {summary['relevance']['max']:.3f}")
        
        print(f"\nROUGE Scores for Summaries (Fast):")
        if summary['rouge']['available_count'] > 0:
            print(f"  ROUGE-1 F1: {summary['rouge']['rouge1']['mean']:.3f} (Range: {summary['rouge']['rouge1']['min']:.3f} - {summary['rouge']['rouge1']['max']:.3f})")
            print(f"  ROUGE-2 F1: {summary['rouge']['rouge2']['mean']:.3f} (Range: {summary['rouge']['rouge2']['min']:.3f} - {summary['rouge']['rouge2']['max']:.3f})")
            print(f"  ROUGE-L F1: {summary['rouge']['rougeL']['mean']:.3f} (Range: {summary['rouge']['rougeL']['min']:.3f} - {summary['rouge']['rougeL']['max']:.3f})")
            print(f"  Available for {summary['rouge']['available_count']}/{summary['successful']} queries")
        else:
            print(f"  ROUGE scores not available (rouge-score package may not be installed)")
        
        if "response_time" in summary:
            print(f"\nResponse Time:")
            print(f"  Mean: {summary['response_time']['mean']:.2f}s")
            print(f"  Range: {summary['response_time']['min']:.2f}s - {summary['response_time']['max']:.2f}s")
    
    print(f"\nResults saved to: {output_path}")
    print("="*60)
    
    return results


if __name__ == "__main__":
    # Run evaluation from command line
    import sys
    
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else None
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    asyncio.run(run_evaluation(dataset_path, output_path))
