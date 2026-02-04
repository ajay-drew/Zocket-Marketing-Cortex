"""
Structured JSON logging configuration
Provides consistent logging format across all components
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4
from contextvars import ContextVar

# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        
        Args:
            record: Log record
            
        Returns:
            JSON string
        """
        # Get request and session IDs from context
        request_id = request_id_var.get()
        session_id = session_id_var.get()
        
        # Build log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        
        # Add request ID if available
        if request_id:
            log_entry["request_id"] = request_id
        
        # Add session ID if available
        if session_id:
            log_entry["session_id"] = session_id
        
        # Add query if in extra
        if hasattr(record, "query"):
            log_entry["query"] = record.query
        
        # Add metadata if in extra
        if hasattr(record, "metadata"):
            log_entry["metadata"] = record.metadata
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add stack trace for errors
        if record.levelno >= logging.ERROR:
            import traceback
            log_entry["stack_trace"] = traceback.format_stack()
        
        return json.dumps(log_entry)


def setup_structured_logging(level: str = "INFO", use_json: bool = True):
    """
    Setup structured logging configuration
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Whether to use JSON formatting
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Set formatter
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    logging.info("Structured logging configured", extra={"metadata": {"level": level, "format": "json" if use_json else "text"}})


def get_structured_logger(name: str) -> logging.Logger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Add convenience methods for structured logging
    def log_with_context(level: int, msg: str, query: Optional[str] = None, **metadata):
        """
        Log with context (query, session_id, etc.)
        
        Args:
            level: Log level
            msg: Log message
            query: Query string (optional)
            **metadata: Additional metadata
        """
        extra = {}
        if query:
            extra["query"] = query
        if metadata:
            extra["metadata"] = metadata
        
        logger.log(level, msg, extra=extra)
    
    # Add methods to logger
    logger.log_with_context = log_with_context
    
    return logger


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set request ID in context
    
    Args:
        request_id: Request ID (generates new one if None)
        
    Returns:
        Request ID
    """
    if request_id is None:
        request_id = str(uuid4())
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """
    Get current request ID from context
    
    Returns:
        Request ID or None
    """
    return request_id_var.get()


def set_session_id(session_id: Optional[str]):
    """
    Set session ID in context
    
    Args:
        session_id: Session ID
    """
    if session_id:
        session_id_var.set(session_id)


def get_session_id() -> Optional[str]:
    """
    Get current session ID from context
    
    Returns:
        Session ID or None
    """
    return session_id_var.get()
