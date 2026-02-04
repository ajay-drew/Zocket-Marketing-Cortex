"""Evaluation runner for benchmark dataset"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

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
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate agent response on a single query
        
        Args:
            benchmark_query: Benchmark query with ground truth
            session_id: Optional session ID for agent memory
            
        Returns:
            Dictionary with evaluation results
        """
        query = benchmark_query.query
        ground_truth = benchmark_query.ground_truth
        expected_sources = benchmark_query.expected_sources
        
        logger.info(f"Evaluating query: {query[:50]}...")
        
        try:
            # Get agent response
            response_result = await self.agent.run_agent(
                query=query,
                session_id=session_id or f"eval_{datetime.now().timestamp()}"
            )
            
            response = response_result.get("response", "")
            
            # Evaluate response
            evaluation = self.metrics.evaluate(
                response=response,
                ground_truth=ground_truth,
                expected_sources=expected_sources
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
    
    async def evaluate_dataset(
        self,
        dataset: BenchmarkDataset,
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        Evaluate agent on entire benchmark dataset
        
        Args:
            dataset: Benchmark dataset
            max_concurrent: Maximum concurrent evaluations
            
        Returns:
            Dictionary with evaluation results and summary statistics
        """
        logger.info(f"Starting evaluation on {len(dataset)} queries")
        
        # Evaluate queries with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def evaluate_with_limit(query: BenchmarkQuery):
            async with semaphore:
                return await self.evaluate_query(query)
        
        tasks = [evaluate_with_limit(query) for query in dataset.queries]
        results = await asyncio.gather(*tasks)
        
        # Calculate summary statistics
        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]
        
        if successful_results:
            relevance_scores = [
                r["evaluation"]["relevance"]["relevance_score"]
                for r in successful_results
            ]
            citation_coverages = [
                r["evaluation"]["citation_accuracy"]["citation_coverage"]
                for r in successful_results
            ]
            overall_scores = [
                r["evaluation"]["overall_score"]
                for r in successful_results
            ]
            meets_threshold = [
                r["evaluation"]["meets_threshold"]
                for r in successful_results
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
                    "threshold_met": sum(1 for s in relevance_scores if s >= 0.85) / len(relevance_scores),
                },
                "citation_accuracy": {
                    "mean_coverage": sum(citation_coverages) / len(citation_coverages),
                    "has_citations_rate": sum(1 for c in citation_coverages if c > 0) / len(citation_coverages),
                },
                "overall": {
                    "mean_score": sum(overall_scores) / len(overall_scores),
                    "min": min(overall_scores),
                    "max": max(overall_scores),
                },
                "threshold_met_rate": sum(meets_threshold) / len(meets_threshold),
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
    
    # Create runner
    runner = EvaluationRunner(use_bert_score=use_bert_score)
    
    # Run evaluation
    results = await runner.evaluate_dataset(dataset, max_concurrent=max_concurrent)
    
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
        print(f"\nRelevance Score:")
        print(f"  Mean: {summary['relevance']['mean']:.3f}")
        print(f"  Range: {summary['relevance']['min']:.3f} - {summary['relevance']['max']:.3f}")
        print(f"  Threshold Met (>=0.85): {summary['relevance']['threshold_met']:.2%}")
        
        print(f"\nCitation Accuracy:")
        print(f"  Mean Coverage: {summary['citation_accuracy']['mean_coverage']:.3f}")
        print(f"  Has Citations Rate: {summary['citation_accuracy']['has_citations_rate']:.2%}")
        
        print(f"\nOverall Score:")
        print(f"  Mean: {summary['overall']['mean_score']:.3f}")
        print(f"  Range: {summary['overall']['min']:.3f} - {summary['overall']['max']:.3f}")
        print(f"  Threshold Met Rate: {summary['threshold_met_rate']:.2%}")
    
    print(f"\nResults saved to: {output_path}")
    print("="*60)
    
    return results


if __name__ == "__main__":
    # Run evaluation from command line
    import sys
    
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else None
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    asyncio.run(run_evaluation(dataset_path, output_path))
