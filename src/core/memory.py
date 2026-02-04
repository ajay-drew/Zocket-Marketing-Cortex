"""
Memory management using Zep for conversation persistence
"""
from typing import List, Dict, Optional
from zep_python import ZepClient
from zep_python.memory import Memory, Message, Session
from src.config import settings
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation memory using Zep"""
    
    def __init__(self):
        """Initialize Zep client"""
        self.client = ZepClient(
            api_url=settings.zep_api_url,
            api_key=settings.zep_api_key
        )
        logger.info("Zep Memory Manager initialized")
    
    async def create_session(self, session_id: str, user_id: Optional[str] = None) -> Session:
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
            await self.client.memory.add_session(session)
            logger.info(f"Created session: {session_id}")
            return session
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    async def add_message(
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
            await self.client.memory.add_memory(session_id, message)
            logger.debug(f"Added {role} message to session {session_id}")
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise
    
    async def get_memory(self, session_id: str) -> Optional[Memory]:
        """
        Retrieve conversation memory for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Memory object with conversation history
        """
        try:
            memory = await self.client.memory.get_memory(session_id)
            logger.debug(f"Retrieved memory for session {session_id}")
            return memory
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return None
    
    async def search_memory(
        self,
        session_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search conversation history semantically
        
        Args:
            session_id: Session identifier
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of relevant messages
        """
        try:
            results = await self.client.memory.search_memory(
                session_id=session_id,
                query=query,
                limit=limit
            )
            logger.debug(f"Found {len(results)} relevant messages")
            return results
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []
    
    async def delete_session(self, session_id: str) -> None:
        """
        Delete a conversation session
        
        Args:
            session_id: Session identifier
        """
        try:
            await self.client.memory.delete_memory(session_id)
            logger.info(f"Deleted session: {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise


# Global memory manager instance
memory_manager = MemoryManager()
