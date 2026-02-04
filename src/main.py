"""
Main FastAPI application for Marketing Cortex
"""
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import router
from src.config import settings
from src.core.cache import cache_manager
from src.knowledge.graph_schema import graph_schema

# Configure logging - use stdout for better visibility in Windows cmd
# Uvicorn will capture both stdout and stderr, but stdout is more visible
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Use stdout for Windows cmd visibility
    ],
    force=True  # Force reconfiguration
)

# Get logger
logger = logging.getLogger(__name__)

# Set specific loggers to appropriate levels
logging.getLogger("src.agents").setLevel(logging.DEBUG)
logging.getLogger("src.api").setLevel(logging.DEBUG)

# Configure uvicorn access logger
logging.getLogger("uvicorn.access").setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming HTTP requests"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get client IP
        client_ip = request.client.host if request.client else 'unknown'
        
        # Log incoming request
        request_msg = f"→ {request.method} {request.url.path} - Client: {client_ip}"
        logger.info(request_msg)
        
        # Special logging for agent/stream endpoint
        if "/agent/stream" in request.url.path:
            logger.info(f"[MIDDLEWARE] Intercepted /agent/stream request - Method: {request.method}")
            logger.info(f"[MIDDLEWARE] Request path: {request.url.path}")
            logger.info(f"[MIDDLEWARE] Request URL: {request.url}")
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {request.method} {request.url.path} - Error: {e}", exc_info=True)
            raise
        
        # Calculate duration
        process_time = time.time() - start_time
        
        # Log response
        response_msg = f"← {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s"
        logger.info(response_msg)
        
        # Special logging for 404s
        if response.status_code == 404 and "/agent/stream" in request.url.path:
            logger.error(f"[MIDDLEWARE] 404 ERROR for /agent/stream!")
            logger.error(f"[MIDDLEWARE] This means the route was not found by FastAPI")
            logger.error(f"[MIDDLEWARE] Check if server was restarted after route changes")
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    import asyncio
    
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Marketing Cortex...")
    logger.info("=" * 60)
    
    # Initialize Neo4j schema
    try:
        await graph_schema.initialize_schema()
        logger.info("✓ Neo4j schema initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Neo4j schema: {e}", exc_info=True)
    
    # Connect to Redis (synchronous)
    try:
        cache_manager.connect()
        logger.info("✓ Redis cache connected")
    except Exception as e:
        logger.warning(f"✗ Failed to connect to Redis: {e}")
        logger.warning("  Redis caching will be disabled")
    
    logger.info("=" * 60)
    logger.info("Marketing Cortex started successfully")
    logger.info(f"Server listening on: 0.0.0.0:{settings.port}")
    logger.info(f"API: http://127.0.0.1:{settings.port}/api")
    logger.info(f"Docs: http://127.0.0.1:{settings.port}/docs")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Marketing Cortex...")
    
    # Close Neo4j connection
    try:
        await graph_schema.close()
        logger.info("✓ Neo4j connection closed")
    except asyncio.CancelledError:
        logger.warning("Neo4j shutdown cancelled (server interrupted)")
    except Exception as e:
        logger.error(f"✗ Error closing Neo4j: {e}", exc_info=True)
    
    # Disconnect Redis (synchronous)
    try:
        cache_manager.disconnect()
        logger.info("✓ Redis disconnected")
    except Exception as e:
        logger.error(f"✗ Error disconnecting Redis: {e}", exc_info=True)
    
    logger.info("Marketing Cortex shut down complete")


# Create FastAPI app
app = FastAPI(
    title="Marketing Cortex",
    description="Multi-Agent AI System for Zocket's Ad Tech Ecosystem",
    version="0.1.0",
    lifespan=lifespan
)

# Add request logging middleware (before CORS)
app.add_middleware(RequestLoggingMiddleware)

# Configure CORS - Allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Default Vite port
        "http://127.0.0.1:5173",
        "*"  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers for SSE
)

# Include routes
app.include_router(router, prefix="/api", tags=["Marketing Cortex"])


@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("[ROOT] Root endpoint accessed")
    return {
        "name": "Marketing Cortex",
        "version": "0.1.0",
        "status": "running",
        "phase": "2 - Research Assistant",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting uvicorn server on 0.0.0.0:{settings.port}")
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="debug",
        access_log=True,
        use_colors=True,
        # Ensure logs go to console
        log_config=None  # Use our custom logging config instead of uvicorn's default
    )
