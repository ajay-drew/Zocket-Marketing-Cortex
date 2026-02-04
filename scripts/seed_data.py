"""
Seed sample data into Neo4j for testing
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge.graph_schema import graph_schema
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_sample_data():
    """Seed sample marketing data into Neo4j"""
    
    logger.info("Starting data seeding...")
    
    # Initialize schema
    await graph_schema.initialize_schema()
    
    # Campaign 1: Summer Fashion Campaign
    campaign1 = await graph_schema.create_campaign(
        campaign_id="camp_001",
        name="Summer Fashion 2026",
        objective="CONVERSIONS",
        budget=50000.0,
        start_date="2026-06-01",
        metadata={"vertical": "fashion", "season": "summer"}
    )
    logger.info(f"Created campaign: {campaign1['name']}")
    
    # AdSet 1.1: Women's Dresses
    adset1_1 = await graph_schema.create_adset(
        adset_id="adset_001",
        campaign_id="camp_001",
        name="Women's Summer Dresses",
        targeting={
            "age_range": "25-45",
            "gender": "female",
            "interests": ["fashion", "summer style"]
        },
        budget=20000.0,
        metadata={"category": "dresses"}
    )
    logger.info(f"Created adset: {adset1_1['name']}")
    
    # Creative 1.1.1
    creative1_1_1 = await graph_schema.create_creative(
        creative_id="cr_001",
        adset_id="adset_001",
        name="Floral Dress Promo",
        copy="☀️ Summer's hottest styles are here! Get 30% off floral dresses. Limited time only! 👗",
        image_url="https://example.com/floral-dress.jpg",
        metadata={"theme": "floral", "discount": "30%"}
    )
    logger.info(f"Created creative: {creative1_1_1['name']}")
    
    # Performance data for Creative 1.1.1
    perf1 = await graph_schema.create_performance(
        performance_id="perf_001",
        creative_id="cr_001",
        date="2026-06-15",
        impressions=50000,
        clicks=2500,
        conversions=125,
        spend=1500.0,
        revenue=6250.0
    )
    logger.info(f"Created performance record: ROAS {perf1['roas']:.2f}")
    
    # Creative 1.1.2
    creative1_1_2 = await graph_schema.create_creative(
        creative_id="cr_002",
        adset_id="adset_001",
        name="Beach Wear Collection",
        copy="🏖️ Beach-ready in minutes! Shop our new summer collection. Free shipping on orders $50+",
        image_url="https://example.com/beach-wear.jpg",
        metadata={"theme": "beach", "free_shipping": True}
    )
    logger.info(f"Created creative: {creative1_1_2['name']}")
    
    # Performance data for Creative 1.1.2
    perf2 = await graph_schema.create_performance(
        performance_id="perf_002",
        creative_id="cr_002",
        date="2026-06-15",
        impressions=45000,
        clicks=1800,
        conversions=90,
        spend=1200.0,
        revenue=3600.0
    )
    logger.info(f"Created performance record: ROAS {perf2['roas']:.2f}")
    
    # AdSet 1.2: Men's Casual Wear
    adset1_2 = await graph_schema.create_adset(
        adset_id="adset_002",
        campaign_id="camp_001",
        name="Men's Summer Casual",
        targeting={
            "age_range": "25-50",
            "gender": "male",
            "interests": ["casual fashion", "summer"]
        },
        budget=15000.0,
        metadata={"category": "casual"}
    )
    logger.info(f"Created adset: {adset1_2['name']}")
    
    # Creative 1.2.1
    creative1_2_1 = await graph_schema.create_creative(
        creative_id="cr_003",
        adset_id="adset_002",
        name="Linen Shirts Promo",
        copy="Stay cool this summer! 🌊 Premium linen shirts now 25% off. Breathable & stylish.",
        image_url="https://example.com/linen-shirts.jpg",
        metadata={"theme": "linen", "discount": "25%"}
    )
    logger.info(f"Created creative: {creative1_2_1['name']}")
    
    # Performance data for Creative 1.2.1
    perf3 = await graph_schema.create_performance(
        performance_id="perf_003",
        creative_id="cr_003",
        date="2026-06-15",
        impressions=40000,
        clicks=2000,
        conversions=100,
        spend=1000.0,
        revenue=4000.0
    )
    logger.info(f"Created performance record: ROAS {perf3['roas']:.2f}")
    
    # Campaign 2: Tech Gadgets Campaign
    campaign2 = await graph_schema.create_campaign(
        campaign_id="camp_002",
        name="Smart Tech Summer Sale",
        objective="TRAFFIC",
        budget=30000.0,
        start_date="2026-06-10",
        metadata={"vertical": "electronics", "season": "summer"}
    )
    logger.info(f"Created campaign: {campaign2['name']}")
    
    # AdSet 2.1: Wireless Earbuds
    adset2_1 = await graph_schema.create_adset(
        adset_id="adset_003",
        campaign_id="camp_002",
        name="Premium Wireless Earbuds",
        targeting={
            "age_range": "18-40",
            "interests": ["technology", "music", "fitness"]
        },
        budget=15000.0,
        metadata={"category": "audio"}
    )
    logger.info(f"Created adset: {adset2_1['name']}")
    
    # Creative 2.1.1
    creative2_1_1 = await graph_schema.create_creative(
        creative_id="cr_004",
        adset_id="adset_003",
        name="Noise-Canceling Earbuds",
        copy="🎧 Experience pure sound! Premium noise-canceling earbuds. 40% off + free case!",
        image_url="https://example.com/earbuds.jpg",
        metadata={"feature": "noise-canceling", "discount": "40%"}
    )
    logger.info(f"Created creative: {creative2_1_1['name']}")
    
    # Performance data for Creative 2.1.1
    perf4 = await graph_schema.create_performance(
        performance_id="perf_004",
        creative_id="cr_004",
        date="2026-06-15",
        impressions=60000,
        clicks=3600,
        conversions=180,
        spend=2000.0,
        revenue=9000.0
    )
    logger.info(f"Created performance record: ROAS {perf4['roas']:.2f}")
    
    logger.info("✅ Sample data seeding completed!")
    logger.info(f"Created: 2 campaigns, 3 adsets, 4 creatives, 4 performance records")


async def main():
    """Main execution"""
    try:
        await seed_sample_data()
    finally:
        await graph_schema.close()


if __name__ == "__main__":
    asyncio.run(main())
