"""
Neo4j Knowledge Graph Schema for Marketing Entities
"""
from neo4j import AsyncGraphDatabase
from typing import Dict, List, Optional
import logging
import json
from src.config import settings

logger = logging.getLogger(__name__)


class GraphSchema:
    """Manages Neo4j knowledge graph schema and operations"""
    
    # Schema definitions
    CONSTRAINTS = [
        "CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (c:Campaign) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT adset_id IF NOT EXISTS FOR (a:AdSet) REQUIRE a.id IS UNIQUE",
        "CREATE CONSTRAINT creative_id IF NOT EXISTS FOR (cr:Creative) REQUIRE cr.id IS UNIQUE",
        "CREATE CONSTRAINT performance_id IF NOT EXISTS FOR (p:Performance) REQUIRE p.id IS UNIQUE",
    ]
    
    INDEXES = [
        "CREATE INDEX campaign_name IF NOT EXISTS FOR (c:Campaign) ON (c.name)",
        "CREATE INDEX adset_name IF NOT EXISTS FOR (a:AdSet) ON (a.name)",
        "CREATE INDEX creative_name IF NOT EXISTS FOR (cr:Creative) ON (cr.name)",
        "CREATE INDEX performance_date IF NOT EXISTS FOR (p:Performance) ON (p.date)",
    ]
    
    def __init__(self):
        """Initialize Neo4j driver"""
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        logger.info("Neo4j driver initialized")
    
    async def close(self):
        """Close Neo4j driver"""
        await self.driver.close()
        logger.info("Neo4j driver closed")
    
    async def initialize_schema(self):
        """Create constraints and indexes"""
        async with self.driver.session(database=settings.neo4j_database) as session:
            # Create constraints
            for constraint in self.CONSTRAINTS:
                try:
                    await session.run(constraint)
                    logger.info(f"Created constraint: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"Constraint may already exist: {e}")
            
            # Create indexes
            for index in self.INDEXES:
                try:
                    await session.run(index)
                    logger.info(f"Created index: {index[:50]}...")
                except Exception as e:
                    logger.warning(f"Index may already exist: {e}")
    
    async def create_campaign(
        self,
        campaign_id: str,
        name: str,
        objective: str,
        budget: float,
        start_date: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a Campaign node
        
        Args:
            campaign_id: Unique campaign identifier
            name: Campaign name
            objective: Campaign objective (e.g., CONVERSIONS, TRAFFIC)
            budget: Campaign budget
            start_date: Campaign start date (ISO format)
            metadata: Additional metadata
            
        Returns:
            Created campaign node
        """
        query = """
        CREATE (c:Campaign {
            id: $campaign_id,
            name: $name,
            objective: $objective,
            budget: $budget,
            start_date: $start_date,
            created_at: datetime(),
            metadata: $metadata
        })
        RETURN c
        """
        
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(
                query,
                campaign_id=campaign_id,
                name=name,
                objective=objective,
                budget=budget,
                start_date=start_date,
                metadata=json.dumps(metadata or {})  # Serialize dict to JSON string
            )
            record = await result.single()
            logger.info(f"Created campaign: {campaign_id}")
            return dict(record["c"])
    
    async def create_adset(
        self,
        adset_id: str,
        campaign_id: str,
        name: str,
        targeting: Dict,
        budget: float,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create an AdSet node and link to Campaign
        
        Args:
            adset_id: Unique adset identifier
            campaign_id: Parent campaign ID
            name: AdSet name
            targeting: Targeting parameters
            budget: AdSet budget
            metadata: Additional metadata
            
        Returns:
            Created adset node
        """
        query = """
        MATCH (c:Campaign {id: $campaign_id})
        CREATE (a:AdSet {
            id: $adset_id,
            name: $name,
            targeting: $targeting,
            budget: $budget,
            created_at: datetime(),
            metadata: $metadata
        })
        CREATE (c)-[:HAS_ADSET]->(a)
        RETURN a
        """
        
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(
                query,
                adset_id=adset_id,
                campaign_id=campaign_id,
                name=name,
                targeting=json.dumps(targeting),  # Serialize dict to JSON string
                budget=budget,
                metadata=json.dumps(metadata or {})  # Serialize dict to JSON string
            )
            record = await result.single()
            logger.info(f"Created adset: {adset_id} under campaign: {campaign_id}")
            return dict(record["a"])
    
    async def create_creative(
        self,
        creative_id: str,
        adset_id: str,
        name: str,
        copy: str,
        image_url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a Creative node and link to AdSet
        
        Args:
            creative_id: Unique creative identifier
            adset_id: Parent adset ID
            name: Creative name
            copy: Ad copy text
            image_url: Optional image URL
            metadata: Additional metadata
            
        Returns:
            Created creative node
        """
        query = """
        MATCH (a:AdSet {id: $adset_id})
        CREATE (cr:Creative {
            id: $creative_id,
            name: $name,
            copy: $copy,
            image_url: $image_url,
            created_at: datetime(),
            metadata: $metadata
        })
        CREATE (a)-[:HAS_CREATIVE]->(cr)
        RETURN cr
        """
        
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(
                query,
                creative_id=creative_id,
                adset_id=adset_id,
                name=name,
                copy=copy,
                image_url=image_url,
                metadata=json.dumps(metadata or {})  # Serialize dict to JSON string
            )
            record = await result.single()
            logger.info(f"Created creative: {creative_id} under adset: {adset_id}")
            return dict(record["cr"])
    
    async def create_performance(
        self,
        performance_id: str,
        creative_id: str,
        date: str,
        impressions: int,
        clicks: int,
        conversions: int,
        spend: float,
        revenue: float
    ) -> Dict:
        """
        Create a Performance node and link to Creative
        
        Args:
            performance_id: Unique performance record ID
            creative_id: Parent creative ID
            date: Performance date (ISO format)
            impressions: Number of impressions
            clicks: Number of clicks
            conversions: Number of conversions
            spend: Amount spent
            revenue: Revenue generated
            
        Returns:
            Created performance node
        """
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cvr = (conversions / clicks * 100) if clicks > 0 else 0
        roas = (revenue / spend) if spend > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        
        query = """
        MATCH (cr:Creative {id: $creative_id})
        CREATE (p:Performance {
            id: $performance_id,
            date: $date,
            impressions: $impressions,
            clicks: $clicks,
            conversions: $conversions,
            spend: $spend,
            revenue: $revenue,
            ctr: $ctr,
            cvr: $cvr,
            roas: $roas,
            cpc: $cpc,
            created_at: datetime()
        })
        CREATE (cr)-[:HAS_PERFORMANCE]->(p)
        RETURN p
        """
        
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(
                query,
                performance_id=performance_id,
                creative_id=creative_id,
                date=date,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                spend=spend,
                revenue=revenue,
                ctr=ctr,
                cvr=cvr,
                roas=roas,
                cpc=cpc
            )
            record = await result.single()
            logger.info(f"Created performance: {performance_id} for creative: {creative_id}")
            return dict(record["p"])
    
    async def get_campaign_hierarchy(self, campaign_id: str) -> Dict:
        """
        Get complete campaign hierarchy with all related entities
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Campaign hierarchy with adsets, creatives, and performance
        """
        query = """
        MATCH (c:Campaign {id: $campaign_id})
        OPTIONAL MATCH (c)-[:HAS_ADSET]->(a:AdSet)
        OPTIONAL MATCH (a)-[:HAS_CREATIVE]->(cr:Creative)
        OPTIONAL MATCH (cr)-[:HAS_PERFORMANCE]->(p:Performance)
        RETURN c, collect(DISTINCT a) as adsets, 
               collect(DISTINCT cr) as creatives,
               collect(DISTINCT p) as performances
        """
        
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(query, campaign_id=campaign_id)
            record = await result.single()
            
            if not record:
                return {}
            
            return {
                "campaign": dict(record["c"]),
                "adsets": [dict(a) for a in record["adsets"] if a],
                "creatives": [dict(cr) for cr in record["creatives"] if cr],
                "performances": [dict(p) for p in record["performances"] if p]
            }
    
    async def query_high_performers(
        self,
        min_roas: float = 2.0,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query high-performing creatives
        
        Args:
            min_roas: Minimum ROAS threshold
            limit: Maximum number of results
            
        Returns:
            List of high-performing creatives with metrics
        """
        query = """
        MATCH (c:Campaign)-[:HAS_ADSET]->(a:AdSet)-[:HAS_CREATIVE]->(cr:Creative)
        MATCH (cr)-[:HAS_PERFORMANCE]->(p:Performance)
        WHERE p.roas >= $min_roas
        RETURN c.name as campaign_name, 
               a.name as adset_name,
               cr.name as creative_name,
               cr.copy as copy,
               avg(p.roas) as avg_roas,
               sum(p.conversions) as total_conversions,
               sum(p.spend) as total_spend
        ORDER BY avg_roas DESC
        LIMIT $limit
        """
        
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(query, min_roas=min_roas, limit=limit)
            records = await result.data()
            logger.info(f"Found {len(records)} high performers (ROAS >= {min_roas})")
            return records


# Global graph schema instance
graph_schema = GraphSchema()
