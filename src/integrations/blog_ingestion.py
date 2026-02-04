"""
Blog Ingestion Client - Fetch, extract, and chunk blog content from RSS feeds
"""
from typing import List, Dict, Any, Optional, Callable, Awaitable
import feedparser
import httpx
from readability import Document
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import settings
from src.knowledge.vector_store import vector_store
from src.core.queue import ParallelProcessor
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
        max_posts: int = 50,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
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
            
            if progress_callback:
                await progress_callback({
                    "stage": "fetching",
                    "message": f"Fetching RSS feed from {feed_url}...",
                    "progress": 0
                })
            
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
            total_entries = len(entries)
            
            if progress_callback:
                await progress_callback({
                    "stage": "processing",
                    "message": f"Found {total_entries} posts. Starting ingestion...",
                    "progress": 5,
                    "total": total_entries
                })
            
            posts_ingested = 0
            chunks_created = 0
            errors = 0
            
            # Process entries in parallel with concurrency control
            async def process_entry(entry_data: tuple[int, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
                """Process a single blog entry"""
                i, entry = entry_data
                try:
                    url = entry.get("link", "")
                    if not url:
                        logger.warning(f"Entry {i} has no link, skipping")
                        return {"error": True}
                    
                    # Check for duplicates
                    if await self.check_duplicate(url):
                        logger.debug(f"Skipping duplicate: {url}")
                        return None
                    
                    # Extract content
                    article = await self.extract_article_content(url)
                    if not article:
                        logger.warning(f"Failed to extract content from: {url}")
                        return {"error": True}
                    
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
                        return {"error": True}
                    
                    # Upsert to vector store
                    await vector_store.upsert_blog_content(chunks, metadata)
                    
                    # Extract entities and store in Neo4j (if enabled)
                    if settings.enable_entity_extraction:
                        try:
                            from src.knowledge.entity_extractor import EntityExtractor
                            from src.knowledge.graph_schema import graph_schema
                            
                            entity_extractor = EntityExtractor()
                            
                            # Process entity extraction for chunks in parallel (with semaphore control)
                            async def extract_entities_for_chunk(chunk_data: tuple[int, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
                                """Extract entities for a single chunk"""
                                chunk_idx, chunk = chunk_data
                                try:
                                    # Generate chunk ID using same logic as vector_store
                                    chunk_index = chunk.get("chunk_index", chunk_idx)
                                    chunk_id = f"blog_{hash(url)}_{chunk_index}"
                                    chunk_text = chunk.get("text", "")
                                    
                                    if not chunk_text:
                                        return None
                                    
                                    # Extract entities (with rate limiting built-in)
                                    extraction_result = await entity_extractor.extract_entities(
                                        content=chunk_text,
                                        chunk_id=chunk_id,
                                        url=url
                                    )
                                    
                                    # Only process if entities were extracted (not empty due to rate limit)
                                    if extraction_result.entities or extraction_result.relationships:
                                        return {
                                            "chunk_id": chunk_id,
                                            "extraction_result": extraction_result,
                                            "chunk_index": chunk_index
                                        }
                                    return None
                                except Exception as e:
                                    logger.warning(f"Error extracting entities for chunk {chunk_idx}: {e}")
                                    return None
                            
                            # Process chunks in parallel (semaphore in EntityExtractor limits concurrency)
                            chunks_with_index = [(i, chunk) for i, chunk in enumerate(chunks)]
                            extraction_results = await ParallelProcessor.process_parallel(
                                items=chunks_with_index,
                                processor=extract_entities_for_chunk,
                                max_concurrent=3,  # Limited by EntityExtractor semaphore
                                progress_callback=None
                            )
                            
                            # Store extracted entities in Neo4j
                            for result in extraction_results:
                                if result is None:
                                    continue
                                
                                extraction_result = result["extraction_result"]
                                chunk_id = result["chunk_id"]
                                
                                # Store entities in Neo4j
                                entity_ids_map = {}  # Map entity names to IDs for relationships
                                for entity in extraction_result.entities:
                                    entity_id = EntityExtractor._generate_entity_id(entity.name, entity.type)
                                    entity_ids_map[entity.name] = entity_id
                                    
                                    await graph_schema.create_marketing_entity(
                                        entity_id=entity_id,
                                        name=entity.name,
                                        entity_type=entity.type,
                                        confidence=entity.confidence,
                                        metadata={"extracted_from": url}
                                    )
                                    
                                    # Link entity to blog chunk
                                    await graph_schema.link_entity_to_blog(
                                        entity_id=entity_id,
                                        chunk_id=chunk_id,
                                        url=url,
                                        blog_name=blog_name,
                                        title=article.get("title", "")
                                    )
                                
                                # Store relationships (need to find entity types for source/target)
                                for relationship in extraction_result.relationships:
                                    # Find source entity type
                                    source_entity = next(
                                        (e for e in extraction_result.entities if e.name == relationship.source),
                                        None
                                    )
                                    target_entity = next(
                                        (e for e in extraction_result.entities if e.name == relationship.target),
                                        None
                                    )
                                    
                                    if source_entity and target_entity:
                                        source_id = EntityExtractor._generate_entity_id(relationship.source, source_entity.type)
                                        target_id = EntityExtractor._generate_entity_id(relationship.target, target_entity.type)
                                        
                                        await graph_schema.create_entity_relationship(
                                            source_entity_id=source_id,
                                            target_entity_id=target_id,
                                            relationship_type=relationship.type,
                                            confidence=relationship.confidence,
                                            metadata={"extracted_from": url}
                                        )
                            
                            logger.debug(f"Extracted entities for post: {article['title'][:50]}")
                        except Exception as e:
                            logger.warning(f"Entity extraction failed for {url}: {e}")
                            # Continue ingestion even if entity extraction fails
                    
                    logger.info(f"Ingested post {i}/{total_entries}: {article['title'][:50]}... ({len(chunks)} chunks)")
                    
                    return {
                        "success": True,
                        "index": i,
                        "title": article["title"],
                        "chunks": len(chunks),
                        "url": url
                    }
                    
                except Exception as e:
                    logger.error(f"Error processing entry {i}: {e}", exc_info=True)
                    return {"error": True, "index": i}
            
            # Prepare entries with indices for parallel processing
            entries_with_index = [(i + 1, entry) for i, entry in enumerate(entries)]
            
            # Progress callback wrapper
            async def progress_wrapper(progress_data: Dict[str, Any]):
                """Wrapper for progress callback"""
                if progress_callback:
                    await progress_callback({
                        "stage": "processing",
                        "message": f"Processing posts... ({progress_data['completed']}/{progress_data['total']} completed)",
                        "progress": 5 + int((progress_data['completed'] / progress_data['total']) * 90) if progress_data['total'] > 0 else 5,
                        "current": progress_data['completed'],
                        "total": progress_data['total']
                    })
            
            # Process in parallel with configurable concurrency
            results = await ParallelProcessor.process_parallel(
                items=entries_with_index,
                processor=process_entry,
                max_concurrent=settings.max_concurrent_posts,
                progress_callback=progress_wrapper if progress_callback else None
            )
            
            # Process results and update counters
            for result in results:
                if result is None:
                    continue  # Skipped duplicate
                elif result.get("error"):
                    errors += 1
                elif result.get("success"):
                    posts_ingested += 1
                    chunks_created += result.get("chunks", 0)
                    
                    # Update progress for successful ingestion
                    if progress_callback:
                        progress = 5 + int((posts_ingested / total_entries) * 90) if total_entries > 0 else 5
                        await progress_callback({
                            "stage": "processing",
                            "message": f"✓ Ingested: {result.get('title', 'Unknown')[:50]}... ({result.get('chunks', 0)} chunks)",
                            "progress": progress,
                            "current": posts_ingested,
                            "total": total_entries,
                            "posts_ingested": posts_ingested,
                            "chunks_created": chunks_created
                        })
            
            if progress_callback:
                await progress_callback({
                    "stage": "complete",
                    "message": f"Ingestion complete! {posts_ingested} posts, {chunks_created} chunks",
                    "progress": 100,
                    "posts_ingested": posts_ingested,
                    "chunks_created": chunks_created,
                    "errors": errors
                })
            
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
