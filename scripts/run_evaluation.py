"""Script to run evaluation on benchmark dataset"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.runner import run_evaluation


def main():
    """Main entry point for evaluation script"""
    parser = argparse.ArgumentParser(
        description="Run evaluation on benchmark dataset for Marketing Strategy Advisor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default dataset and settings
  python scripts/run_evaluation.py
  
  # Use custom dataset
  python scripts/run_evaluation.py --dataset data/custom_benchmark.json
  
  # Custom output path
  python scripts/run_evaluation.py --output results/my_evaluation.json
  
  # Disable BERTScore (use fallback method)
  python scripts/run_evaluation.py --no-bert-score
  
  # Increase concurrency (faster but may hit rate limits)
  python scripts/run_evaluation.py --max-concurrent 5
        """
    )
    
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to benchmark dataset JSON file (default: uses built-in 20-query dataset)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save evaluation results JSON (default: evaluation_results.json)"
    )
    
    parser.add_argument(
        "--no-bert-score",
        action="store_true",
        help="Disable BERTScore and use fallback semantic similarity method"
    )
    
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent evaluations (default: 3, recommended: 1-5)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    import logging
    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format='%(levelname)s - %(message)s'
        )
    
    # Set UTF-8 encoding for Windows console
    import sys
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print("="*60)
    print("Marketing Strategy Advisor - Fast Evaluation Runner")
    print("="*60)
    print(f"Dataset: {args.dataset or 'Default (20 queries)'}")
    print(f"Output: {args.output or 'evaluation_results.json'}")
    print(f"Metrics: Relevance (Word Overlap) + ROUGE (No LLM Judge)")
    print(f"Max Concurrent: {args.max_concurrent}")
    print("="*60)
    print()
    print("Note: This evaluation uses Groq API for agent responses.")
    print("   Metrics are calculated using fast rule-based methods (no LLM judge).")
    print("   Consider using --max-concurrent 1 for slower but more reliable execution.")
    print()
    
    try:
        # Run evaluation
        results = asyncio.run(run_evaluation(
            dataset_path=args.dataset,
            output_path=args.output,
            use_bert_score=not args.no_bert_score,
            max_concurrent=args.max_concurrent
        ))
        
        # Exit with appropriate code
        summary = results.get("summary", {})
        success_rate = summary.get("success_rate", 0.0)
        
        if success_rate < 0.5:
            print("\nWarning: Less than 50% of evaluations succeeded!")
            sys.exit(1)
        elif success_rate < 0.8:
            print("\nWarning: Some evaluations failed. Review results.")
            sys.exit(0)
        else:
            print("\nEvaluation completed successfully!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\nEvaluation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError running evaluation: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
