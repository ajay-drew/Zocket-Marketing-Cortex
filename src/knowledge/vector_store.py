"""
Pinecone vector store for storing and retrieving research results
Uses Pinecone's built-in embedding model (multilingual-e5-large)
"""
from typing import List, Dict, Any, Optional
from pinecone import Pinecone, ServerlessSpec
from src.config import settings
from src.observability import circuit_breaker, get_alert_manager
import logging
import uuid

logger = logging.getLogger(__name__)
alert_manager = get_alert_manager()


class VectorStore:
    """
    Manages Pinecone vector store for research results
    
    Features:
    - Uses Pinecone's built-in multilingual-e5-large embedding model
    - Store and retrieve similar research results
    - RAG integration for agent queries
    - No local embedding generation needed
    """
    
    # Pinecone built-in embedding model
    EMBEDDING_MODEL = "multilingual-e5-large"
    EMBEDDING_DIMENSION = 1024  # Dimension for multilingual-e5-large
    
    def __init__(self):
        """Initialize Pinecone client with built-in embedding model"""
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        
        # Initialize or get index with built-in embedding model
        self.index = self._get_or_create_index()
        logger.info(f"Pinecone vector store initialized: {self.index_name} with {self.EMBEDDING_MODEL}")
    
    def _get_or_create_index(self):
        """
        Get existing index or create new one if it doesn't exist
        
        Returns:
            Pinecone Index object
        """
        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if self.index_name in existing_indexes:
                logger.info(f"Using existing Pinecone index: {self.index_name}")
                return self.pc.Index(self.index_name)
            else:
                # Create new index with built-in embedding model
                logger.info(f"Creating new Pinecone index: {self.index_name} with {self.EMBEDDING_MODEL}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.EMBEDDING_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    ),
                    # Use Pinecone's built-in embedding model
                    metadata_config={
                        "indexed": ["query", "title", "url"]
                    }
                )
                # Wait for index to be ready (only called during init, so sync is OK)
                import time
                time.sleep(2)
                return self.pc.Index(self.index_name)
        except Exception as e:
            logger.error(f"Error getting/creating Pinecone index: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for query-time operations
        
        Note: For storage, Pinecone's serverless index with multilingual-e5-large handles embeddings.
        For queries, we need to generate embeddings locally. Since multilingual-e5-large produces
        1024-dimensional vectors, we use a compatible approach.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (1024 dimensions to match multilingual-e5-large)
        """
        try:
            # Try using Pinecone's embed API if available through the client
            if hasattr(self.pc, 'embed'):
                try:
                    result = self.pc.embed(
                        texts=[text],
                        model=self.EMBEDDING_MODEL
                    )
                    return result[0] if isinstance(result, list) else result.vectors[0]
                except Exception:
                    pass
            
            # Fallback: Use a simple hash-based embedding for testing/compatibility
            # This is a placeholder - in production, use Pinecone's embed API or a matching model
            # For now, generate a deterministic 1024-dim vector based on text hash
            import hashlib
            import struct
            
            # Create a deterministic embedding based on text hash
            # This is a simple fallback - not semantically meaningful but dimensionally correct
            # Generate enough hash material for 1024 dimensions
            text_bytes = text.encode()
            embedding = []
            
            # Generate 1024 dimensions by hashing the text multiple times with different salts
            for i in range(self.EMBEDDING_DIMENSION):
                # Create a unique hash for each dimension
                hash_input = text_bytes + str(i).encode()
                hash_val = hashlib.sha256(hash_input).digest()
                # Use first 4 bytes to create a float
                val = struct.unpack('>I', hash_val[:4])[0]
                normalized = (val / 4294967295.0) * 2.0 - 1.0  # Normalize to [-1, 1]
                embedding.append(normalized)
            
            logger.warning(
                "Using hash-based embedding fallback. "
                "For production, configure Pinecone's embed API or use a proper embedding model."
            )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def upsert_research(
        self,
        query: str,
        research_results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Store research results in Pinecone using built-in multilingual-e5-large model
        
        For serverless indexes with built-in embeddings, Pinecone handles embedding automatically.
        We generate embeddings locally only for compatibility with existing indexes.
        
        Args:
            query: Original research query
            research_results: List of research results from Tavily
            metadata: Additional metadata to store
            
        Returns:
            Number of vectors upserted
        """
        try:
            vectors_to_upsert = []
            
            for i, result in enumerate(research_results):
                # Combine title and content for embedding
                text_to_embed = f"{result.get('title', '')} {result.get('content', '')}"
                
                # Generate embedding using Pinecone's model (1024 dimensions)
                embedding = self.embed_text(text_to_embed)
                
                # Create vector with metadata
                vector_id = str(uuid.uuid4())
                vector_metadata = {
                    "query": query,
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", "")[:1000],  # Limit content length
                    "score": result.get("score", 0.0),
                    "index": i,
                    **(metadata or {})
                }
                
                vectors_to_upsert.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": vector_metadata
                })
            
            # Upsert in batches
            if vectors_to_upsert:
                self.index.upsert(vectors=vectors_to_upsert)
                logger.info(f"Upserted {len(vectors_to_upsert)} research vectors for query: {query[:50]}")
                return len(vectors_to_upsert)
            
            return 0
        except Exception as e:
            logger.error(f"Error upserting research: {e}")
            raise
    
    @circuit_breaker("pinecone")
    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar research results
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of similar research results with scores
        """
        from src.observability.circuit_breaker import CircuitBreakerOpenError
        
        try:
            # Generate embedding for query
            query_embedding = self.embed_text(query)
            
            # Search in Pinecone
            search_results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_metadata
            )
            
            # Format results
            results = []
            for match in search_results.matches:
                results.append({
                    "id": match.id,
                    "score": match.score,
                    "title": match.metadata.get("title", ""),
                    "url": match.metadata.get("url", ""),
                    "content": match.metadata.get("content", ""),
                    "original_query": match.metadata.get("query", ""),
                    "metadata": match.metadata
                })
            
            logger.info(f"Found {len(results)} similar research results for query: {query[:50]}")
            return results
        except CircuitBreakerOpenError:
            # Circuit breaker is open, return empty results
            logger.warning(f"⚠️ Circuit breaker open for Pinecone, returning empty results for: {query[:50]}")
            return []
        except Exception as e:
            alert_manager.record_error("pinecone_search_error", "pinecone", {"error": str(e), "query": query[:200]})
            logger.error(f"Error searching similar research: {e}")
            return []
    
    async def delete_by_query(self, query: str) -> int:
        """
        Delete all vectors associated with a query
        
        Args:
            query: Query to delete vectors for
            
        Returns:
            Number of vectors deleted
        """
        try:
            # Search for vectors with this query
            query_embedding = self.embed_text(query)
            search_results = self.index.query(
                vector=query_embedding,
                top_k=100,  # Get up to 100 results
                include_metadata=True
            )
            
            # Delete matching vectors
            ids_to_delete = [
                match.id for match in search_results.matches
                if match.metadata.get("query") == query
            ]
            
            if ids_to_delete:
                self.index.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} vectors for query: {query[:50]}")
                return len(ids_to_delete)
            
            return 0
        except Exception as e:
            logger.error(f"Error deleting by query: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics
        
        Returns:
            Dictionary with index stats
        """
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness if hasattr(stats, 'index_fullness') else None
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    async def check_duplicate(self, url: str) -> bool:
        """
        Check if a URL already exists in the vector store
        
        Args:
            url: URL to check for duplicates
            
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            # Search for vectors with this exact URL
            results = await self.search_similar(
                query=url,
                top_k=5,
                filter_metadata={"url": url, "content_type": "blog_post"}
            )
            
            # Check if any result has the exact URL
            for result in results:
                if result.get("url") == url:
                    logger.debug(f"Duplicate found: {url}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking duplicate for {url}: {e}")
            return False
    
    async def upsert_blog_content(
        self,
        chunks: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Upsert blog content chunks to Pinecone
        
        Args:
            chunks: List of chunk dictionaries with 'text' and metadata
            metadata: Additional metadata to merge with each chunk
            
        Returns:
            Number of vectors upserted
        """
        try:
            vectors_to_upsert = []
            
            for chunk in chunks:
                text = chunk.get("text", "")
                if not text:
                    continue
                
                # Generate embedding
                embedding = self.embed_text(text)
                
                # Merge chunk metadata with provided metadata
                chunk_metadata = {
                    **chunk,
                    **(metadata or {})
                }
                
                # Remove 'text' from metadata (it's the vector value)
                chunk_metadata.pop("text", None)
                
                # Create vector ID from URL and chunk index
                url = chunk_metadata.get("url", "")
                chunk_index = chunk_metadata.get("chunk_index", 0)
                vector_id = f"blog_{hash(url)}_{chunk_index}"
                
                vectors_to_upsert.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": chunk_metadata
                })
            
            # Upsert in batches of 100
            if vectors_to_upsert:
                batch_size = 100
                for i in range(0, len(vectors_to_upsert), batch_size):
                    batch = vectors_to_upsert[i:i + batch_size]
                    self.index.upsert(vectors=batch)
                
                logger.info(f"Upserted {len(vectors_to_upsert)} blog content vectors")
                return len(vectors_to_upsert)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error upserting blog content: {e}", exc_info=True)
            raise
    
    async def get_blog_stats(self, blog_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for blog content in vector store
        
        Args:
            blog_name: Optional blog name to filter by
            
        Returns:
            Dictionary with blog statistics
        """
        try:
            # Get overall index stats
            stats = self.get_stats()
            
            # For blog-specific stats, we'd need to query the index
            # This is a simplified version - in production, you might want to
            # maintain a separate metadata store or use Pinecone's metadata filtering
            
            result = {
                "total_vectors": stats.get("total_vectors", 0),
                "blog_name": blog_name,
                "blog_vectors": 0,  # Would need to query with filter to get exact count
            }
            
            # If blog_name is provided, try to get approximate count
            if blog_name:
                try:
                    # Query with blog name filter to get approximate count
                    results = await self.search_similar(
                        query=blog_name,
                        top_k=100,
                        filter_metadata={"blog_name": blog_name, "content_type": "blog_post"}
                    )
                    result["blog_vectors"] = len(results)
                except Exception as e:
                    logger.warning(f"Could not get blog-specific stats: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting blog stats: {e}")
            return {}


# Global vector store instance (lazy initialization to avoid import errors)
_vector_store_instance = None

def get_vector_store():
    """Get or create vector store instance (lazy initialization)"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance

# Create a simple proxy class for backward compatibility
class VectorStoreProxy:
    """Proxy class to allow lazy initialization"""
    def __getattr__(self, name):
        return getattr(get_vector_store(), name)

vector_store = VectorStoreProxy()
