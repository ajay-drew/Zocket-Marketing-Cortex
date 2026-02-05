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
            
            # Validate and auto-correct common RSS feed URL patterns
            original_url = feed_url
            if not any(feed_url.endswith(ext) for ext in ['/feed', '/feed/', '/rss', '/rss.xml', '.xml', '/atom.xml']):
                # Try common RSS feed patterns in parallel for faster detection
                base_url = feed_url.rstrip('/')
                common_patterns = [
                    f"{base_url}/feed/",
                    f"{base_url}/feed",
                    f"{base_url}/rss.xml",
                    f"{base_url}/rss",
                ]
                
                # Try all patterns in parallel
                async def test_pattern(pattern: str) -> Optional[str]:
                    """Test a single pattern and return it if valid"""
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as test_client:
                            test_response = await test_client.get(pattern, follow_redirects=True)
                            if test_response.status_code == 200:
                                # Check if it's actually an RSS feed
                                content_type = test_response.headers.get('content-type', '').lower()
                                if 'xml' in content_type or 'rss' in content_type or 'atom' in content_type:
                                    return pattern
                    except Exception:
                        pass
                    return None
                
                # Test all patterns in parallel
                import asyncio
                results = await asyncio.gather(*[test_pattern(p) for p in common_patterns], return_exceptions=True)
                
                # Find first valid result
                for result in results:
                    if result and isinstance(result, str):
                        feed_url = result
                        logger.info(f"Auto-corrected RSS feed URL: {original_url} -> {feed_url}")
                        break
                else:
                    logger.warning(f"URL '{original_url}' doesn't look like an RSS feed. Tried common patterns but none worked.")
            
            # Use httpx for async HTTP requests
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(feed_url, follow_redirects=True)
                response.raise_for_status()
                
                # Check content type (handle Mock objects in tests)
                content_type = response.headers.get('content-type', '')
                if not isinstance(content_type, str):
                    content_type = str(content_type) if content_type else ''
                content_type = content_type.lower()
                if 'html' in content_type and 'xml' not in content_type and 'rss' not in content_type and 'atom' not in content_type:
                    logger.error(f"URL returned HTML instead of RSS feed. This is likely a webpage, not an RSS feed.")
                    logger.error(f"Common RSS feed URLs: {feed_url.rstrip('/')}/feed/, {feed_url.rstrip('/')}/feed, {feed_url.rstrip('/')}/rss.xml")
                    return []
                
                # Parse RSS feed
                feed = feedparser.parse(response.text)
                
                if feed.bozo:
                    logger.warning(f"Feed parsing warning: {feed.bozo_exception}")
                    # If parsing failed and we got HTML, suggest the correct URL
                    if response.text and 'html' in response.text[:200].lower():
                        logger.error(f"Received HTML instead of RSS feed. Try: {feed_url.rstrip('/')}/feed/ or {feed_url.rstrip('/')}/rss.xml")
                        return []
                
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
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code} when fetching RSS feed"
            if e.response.status_code == 404:
                error_msg = f"RSS feed not found (404). Please verify the URL: {feed_url}"
            elif e.response.status_code == 403:
                error_msg = f"Access forbidden (403). The RSS feed may require authentication."
            logger.error(f"{error_msg}: {e}", exc_info=True)
            raise ValueError(error_msg) from e
        except httpx.TimeoutException as e:
            error_msg = f"Request timeout when fetching RSS feed: {feed_url}"
            logger.error(f"{error_msg}: {e}", exc_info=True)
            raise ValueError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"Network error when fetching RSS feed: {feed_url}. {str(e)}"
            logger.error(f"{error_msg}: {e}", exc_info=True)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"Error fetching RSS feed {feed_url}: {str(e)}"
            logger.error(f"{error_msg}: {e}", exc_info=True)
            raise ValueError(error_msg) from e
    
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
            try:
                entries = await self.fetch_rss_feed(feed_url)
            except ValueError as e:
                # RSS feed fetch error (invalid URL, network error, etc.)
                error_message = str(e)
                if progress_callback:
                    await progress_callback({
                        "stage": "error",
                        "message": error_message,
                        "progress": 0,
                        "error": True
                    })
                return {
                    "status": "error",
                    "blog_name": blog_name,
                    "posts_ingested": 0,
                    "chunks_created": 0,
                    "errors": 1,
                    "message": error_message
                }
            
            if not entries:
                error_message = f"No entries found in RSS feed: {feed_url}. The feed may be empty or invalid."
                logger.warning(error_message)
                if progress_callback:
                    await progress_callback({
                        "stage": "error",
                        "message": error_message,
                        "progress": 0,
                        "error": True
                    })
                return {
                    "status": "error",
                    "blog_name": blog_name,
                    "posts_ingested": 0,
                    "chunks_created": 0,
                    "errors": 1,
                    "message": error_message
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
            
            # Process entries sequentially to avoid rate limits
            # With entity extraction, even 2-3 concurrent posts can hit rate limits
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
                            
                            # Process chunks sequentially to avoid rate limits
                            # Even with semaphore=1, parallel processing can cause bursts
                            chunks_with_index = [(i, chunk) for i, chunk in enumerate(chunks)]
                            extraction_results = []
                            
                            # Process chunks one at a time with delays
                            for chunk_data in chunks_with_index:
                                result = await extract_entities_for_chunk(chunk_data)
                                extraction_results.append(result)
                                
                                # Add delay between entity extractions to avoid rate limits
                                if settings.entity_extraction_delay > 0:
                                    await asyncio.sleep(settings.entity_extraction_delay)
                            
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
            
            # Process entries sequentially to avoid rate limits
            # With entity extraction, parallel processing causes rate limit issues
            results = []
            for i, entry_data in enumerate(entries_with_index):
                result = await process_entry(entry_data)
                results.append(result)
                
                # Update progress
                if progress_callback:
                    await progress_callback({
                        "stage": "processing",
                        "message": f"Processing posts... ({i + 1}/{total_entries} completed)",
                        "progress": 5 + int(((i + 1) / total_entries) * 90) if total_entries > 0 else 5,
                        "current": i + 1,
                        "total": total_entries
                    })
                
                # Add delay between posts to avoid rate limits
                if settings.blog_processing_delay > 0 and i < len(entries_with_index) - 1:
                    await asyncio.sleep(settings.blog_processing_delay)
            
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
            
        except ValueError as e:
            # Validation errors (RSS feed issues, etc.)
            error_message = str(e)
            logger.error(f"Validation error ingesting blog {blog_name}: {e}", exc_info=True)
            if progress_callback:
                await progress_callback({
                    "stage": "error",
                    "message": error_message,
                    "progress": 0,
                    "error": True
                })
            return {
                "status": "error",
                "blog_name": blog_name,
                "posts_ingested": 0,
                "chunks_created": 0,
                "errors": 1,
                "message": error_message
            }
        except Exception as e:
            # Unexpected errors
            error_message = f"Unexpected error during ingestion: {str(e)}"
            logger.error(f"Error ingesting blog {blog_name}: {e}", exc_info=True)
            if progress_callback:
                await progress_callback({
                    "stage": "error",
                    "message": error_message,
                    "progress": 0,
                    "error": True
                })
            return {
                "status": "error",
                "blog_name": blog_name,
                "posts_ingested": 0,
                "chunks_created": 0,
                "errors": 1,
                "message": error_message
            }
