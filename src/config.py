"""
Configuration management for Marketing Cortex
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    port: int = 8070
    
    # Groq
    groq_api_key: str
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
