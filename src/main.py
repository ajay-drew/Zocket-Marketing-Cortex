"""
Main FastAPI application for Marketing Cortex
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from src.api.routes import router
from src.knowledge.graph_schema import graph_schema
from src.core.cache import cache_manager
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting Marketing Cortex...")
    
    # Initialize Neo4j schema
    try:
        await graph_schema.initialize_schema()
        logger.info("Neo4j schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j schema: {e}")
    
    # Connect to Redis
    try:
        await cache_manager.connect()
        logger.info("Redis cache connected")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
    
    logger.info("Marketing Cortex started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Marketing Cortex...")
    
    # Close Neo4j connection
    try:
        await graph_schema.close()
        logger.info("Neo4j connection closed")
    except Exception as e:
        logger.error(f"Error closing Neo4j: {e}")
    
    # Disconnect Redis
    try:
        await cache_manager.disconnect()
        logger.info("Redis disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting Redis: {e}")
    
    logger.info("Marketing Cortex shut down complete")


# Create FastAPI app
app = FastAPI(
    title="Marketing Cortex",
    description="Multi-Agent AI System for Zocket's Ad Tech Ecosystem",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1", tags=["Marketing Cortex"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Marketing Cortex",
        "version": "0.1.0",
        "status": "running",
        "phase": "1 - Foundation",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
