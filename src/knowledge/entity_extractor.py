"""
Entity Extraction Module for Marketing Blog Content
Extracts marketing entities and relationships using LLM
"""
from typing import List, Dict, Any, Optional, Tuple
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from src.config import settings
from src.core.cache import cache_manager
import logging
import json
import re
import hashlib
import asyncio
from datetime import datetime, timedelta
import groq

logger = logging.getLogger(__name__)


class Entity(BaseModel):
    """Marketing entity model"""
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type: AdPlatform, UserIntent, CreativeType, MarketingStrategy, MarketingConcept")
    confidence: float = Field(0.8, description="Extraction confidence score", ge=0.0, le=1.0)


class Relationship(BaseModel):
    """Entity relationship model"""
    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    type: str = Field(..., description="Relationship type: OPTIMIZES_FOR, RECOMMENDS_AGAINST, CONNECTED_TO, APPLIED_ON")
    confidence: float = Field(0.8, description="Relationship confidence score", ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    """Entity extraction result"""
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)


class EntityExtractor:
    """
    Extracts marketing entities and relationships from blog content using LLM
    """
    
    # Entity types
    ENTITY_TYPES = [
        "AdPlatform",  # Meta Ads, Google Ads, LinkedIn Ads, TikTok Ads, etc.
        "UserIntent",  # purchase-driven, awareness, engagement, retention
        "CreativeType",  # video carousels, image ads, text ads, interactive ads
        "MarketingStrategy",  # seasonal campaigns, urgency tactics, social proof, etc.
        "MarketingConcept",  # CTR, ROAS, A/B testing, conversion optimization, etc.
    ]
    
    # Relationship types
    RELATIONSHIP_TYPES = [
        "OPTIMIZES_FOR",  # Platform → Intent
        "RECOMMENDS_AGAINST",  # Strategy → Platform
        "CONNECTED_TO",  # Concept → Concept, Strategy → Strategy
        "APPLIED_ON",  # Strategy → Platform
    ]
    
    def __init__(self):
        """Initialize entity extractor with LLM"""
        self.llm = ChatGroq(
            model=settings.groq_model,
            temperature=0.1,  # Low temperature for consistent extraction
            groq_api_key=settings.groq_api_key
        )
        # Semaphore to limit concurrent entity extraction requests (max 3 at a time)
        self._extraction_semaphore = asyncio.Semaphore(3)
        # Groq rate limits: 100,000 tokens per day (on-demand tier)
        self.daily_token_limit = 100000
        self.rate_limit_retry_attempts = 3
        self.rate_limit_base_delay = 1.0  # Base delay in seconds
        logger.info("EntityExtractor initialized with rate limiting")
    
    @staticmethod
    def _generate_entity_id(entity_name: str, entity_type: str) -> str:
        """Generate unique entity ID from name and type"""
        # Normalize name (lowercase, remove special chars)
        normalized = re.sub(r'[^a-z0-9]', '_', entity_name.lower())
        # Create hash for uniqueness
        hash_str = hashlib.md5(f"{entity_type}:{entity_name}".encode()).hexdigest()[:8]
        return f"{entity_type}_{normalized}_{hash_str}"
    
    def _get_daily_token_key(self) -> str:
        """Get Redis key for daily token usage tracking"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"groq:token_usage:{today}"
    
    def _get_rate_limit_key(self) -> str:
        """Get Redis key for rate limit status"""
        return "groq:rate_limit:status"
    
    async def _check_token_usage(self) -> Tuple[bool, int]:
        """
        Check current daily token usage
        
        Returns:
            Tuple of (is_within_limit, tokens_used)
        """
        try:
            key = self._get_daily_token_key()
            usage_str = cache_manager.get(key)
            tokens_used = int(usage_str) if usage_str else 0
            
            # Check if we're close to limit (90% threshold)
            threshold = int(self.daily_token_limit * 0.9)
            is_within_limit = tokens_used < threshold
            
            return is_within_limit, tokens_used
        except Exception as e:
            logger.warning(f"Error checking token usage: {e}")
            # On error, assume we're within limit
            return True, 0
    
    async def _increment_token_usage(self, tokens: int):
        """Increment daily token usage counter"""
        try:
            key = self._get_daily_token_key()
            current = cache_manager.get(key) or "0"
            new_total = int(current) + tokens
            
            # Store with TTL until end of day (UTC)
            now = datetime.utcnow()
            end_of_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = int((end_of_day - now).total_seconds())
            
            cache_manager.set(key, str(new_total), ttl=ttl)
            logger.debug(f"Token usage updated: {new_total}/{self.daily_token_limit}")
        except Exception as e:
            logger.warning(f"Error incrementing token usage: {e}")
    
    async def _handle_rate_limit_error(self, error: Exception, attempt: int) -> bool:
        """
        Handle rate limit error with exponential backoff
        
        Args:
            error: The rate limit error
            attempt: Current retry attempt number
            
        Returns:
            True if should retry, False otherwise
        """
        if not isinstance(error, groq.RateLimitError):
            return False
        
        # Extract retry-after time from error message if available
        error_str = str(error)
        retry_after = None
        
        # Try to extract retry time from error message
        retry_match = re.search(r'Please try again in ([\d.]+)s', error_str)
        if retry_match:
            retry_after = float(retry_match.group(1))
        
        # If no retry-after found, use exponential backoff
        if retry_after is None:
            retry_after = self.rate_limit_base_delay * (2 ** (attempt - 1))
        
        # Cap retry delay at 5 minutes
        retry_after = min(retry_after, 300)
        
        logger.warning(
            f"Rate limit hit (attempt {attempt}/{self.rate_limit_retry_attempts}). "
            f"Retrying after {retry_after:.1f}s..."
        )
        
        # Mark rate limit status in cache
        cache_manager.set(
            self._get_rate_limit_key(),
            {"hit_at": datetime.utcnow().isoformat(), "retry_after": retry_after},
            ttl=int(retry_after) + 60
        )
        
        await asyncio.sleep(retry_after)
        return attempt < self.rate_limit_retry_attempts
    
    async def extract_entities(
        self,
        content: str,
        chunk_id: Optional[str] = None,
        url: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract entities and relationships from blog content with rate limiting
        
        Args:
            content: Blog content text
            chunk_id: Optional chunk identifier for linking
            url: Optional URL for linking
            
        Returns:
            ExtractionResult with entities and relationships
        """
        # Check if we're within token limits
        is_within_limit, tokens_used = await self._check_token_usage()
        if not is_within_limit:
            logger.warning(
                f"Token usage limit approaching: {tokens_used}/{self.daily_token_limit}. "
                f"Skipping entity extraction to avoid rate limit."
            )
            return ExtractionResult()
        
        # Use semaphore to limit concurrent extractions
        async with self._extraction_semaphore:
            # Limit content length for LLM processing
            content_preview = content[:2000] if len(content) > 2000 else content
            
            extraction_prompt = f"""Extract marketing entities and relationships from this blog content.

Content:
{content_preview}

Extract the following entity types:
- AdPlatform: Advertising platforms (Meta Ads, Google Ads, LinkedIn Ads, TikTok Ads, etc.)
- UserIntent: User intent types (purchase-driven, awareness, engagement, retention, etc.)
- CreativeType: Ad creative formats (video carousels, image ads, text ads, interactive ads, etc.)
- MarketingStrategy: Marketing strategies and tactics (seasonal campaigns, urgency tactics, social proof, etc.)
- MarketingConcept: Marketing concepts and metrics (CTR, ROAS, A/B testing, conversion optimization, etc.)

Extract relationships:
- OPTIMIZES_FOR: When a platform is optimized for a specific intent (e.g., Meta Ads → purchase-driven)
- RECOMMENDS_AGAINST: When a strategy is not recommended for a platform
- CONNECTED_TO: When concepts or strategies are related (e.g., seasonal campaigns → urgency tactics)
- APPLIED_ON: When a strategy is applied on a platform (e.g., urgency tactics → Google Ads)

Respond with a JSON object:
{{
    "entities": [
        {{
            "name": "Meta Ads",
            "type": "AdPlatform",
            "confidence": 0.95
        }}
    ],
    "relationships": [
        {{
            "source": "Meta Ads",
            "target": "purchase-driven",
            "type": "OPTIMIZES_FOR",
            "confidence": 0.90
        }}
    ]
}}

Only extract entities and relationships that are explicitly mentioned or strongly implied in the content.
Be conservative with confidence scores. Only include relationships if there's clear evidence in the text."""
            
            # Retry logic for rate limit errors
            last_error = None
            for attempt in range(1, self.rate_limit_retry_attempts + 1):
                try:
                    response = await self.llm.ainvoke([HumanMessage(content=extraction_prompt)])
                    response_text = response.content
                    
                    # Estimate token usage (rough: ~4 chars per token)
                    estimated_tokens = len(extraction_prompt + response_text) // 4
                    await self._increment_token_usage(estimated_tokens)
                    
                    # Parse JSON from response - look for JSON object with nested structures
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
                    if not json_match:
                        # Fallback: try simpler pattern
                        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        try:
                            extraction_data = json.loads(json_match.group())
                            
                            # Parse entities
                            entities = []
                            for entity_data in extraction_data.get("entities", []):
                                try:
                                    entity = Entity(**entity_data)
                                    # Filter by confidence threshold
                                    if entity.confidence >= 0.7:
                                        entities.append(entity)
                                except Exception as e:
                                    logger.warning(f"Error parsing entity: {e}")
                            
                            # Parse relationships
                            relationships = []
                            for rel_data in extraction_data.get("relationships", []):
                                try:
                                    relationship = Relationship(**rel_data)
                                    # Filter by confidence threshold
                                    if relationship.confidence >= 0.7:
                                        relationships.append(relationship)
                                except Exception as e:
                                    logger.warning(f"Error parsing relationship: {e}")
                            
                            result = ExtractionResult(entities=entities, relationships=relationships)
                            logger.info(f"Extracted {len(entities)} entities and {len(relationships)} relationships")
                            return result
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing JSON from LLM response: {e}")
                            return ExtractionResult()
                    else:
                        logger.warning("No JSON found in LLM response")
                        return ExtractionResult()
                    
                except groq.RateLimitError as e:
                    last_error = e
                    should_retry = await self._handle_rate_limit_error(e, attempt)
                    if not should_retry:
                        logger.error(
                            f"Rate limit error after {attempt} attempts. "
                            f"Skipping entity extraction for this chunk."
                        )
                        return ExtractionResult()
                    # Continue to retry
                    continue
                    
                except Exception as e:
                    logger.error(f"Error extracting entities: {e}", exc_info=True)
                    return ExtractionResult()
            
            # If we exhausted retries, return empty result
            if last_error:
                logger.error(f"Failed to extract entities after {self.rate_limit_retry_attempts} attempts")
            return ExtractionResult()
    
    def normalize_entity_name(self, name: str) -> str:
        """Normalize entity name for consistent matching"""
        # Remove extra whitespace, lowercase
        normalized = " ".join(name.lower().split())
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(the|a|an)\s+', '', normalized)
        return normalized
