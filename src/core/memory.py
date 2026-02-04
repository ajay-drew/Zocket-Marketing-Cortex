"""
Memory management using Zep for conversation persistence
"""
from typing import List, Dict, Optional
from zep_python.client import Zep
from zep_python import Memory, Message, Session
from src.config import settings
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation memory using Zep"""
    
    def __init__(self):
        """Initialize Zep client"""
        self.client = Zep(
            api_key=settings.zep_api_key
        )
        logger.info("Zep Memory Manager initialized")
    
    def create_session(self, session_id: str, user_id: Optional[str] = None) -> Session:
        """
        Create a new conversation session
        
        Args:
            session_id: Unique identifier for the session
            user_id: Optional user identifier
            
        Returns:
            Session object
        """
        try:
            session = Session(
                session_id=session_id,
                user_id=user_id or "default_user"
            )
            self.client.memory.add_session(session)
            logger.info(f"Created session: {session_id}")
            return session
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Add a message to the conversation history
        
        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata dictionary
        """
        try:
            message = Message(
                role=role,
                content=content,
                metadata=metadata or {}
            )
            self.client.memory.add(session_id, messages=[message])
            logger.debug(f"Added {role} message to session {session_id}")
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise
    
    def get_memory(self, session_id: str) -> Optional[Memory]:
        """
        Retrieve conversation memory for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Memory object with conversation history
        """
        try:
            memory = self.client.memory.get(session_id)
            logger.debug(f"Retrieved memory for session {session_id}")
            return memory
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return None
    
    def search_sessions(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search across sessions semantically
        
        Args:
            query: Search query
            user_id: Optional user filter
            limit: Maximum number of results
            
        Returns:
            List of relevant session results
        """
        try:
            results = self.client.memory.search_sessions(
                text=query,
                user_id=user_id,
                limit=limit
            )
            logger.debug(f"Found {len(results)} relevant sessions")
            return results
        except Exception as e:
            logger.error(f"Error searching sessions: {e}")
            return []
    
    def delete_session(self, session_id: str) -> None:
        """
        Delete a conversation session
        
        Args:
            session_id: Session identifier
        """
        try:
            self.client.memory.delete(session_id)
            logger.info(f"Deleted session: {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise


# Global memory manager instance
memory_manager = MemoryManager()
