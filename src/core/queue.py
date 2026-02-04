"""
Simple request queue manager for parallel processing with concurrency control
"""
from typing import Callable, Any, Optional, List, Dict
import asyncio
import logging

logger = logging.getLogger(__name__)


class ParallelProcessor:
    """
    Utility class for parallel processing with concurrency limits
    """
    
    @staticmethod
    async def process_parallel(
        items: List[Any],
        processor: Callable[[Any], Any],
        max_concurrent: int = 5,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> List[Any]:
        """
        Process items in parallel with concurrency control
        
        Args:
            items: List of items to process
            processor: Async function to process each item
            max_concurrent: Maximum concurrent operations
            batch_size: Process in batches (None = process all at once)
            progress_callback: Optional progress callback
            
        Returns:
            List of results (same order as items)
        """
        if not items:
            return []
        
        semaphore = asyncio.Semaphore(max_concurrent)
        total = len(items)
        completed = 0
        
        async def process_with_limit(item: Any, index: int) -> tuple[int, Any]:
            """Process item with concurrency limit"""
            async with semaphore:
                try:
                    result = await processor(item)
                    nonlocal completed
                    completed += 1
                    
                    if progress_callback:
                        await progress_callback({
                            "completed": completed,
                            "total": total,
                            "progress": int((completed / total) * 100) if total > 0 else 0,
                            "current": index + 1
                        })
                    
                    return (index, result)
                except Exception as e:
                    logger.error(f"Error processing item {index}: {e}")
                    return (index, None)
        
        # Process all items
        tasks = [process_with_limit(item, i) for i, item in enumerate(items)]
        
        # If batch_size is specified, process in batches
        if batch_size:
            results = [None] * total
            for i in range(0, total, batch_size):
                batch = tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                
                for idx, result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Exception in batch processing: {result}")
                        results[idx] = None
                    else:
                        results[idx] = result[1] if isinstance(result, tuple) else result
        else:
            # Process all at once
            results = [None] * total
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in gathered:
                if isinstance(result, Exception):
                    logger.error(f"Exception in parallel processing: {result}")
                elif isinstance(result, tuple):
                    idx, value = result
                    results[idx] = value
        
        return results
