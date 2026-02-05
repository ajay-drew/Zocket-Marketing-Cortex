"""
Batch Blog Ingestion Script
Ingests multiple blogs from a list while backend is running
Checks for duplicates before ingestion and processes one blog at a time

Usage:
    python scripts/batch_ingest_blogs.py
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import logging
from datetime import datetime

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.blog_ingestion import BlogIngestionClient
from src.knowledge.vector_store import vector_store
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_blog_exists(blog_name: str, feed_url: str) -> bool:
    """
    Check if blog already exists in configured sources
    
    Args:
        blog_name: Name of the blog
        feed_url: RSS feed URL
        
    Returns:
        True if blog exists, False otherwise
    """
    # Normalize URLs for comparison (remove trailing slashes, etc.)
    normalized_url = feed_url.rstrip('/')
    
    for blog_source in settings.blog_sources:
        normalized_source_url = blog_source["url"].rstrip('/')
        # Check by URL (most reliable) or name
        if (normalized_source_url == normalized_url or 
            blog_source["name"].lower() == blog_name.lower()):
            return True
    
    return False


async def check_blog_in_pinecone(blog_name: str) -> bool:
    """
    Check if blog content already exists in Pinecone
    
    Args:
        blog_name: Name of the blog
        
    Returns:
        True if blog has content in Pinecone, False otherwise
    """
    try:
        stats = await vector_store.get_blog_stats(blog_name=blog_name)
        blog_vectors = stats.get("blog_vectors", 0)
        return blog_vectors > 0
    except Exception as e:
        logger.warning(f"Could not check Pinecone for {blog_name}: {e}")
        return False


async def ingest_blog_with_progress(
    client: BlogIngestionClient,
    blog_name: str,
    feed_url: str,
    max_posts: int,
    index: int,
    total: int
) -> Dict:
    """Ingest a single blog with progress reporting"""
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"[{index}/{total}] Processing: {blog_name}")
    logger.info(f"  URL: {feed_url}")
    logger.info(f"  Max Posts: {max_posts}")
    logger.info("-" * 70)
    
    # Check if blog content exists in Pinecone (only skip if content exists)
    has_content = await check_blog_in_pinecone(blog_name)
    if has_content:
        logger.warning(f"⚠️  Blog '{blog_name}' already has content in Pinecone!")
        logger.info("   Skipping ingestion to avoid duplicates.")
        return {
            "status": "skipped",
            "blog_name": blog_name,
            "feed_url": feed_url,
            "posts_ingested": 0,
            "chunks_created": 0,
            "errors": 0,
            "message": "Blog content already exists in Pinecone",
            "reason": "duplicate"
        }
    
    # Note: Even if blog exists in configured sources, we still ingest it
    # This allows refreshing/updating existing blogs
    if check_blog_exists(blog_name, feed_url):
        logger.info(f"ℹ️  Blog '{blog_name}' exists in configured sources, but will still be ingested.")
    
    start_time = datetime.now()
    
    try:
        # Progress callback for real-time updates
        async def progress_callback(progress_data: Dict):
            stage = progress_data.get("stage", "unknown")
            message = progress_data.get("message", "")
            progress = progress_data.get("progress", 0)
            
            if stage == "fetching":
                logger.info(f"  📥 {message}")
            elif stage == "extracting":
                logger.info(f"  🔍 {message}")
            elif stage == "chunking":
                logger.info(f"  ✂️  {message}")
            elif stage == "storing":
                logger.info(f"  💾 {message}")
            elif stage == "entity_extraction":
                logger.info(f"  🏷️  {message}")
            elif stage == "error":
                logger.error(f"  ❌ Error: {message}")
        
        result = await client.ingest_blog(
            blog_name=blog_name,
            feed_url=feed_url,
            max_posts=max_posts,
            progress_callback=progress_callback
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log results
        status_emoji = "✅" if result.get("status") == "success" else "❌"
        logger.info("")
        logger.info(f"{status_emoji} {blog_name} - Completed in {duration:.1f}s")
        logger.info(f"   Posts ingested: {result.get('posts_ingested', 0)}")
        logger.info(f"   Chunks created: {result.get('chunks_created', 0)}")
        logger.info(f"   Errors: {result.get('errors', 0)}")
        
        if result.get("message"):
            logger.info(f"   Message: {result['message']}")
        
        return result
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Error ingesting {blog_name}: {e}", exc_info=True)
        return {
            "status": "error",
            "blog_name": blog_name,
            "feed_url": feed_url,
            "posts_ingested": 0,
            "chunks_created": 0,
            "errors": 1,
            "message": str(e),
            "duration": duration
        }


async def batch_ingest_blogs(
    blogs: List[Tuple[str, str]],
    max_posts: int = 50
) -> List[Dict]:
    """
    Ingest multiple blogs one at a time
    
    Args:
        blogs: List of (blog_name, feed_url) tuples
        max_posts: Maximum posts per blog
    """
    if not blogs:
        logger.error("No blogs to ingest!")
        return []
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("BATCH BLOG INGESTION")
    logger.info("=" * 70)
    logger.info(f"Total blogs: {len(blogs)}")
    logger.info(f"Max posts per blog: {max_posts}")
    logger.info(f"Mode: Sequential (one at a time)")
    logger.info("=" * 70)
    
    client = BlogIngestionClient()
    results = []
    
    # Process blogs sequentially (one at a time)
    for i, (name, url) in enumerate(blogs, 1):
        result = await ingest_blog_with_progress(
            client, name, url, max_posts, i, len(blogs)
        )
        results.append(result)
    
    # Print summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 70)
    
    total_posts = sum(r.get("posts_ingested", 0) for r in results)
    total_chunks = sum(r.get("chunks_created", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    successful = sum(1 for r in results if r.get("status") == "success")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    failed = sum(1 for r in results if r.get("status") == "error")
    
    logger.info(f"Blogs processed: {len(results)}")
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"⏭️  Skipped (duplicates): {skipped}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📄 Total posts ingested: {total_posts}")
    logger.info(f"📦 Total chunks created: {total_chunks}")
    logger.info(f"⚠️  Total errors: {total_errors}")
    
    # Get vector store stats
    try:
        stats = vector_store.get_stats()
        logger.info(f"📊 Total vectors in Pinecone: {stats.get('total_vectors', 0)}")
    except Exception as e:
        logger.warning(f"Could not get vector store stats: {e}")
    
    # Show skipped blogs
    if skipped > 0:
        logger.info("")
        logger.info("Skipped blogs (duplicates):")
        for result in results:
            if result.get("status") == "skipped":
                logger.info(f"  ⏭️  {result.get('blog_name', 'Unknown')}: {result.get('message', 'Already exists')}")
    
    # Show failed blogs
    if failed > 0:
        logger.info("")
        logger.info("Failed blogs:")
        for result in results:
            if result.get("status") == "error":
                logger.info(f"  ❌ {result.get('blog_name', 'Unknown')}: {result.get('message', 'Unknown error')}")
    
    logger.info("=" * 70)
    
    return results


def main():
    """Main entry point"""
    # Predefined list of blogs to ingest
    blogs_to_ingest = [
        ("Ahrefs Blog", "https://ahrefs.com/blog/feed/"),
        ("Content Marketing Institute", "https://contentmarketinginstitute.com/feed/"),
        ("Search Engine Land", "https://searchengineland.com/feed"),
        ("Neil Patel Blog", "https://neilpatel.com/feed/"),
        ("Social Media Examiner", "https://www.socialmediaexaminer.com/feed/"),
        ("Copyblogger", "https://copyblogger.com/feed/"),
        ("MarTech", "https://martech.org/feed/"),
        ("Smart Insights", "https://www.smartinsights.com/feed/"),
        ("Entrepreneur Marketing", "https://www.entrepreneur.com/topic/marketing.rss"),
        ("The Next Web", "https://feeds2.feedburner.com/thenextweb"),
        ("Inside Intercom", "https://feeds.feedburner.com/insideintercom"),
        ("Smashing Magazine", "https://www.smashingmagazine.com/feed/"),
        ("The Keyword (Google)", "https://www.blog.google/rss/"),
        ("Social Media Today", "https://www.socialmediatoday.com/feeds/news/"),
    ]
    
    logger.info("Starting batch blog ingestion for predefined blogs...")
    logger.info(f"Blogs to process: {len(blogs_to_ingest)}")
    
    # Run ingestion
    results = asyncio.run(batch_ingest_blogs(blogs_to_ingest, max_posts=50))
    
    # Exit code based on results
    successful = sum(1 for r in results if r.get("status") == "success")
    sys.exit(0 if successful > 0 else 1)


if __name__ == "__main__":
    main()
