"""
Script to ingest blog content from configured RSS feeds
Run this script to perform initial blog ingestion or refresh all blogs
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.integrations.blog_ingestion import BlogIngestionClient
from src.knowledge.vector_store import vector_store
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def ingest_all_blogs(max_posts_per_blog: int = 50):
    """
    Ingest all configured blog sources
    
    Args:
        max_posts_per_blog: Maximum number of posts to ingest per blog
    """
    logger.info("=" * 60)
    logger.info("Starting blog ingestion for all configured sources")
    logger.info("=" * 60)
    
    client = BlogIngestionClient()
    results = []
    
    total_blogs = len(settings.blog_sources)
    logger.info(f"Found {total_blogs} blog sources to ingest")
    
    for i, blog_source in enumerate(settings.blog_sources, 1):
        blog_name = blog_source["name"]
        feed_url = blog_source["url"]
        
        logger.info("")
        logger.info(f"[{i}/{total_blogs}] Processing: {blog_name}")
        logger.info(f"  Feed URL: {feed_url}")
        logger.info("-" * 60)
        
        try:
            result = await client.ingest_blog(
                blog_name=blog_name,
                feed_url=feed_url,
                max_posts=max_posts_per_blog
            )
            
            results.append(result)
            
            status_emoji = "✓" if result["status"] == "success" else "✗"
            logger.info(f"{status_emoji} {blog_name}:")
            logger.info(f"   Posts ingested: {result['posts_ingested']}")
            logger.info(f"   Chunks created: {result['chunks_created']}")
            logger.info(f"   Errors: {result['errors']}")
            
        except Exception as e:
            logger.error(f"✗ Error ingesting {blog_name}: {e}", exc_info=True)
            results.append({
                "status": "error",
                "blog_name": blog_name,
                "posts_ingested": 0,
                "chunks_created": 0,
                "errors": 1,
                "message": str(e)
            })
    
    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    
    total_posts = sum(r.get("posts_ingested", 0) for r in results)
    total_chunks = sum(r.get("chunks_created", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    successful = sum(1 for r in results if r.get("status") == "success")
    
    logger.info(f"Blogs processed: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Total posts ingested: {total_posts}")
    logger.info(f"Total chunks created: {total_chunks}")
    logger.info(f"Total errors: {total_errors}")
    
    # Get vector store stats
    try:
        stats = vector_store.get_stats()
        logger.info(f"Total vectors in Pinecone: {stats.get('total_vectors', 0)}")
    except Exception as e:
        logger.warning(f"Could not get vector store stats: {e}")
    
    logger.info("=" * 60)
    
    return results


async def ingest_single_blog(blog_name: str, max_posts: int = 50):
    """
    Ingest a single blog by name
    
    Args:
        blog_name: Name of the blog to ingest
        max_posts: Maximum number of posts to ingest
    """
    logger.info(f"Ingesting single blog: {blog_name}")
    
    # Find blog source
    blog_source = next(
        (b for b in settings.blog_sources if b["name"] == blog_name),
        None
    )
    
    if not blog_source:
        logger.error(f"Blog '{blog_name}' not found in configured sources")
        logger.info("Available blogs:")
        for blog in settings.blog_sources:
            logger.info(f"  - {blog['name']}")
        return None
    
    client = BlogIngestionClient()
    result = await client.ingest_blog(
        blog_name=blog_source["name"],
        feed_url=blog_source["url"],
        max_posts=max_posts
    )
    
    logger.info(f"✓ {blog_name}: {result['posts_ingested']} posts, {result['chunks_created']} chunks")
    return result


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest blog content from RSS feeds")
    parser.add_argument(
        "--blog",
        type=str,
        help="Ingest a specific blog by name (omit to ingest all)"
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=50,
        help="Maximum number of posts to ingest per blog (default: 50)"
    )
    
    args = parser.parse_args()
    
    if args.blog:
        # Ingest single blog
        result = asyncio.run(ingest_single_blog(args.blog, args.max_posts))
        sys.exit(0 if result and result.get("status") == "success" else 1)
    else:
        # Ingest all blogs
        results = asyncio.run(ingest_all_blogs(args.max_posts))
        successful = sum(1 for r in results if r.get("status") == "success")
        sys.exit(0 if successful > 0 else 1)


if __name__ == "__main__":
    main()
