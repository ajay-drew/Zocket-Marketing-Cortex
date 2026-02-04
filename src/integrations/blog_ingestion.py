"""
Blog Ingestion Client - Fetch, extract, and chunk blog content from RSS feeds
"""
from typing import List, Dict, Any, Optional
import feedparser
import httpx
from readability import Document
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.config import settings
from src.knowledge.vector_store import vector_store
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class BlogIngestionClient:
    """
    Client for ingesting blog content from RSS feeds
    
    Features:
    - RSS feed parsing
    - Content extraction using readability
    - Text chunking for vector storage
    - Duplicate detection
    - Async operations for non-blocking ingestion
    """
    
    def __init__(self):
        """Initialize blog ingestion client"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        logger.info("Blog Ingestion Client initialized")
    
    async def fetch_rss_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """
        Fetch and parse RSS feed
        
        Args:
            feed_url: RSS feed URL
            
        Returns:
            List of blog post entries with title, link, published date, etc.
        """
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            
            # Use httpx for async HTTP requests
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(feed_url)
                response.raise_for_status()
                
                # Parse RSS feed
                feed = feedparser.parse(response.text)
                
                if feed.bozo:
                    logger.warning(f"Feed parsing warning: {feed.bozo_exception}")
                
                entries = []
                for entry in feed.entries:
                    entries.append({
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "published_parsed": entry.get("published_parsed"),
                        "summary": entry.get("summary", ""),
                        "author": entry.get("author", ""),
                    })
                
                logger.info(f"Fetched {len(entries)} entries from RSS feed")
                return entries
                
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}", exc_info=True)
            raise
    
    async def extract_article_content(self, url: str) -> Optional[Dict[str, str]]:
        """
        Extract clean article content from URL using readability
        
        Args:
            url: Article URL
            
        Returns:
            Dictionary with title and content, or None if extraction fails
        """
        try:
            logger.debug(f"Extracting content from: {url}")
            
            # Fetch HTML content
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html_content = response.text
            
            # Use readability to extract main content
            doc = Document(html_content)
            title = doc.title()
            content_html = doc.summary()
            
            # Convert HTML to plain text using BeautifulSoup
            soup = BeautifulSoup(content_html, "lxml")
            content = soup.get_text(separator="\n", strip=True)
            
            # Clean up content
            content = "\n".join(line.strip() for line in content.split("\n") if line.strip())
            
            if not content or len(content) < 100:
                logger.warning(f"Extracted content too short for {url}")
                return None
            
            logger.debug(f"Extracted {len(content)} characters from {url}")
            return {
                "title": title,
                "content": content
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
    
    def chunk_content(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Split content into chunks for vector storage
        
        Args:
            content: Full article content
            metadata: Metadata to attach to each chunk
            
        Returns:
            List of chunks with metadata
        """
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Create chunk objects with metadata
            chunk_objects = []
            for i, chunk_text in enumerate(chunks):
                chunk_objects.append({
                    "text": chunk_text,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    **metadata
                })
            
            logger.debug(f"Created {len(chunk_objects)} chunks from content")
            return chunk_objects
            
        except Exception as e:
            logger.error(f"Error chunking content: {e}", exc_info=True)
            return []
    
    async def check_duplicate(self, url: str) -> bool:
        """
        Check if URL already exists in vector store
        
        Args:
            url: Article URL to check
            
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            # Search for existing vectors with this URL
            results = await vector_store.search_similar(
                query=url,
                top_k=1,
                filter_metadata={"url": url, "content_type": "blog_post"}
            )
            
            # If we find results with exact URL match, it's a duplicate
            if results and results[0].get("url") == url:
                logger.debug(f"Duplicate found for URL: {url}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking duplicate for {url}: {e}")
            # On error, assume not duplicate to allow ingestion
            return False
    
    async def ingest_blog(
        self,
        blog_name: str,
        feed_url: str,
        max_posts: int = 50
    ) -> Dict[str, Any]:
        """
        Main ingestion orchestration: fetch RSS, extract content, chunk, and store
        
        Args:
            blog_name: Name of the blog
            feed_url: RSS feed URL
            max_posts: Maximum number of posts to ingest
            
        Returns:
            Dictionary with ingestion statistics
        """
        try:
            logger.info(f"Starting blog ingestion: {blog_name} (max {max_posts} posts)")
            
            # Fetch RSS feed
            entries = await self.fetch_rss_feed(feed_url)
            
            if not entries:
                logger.warning(f"No entries found in RSS feed: {feed_url}")
                return {
                    "status": "error",
                    "blog_name": blog_name,
                    "posts_ingested": 0,
                    "chunks_created": 0,
                    "errors": 1,
                    "message": "No entries found in RSS feed"
                }
            
            # Limit to max_posts
            entries = entries[:max_posts]
            
            posts_ingested = 0
            chunks_created = 0
            errors = 0
            
            # Process each entry
            for i, entry in enumerate(entries, 1):
                try:
                    url = entry.get("link", "")
                    if not url:
                        logger.warning(f"Entry {i} has no link, skipping")
                        errors += 1
                        continue
                    
                    # Check for duplicates
                    if await self.check_duplicate(url):
                        logger.debug(f"Skipping duplicate: {url}")
                        continue
                    
                    # Extract content
                    article = await self.extract_article_content(url)
                    if not article:
                        logger.warning(f"Failed to extract content from: {url}")
                        errors += 1
                        continue
                    
                    # Create chunks
                    metadata = {
                        "blog_name": blog_name,
                        "url": url,
                        "title": article["title"],
                        "original_title": entry.get("title", ""),
                        "published": entry.get("published", ""),
                        "author": entry.get("author", ""),
                        "content_type": "blog_post",
                        "ingested_at": datetime.utcnow().isoformat(),
                    }
                    
                    chunks = self.chunk_content(article["content"], metadata)
                    
                    if not chunks:
                        logger.warning(f"No chunks created for: {url}")
                        errors += 1
                        continue
                    
                    # Upsert to vector store
                    await vector_store.upsert_blog_content(chunks, metadata)
                    
                    posts_ingested += 1
                    chunks_created += len(chunks)
                    
                    logger.info(f"Ingested post {i}/{len(entries)}: {article['title'][:50]}... ({len(chunks)} chunks)")
                    
                    # Small delay to avoid overwhelming the system
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error processing entry {i}: {e}", exc_info=True)
                    errors += 1
                    continue
            
            result = {
                "status": "success" if posts_ingested > 0 else "error",
                "blog_name": blog_name,
                "posts_ingested": posts_ingested,
                "chunks_created": chunks_created,
                "errors": errors,
                "total_entries": len(entries)
            }
            
            logger.info(f"Blog ingestion complete: {blog_name} - {posts_ingested} posts, {chunks_created} chunks, {errors} errors")
            return result
            
        except Exception as e:
            logger.error(f"Error ingesting blog {blog_name}: {e}", exc_info=True)
            return {
                "status": "error",
                "blog_name": blog_name,
                "posts_ingested": 0,
                "chunks_created": 0,
                "errors": 1,
                "message": str(e)
            }
