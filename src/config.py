"""
Configuration management for Marketing Cortex
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional, List, Dict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    port: int = 5469
    
    # Groq
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"  # Latest versatile model
    
    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str
    langchain_project: str = "marketing-cortex"
    
    # Langfuse
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"
    
    # Neo4j
    neo4j_uri: str
    neo4j_username: str = "neo4j"
    neo4j_password: str
    neo4j_database: str = "neo4j"
    
    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "marketing-cortex"
    # Note: pinecone_environment deprecated in v3.0+
    
    # Zep
    zep_api_url: str = "https://api.getzep.com"
    zep_api_key: str
    
    # Redis (Upstash Serverless)
    redis_url: str = "rediss://default:your_password@your-endpoint.upstash.io:6379"
    
    # Tavily
    tavily_api_key: str
    tavily_monthly_limit: int = 1000
    tavily_enable_fallback: bool = True
    
    # Blog Ingestion
    blog_sources: List[Dict[str, str]] = [
        {"name": "HubSpot Marketing", "url": "https://blog.hubspot.com/marketing/rss.xml"},
        {"name": "Moz Blog", "url": "https://moz.com/blog/feed"},
        {"name": "Content Marketing Institute", "url": "https://contentmarketinginstitute.com/feed/"},
        {"name": "Marketing Land", "url": "https://marketingland.com/feed"},
        {"name": "AdWeek", "url": "https://www.adweek.com/feed/"},
        {"name": "Social Media Examiner", "url": "https://www.socialmediaexaminer.com/feed/"},
        {"name": "Copyblogger", "url": "https://copyblogger.com/feed/"},
        {"name": "Neil Patel", "url": "https://neilpatel.com/feed/"},
    ]
    chunk_size: int = 500  # Tokens per chunk
    chunk_overlap: int = 50  # Overlap between chunks
    enable_entity_extraction: bool = True  # Enable entity extraction during blog ingestion
    max_concurrent_posts: int = 5  # Maximum concurrent blog posts to process in parallel


# Global settings instance
settings = Settings()
