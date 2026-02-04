"""Script to run evaluation on benchmark dataset"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.runner import run_evaluation

if __name__ == "__main__":
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else None
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    asyncio.run(run_evaluation(dataset_path, output_path))
