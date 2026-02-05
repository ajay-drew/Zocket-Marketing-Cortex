"""
Blog Ingestion Queue Manager
Queues blog ingestion requests and processes them sequentially with rate limiting
"""
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BlogIngestionTask:
    """Blog ingestion task"""
    blog_name: str
    feed_url: str
    max_posts: int
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class BlogIngestionQueue:
    """
    Queue manager for blog ingestion requests
    
    Processes blogs sequentially to avoid rate limits
    """
    
    def __init__(self):
        """Initialize blog ingestion queue"""
        self._queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
        self._current_task: Optional[BlogIngestionTask] = None
        self._lock = asyncio.Lock()
        logger.info("Blog Ingestion Queue initialized")
    
    async def add_task(
        self,
        blog_name: str,
        feed_url: str,
        max_posts: int = 50,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    ) -> int:
        """
        Add a blog ingestion task to the queue
        
        Args:
            blog_name: Name of the blog
            feed_url: RSS feed URL
            max_posts: Maximum posts to ingest
            progress_callback: Optional progress callback
            
        Returns:
            Queue position (0 = currently processing, 1 = next, etc.)
        """
        task = BlogIngestionTask(
            blog_name=blog_name,
            feed_url=feed_url,
            max_posts=max_posts,
            progress_callback=progress_callback
        )
        
        await self._queue.put(task)
        queue_size = self._queue.qsize()
        
        logger.info(
            f"Added blog ingestion task to queue: {blog_name} "
            f"(Queue position: {queue_size})"
        )
        
        # Start processing if not already running
        if not self._processing:
            asyncio.create_task(self._process_queue())
        
        return queue_size
    
    async def _process_queue(self):
        """Process queued blog ingestion tasks sequentially"""
        async with self._lock:
            if self._processing:
                return
            self._processing = True
        
        logger.info("Blog ingestion queue processor started")
        
        try:
            while True:
                try:
                    # Get next task (with timeout to allow checking if queue is empty)
                    task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Queue is empty, check if we should continue
                    if self._queue.empty():
                        logger.info("Blog ingestion queue is empty, stopping processor")
                        break
                    continue
                
                self._current_task = task
                queue_position = self._queue.qsize()
                
                logger.info("")
                logger.info("=" * 70)
                logger.info(f"Processing blog from queue: {task.blog_name}")
                logger.info(f"  URL: {task.feed_url}")
                logger.info(f"  Max Posts: {task.max_posts}")
                logger.info(f"  Queue Position: Processing now (was {queue_position + 1})")
                logger.info("-" * 70)
                
                try:
                    # Import here to avoid circular imports
                    from src.integrations.blog_ingestion import BlogIngestionClient
                    
                    client = BlogIngestionClient()
                    result = await client.ingest_blog(
                        blog_name=task.blog_name,
                        feed_url=task.feed_url,
                        max_posts=task.max_posts,
                        progress_callback=task.progress_callback
                    )
                    
                    status_emoji = "✅" if result.get("status") == "success" else "❌"
                    logger.info(f"{status_emoji} Completed: {task.blog_name}")
                    logger.info(f"   Posts: {result.get('posts_ingested', 0)}, "
                              f"Chunks: {result.get('chunks_created', 0)}, "
                              f"Errors: {result.get('errors', 0)}")
                    
                except Exception as e:
                    logger.error(f"Error processing blog {task.blog_name}: {e}", exc_info=True)
                
                finally:
                    self._current_task = None
                    # Add delay between blog processing to avoid rate limits
                    await asyncio.sleep(2.0)  # 2 second delay between blogs
                    self._queue.task_done()
        
        except Exception as e:
            logger.error(f"Error in blog ingestion queue processor: {e}", exc_info=True)
        finally:
            async with self._lock:
                self._processing = False
            logger.info("Blog ingestion queue processor stopped")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status
        
        Returns:
            Dictionary with queue status information
        """
        return {
            "queue_size": self._queue.qsize(),
            "processing": self._processing,
            "current_task": {
                "blog_name": self._current_task.blog_name,
                "feed_url": self._current_task.feed_url,
                "created_at": self._current_task.created_at.isoformat()
            } if self._current_task else None
        }
    
    async def clear_queue(self):
        """Clear all pending tasks from the queue"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        logger.info("Blog ingestion queue cleared")


# Global queue instance
_blog_queue: Optional[BlogIngestionQueue] = None


def get_blog_queue() -> BlogIngestionQueue:
    """Get or create global blog ingestion queue"""
    global _blog_queue
    if _blog_queue is None:
        _blog_queue = BlogIngestionQueue()
    return _blog_queue
