"""Benchmark dataset for evaluation"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class BenchmarkQuery:
    """Single benchmark query with ground truth"""
    
    def __init__(
        self,
        query: str,
        ground_truth: str,
        expected_sources: Optional[List[str]] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.query = query
        self.ground_truth = ground_truth
        self.expected_sources = expected_sources or []
        self.category = category
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query": self.query,
            "ground_truth": self.ground_truth,
            "expected_sources": self.expected_sources,
            "category": self.category,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkQuery":
        """Create from dictionary"""
        return cls(
            query=data["query"],
            ground_truth=data["ground_truth"],
            expected_sources=data.get("expected_sources", []),
            category=data.get("category"),
            metadata=data.get("metadata", {}),
        )


class BenchmarkDataset:
    """Benchmark dataset for evaluation"""
    
    def __init__(self, queries: List[BenchmarkQuery]):
        self.queries = queries
    
    def __len__(self) -> int:
        return len(self.queries)
    
    def __getitem__(self, index: int) -> BenchmarkQuery:
        return self.queries[index]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "queries": [q.to_dict() for q in self.queries],
            "count": len(self.queries),
        }
    
    def save(self, filepath: str) -> None:
        """Save dataset to JSON file"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved benchmark dataset to {filepath} ({len(self.queries)} queries)")
    
    @classmethod
    def load(cls, filepath: str) -> "BenchmarkDataset":
        """Load dataset from JSON file"""
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"Benchmark dataset not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        queries = [BenchmarkQuery.from_dict(q) for q in data.get("queries", [])]
        
        logger.info(f"Loaded benchmark dataset from {filepath} ({len(queries)} queries)")
        return cls(queries)
    
    def get_by_category(self, category: str) -> List[BenchmarkQuery]:
        """Get queries by category"""
        return [q for q in self.queries if q.category == category]
    
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        categories = set(q.category for q in self.queries if q.category)
        return sorted(list(categories))


def create_default_benchmark() -> BenchmarkDataset:
    """
    Create default benchmark dataset with 20 marketing queries
    
    Returns:
        BenchmarkDataset with 20 queries
    """
    queries = [
        BenchmarkQuery(
            query="How to optimize Facebook ad campaigns for e-commerce?",
            ground_truth="Facebook ad optimization for e-commerce involves: 1) Using detailed targeting based on customer data, 2) A/B testing ad creatives (images, copy, CTAs), 3) Optimizing for conversion events (purchases, add-to-cart), 4) Using dynamic product ads for retargeting, 5) Monitoring key metrics (CTR, CPC, ROAS). Focus on mobile-first creatives and leverage Facebook Pixel for tracking.",
            expected_sources=[],
            category="ad_optimization",
            metadata={"difficulty": "medium", "domain": "social_media"}
        ),
        BenchmarkQuery(
            query="What are the best practices for email marketing campaigns?",
            ground_truth="Best practices for email marketing: 1) Segment your audience for personalized content, 2) Use compelling subject lines (A/B test them), 3) Mobile-responsive design is essential, 4) Send at optimal times (typically Tuesday-Thursday mornings), 5) Include clear CTAs, 6) Maintain clean email lists (remove inactive subscribers), 7) Track metrics (open rates, click rates, conversions), 8) Comply with GDPR/CAN-SPAM regulations.",
            expected_sources=[],
            category="email_marketing",
            metadata={"difficulty": "easy", "domain": "email"}
        ),
        BenchmarkQuery(
            query="How to improve SEO for a new website?",
            ground_truth="SEO improvement for new websites: 1) Conduct keyword research to identify target keywords, 2) Optimize on-page elements (title tags, meta descriptions, headers), 3) Create high-quality, original content regularly, 4) Build backlinks from authoritative sites, 5) Ensure mobile-friendliness and fast page load times, 6) Use internal linking structure, 7) Submit sitemap to search engines, 8) Monitor with analytics tools (Google Search Console, Google Analytics).",
            expected_sources=[],
            category="seo",
            metadata={"difficulty": "medium", "domain": "search"}
        ),
        BenchmarkQuery(
            query="What is the difference between CPC and CPM in digital advertising?",
            ground_truth="CPC (Cost Per Click) charges advertisers only when a user clicks on the ad. CPM (Cost Per Mille/Thousand Impressions) charges based on 1,000 ad impressions regardless of clicks. CPC is better for direct response campaigns focused on conversions. CPM is better for brand awareness campaigns where impressions matter more than clicks. Choose CPC when you want to pay for engagement, CPM when you want to pay for reach.",
            expected_sources=[],
            category="advertising_basics",
            metadata={"difficulty": "easy", "domain": "advertising"}
        ),
        BenchmarkQuery(
            query="How to create effective video ad content for YouTube?",
            ground_truth="Effective YouTube video ads: 1) Hook viewers in first 3-5 seconds, 2) Tell a story that resonates with target audience, 3) Include clear value proposition early, 4) Use captions/subtitles (many watch without sound), 5) Strong call-to-action at the end, 6) Optimize for mobile viewing (vertical/square formats work well), 7) Test different lengths (15s, 30s, 60s), 8) Use YouTube's targeting options (demographics, interests, keywords).",
            expected_sources=[],
            category="video_marketing",
            metadata={"difficulty": "medium", "domain": "video"}
        ),
        BenchmarkQuery(
            query="What are the key metrics to track in Google Ads campaigns?",
            ground_truth="Key Google Ads metrics: 1) Click-Through Rate (CTR) - percentage of impressions that result in clicks, 2) Cost Per Click (CPC) - average cost per click, 3) Conversion Rate - percentage of clicks that convert, 4) Cost Per Conversion (CPA) - cost to acquire one conversion, 5) Return on Ad Spend (ROAS) - revenue generated per dollar spent, 6) Quality Score - Google's rating of ad relevance, 7) Impression Share - percentage of available impressions you captured, 8) Search Impression Share - impressions in search results.",
            expected_sources=[],
            category="advertising_basics",
            metadata={"difficulty": "easy", "domain": "search_ads"}
        ),
        BenchmarkQuery(
            query="How to build a content marketing strategy?",
            ground_truth="Content marketing strategy: 1) Define your target audience and buyer personas, 2) Set clear goals (brand awareness, lead generation, thought leadership), 3) Conduct content audit of existing content, 4) Create content calendar with topics aligned to buyer journey, 5) Choose content formats (blog posts, videos, infographics, podcasts), 6) Establish content distribution channels (owned, earned, paid), 7) Set up analytics to measure performance, 8) Iterate based on what resonates with audience.",
            expected_sources=[],
            category="content_marketing",
            metadata={"difficulty": "medium", "domain": "content"}
        ),
        BenchmarkQuery(
            query="What is retargeting and how does it work?",
            ground_truth="Retargeting (remarketing) shows ads to users who previously visited your website but didn't convert. It works by: 1) Placing a tracking pixel/cookie on your site, 2) When users visit, they're added to a retargeting list, 3) As they browse other sites, they see your ads, 4) This keeps your brand top-of-mind and encourages return visits. Benefits: higher conversion rates (users already showed interest), better ROI, brand recall. Use cases: abandoned carts, product views, form abandonment.",
            expected_sources=[],
            category="advertising_basics",
            metadata={"difficulty": "easy", "domain": "retargeting"}
        ),
        BenchmarkQuery(
            query="How to optimize landing pages for conversions?",
            ground_truth="Landing page optimization: 1) Clear, compelling headline that matches ad copy, 2) Single, focused CTA above the fold, 3) Remove navigation to reduce distractions, 4) Social proof (testimonials, reviews, trust badges), 5) Mobile-responsive design with fast load times, 6) A/B test headlines, CTAs, images, forms, 7) Reduce form fields (only ask for essential info), 8) Use urgency/scarcity elements carefully, 9) Match visitor intent from traffic source, 10) Track and analyze conversion funnel.",
            expected_sources=[],
            category="conversion_optimization",
            metadata={"difficulty": "medium", "domain": "web"}
        ),
        BenchmarkQuery(
            query="What are the benefits of influencer marketing?",
            ground_truth="Influencer marketing benefits: 1) Reach targeted, engaged audiences, 2) Build trust through authentic recommendations, 3) Higher engagement rates than traditional ads, 4) Access to niche communities, 5) User-generated content for your brand, 6) Cost-effective compared to traditional advertising, 7) Improved SEO through backlinks and mentions, 8) Real-time feedback and insights. Best for: brand awareness, product launches, reaching younger demographics, building credibility.",
            expected_sources=[],
            category="social_media",
            metadata={"difficulty": "easy", "domain": "influencer"}
        ),
        BenchmarkQuery(
            query="How to measure ROI of social media marketing?",
            ground_truth="Social media ROI measurement: 1) Set clear objectives (sales, leads, brand awareness), 2) Track conversions from social media (UTM parameters, conversion pixels), 3) Calculate revenue attributed to social campaigns, 4) Measure costs (ad spend, tools, time), 5) Calculate ROI = (Revenue - Cost) / Cost × 100, 6) Track engagement metrics (likes, shares, comments, saves), 7) Monitor brand sentiment and mentions, 8) Use analytics tools (Facebook Insights, Twitter Analytics, LinkedIn Analytics, third-party tools).",
            expected_sources=[],
            category="social_media",
            metadata={"difficulty": "medium", "domain": "analytics"}
        ),
        BenchmarkQuery(
            query="What is A/B testing and how to use it in marketing?",
            ground_truth="A/B testing compares two versions (A and B) to see which performs better. Process: 1) Identify element to test (headline, CTA, image, layout), 2) Create variant with single change, 3) Split traffic evenly (50/50), 4) Run test for statistical significance, 5) Analyze results (conversion rate, engagement), 6) Implement winning variant. Use cases: email subject lines, ad copy, landing pages, website CTAs. Best practices: test one variable at a time, ensure sample size is large enough, test for sufficient duration.",
            expected_sources=[],
            category="testing",
            metadata={"difficulty": "easy", "domain": "optimization"}
        ),
        BenchmarkQuery(
            query="How to create a marketing budget for a startup?",
            ground_truth="Startup marketing budget: 1) Allocate 7-12% of revenue for marketing (or 20-30% of revenue for growth-stage startups), 2) Prioritize channels with highest ROI (often digital: SEO, content, social media), 3) Start with low-cost, high-impact tactics (content marketing, SEO, email), 4) Set aside 20-30% for testing new channels, 5) Track every expense and ROI, 6) Focus on channels that align with target audience, 7) Consider tools and software costs, 8) Plan for seasonal fluctuations. Common allocation: 40% digital ads, 30% content/SEO, 20% tools/software, 10% events/experiments.",
            expected_sources=[],
            category="strategy",
            metadata={"difficulty": "medium", "domain": "planning"}
        ),
        BenchmarkQuery(
            query="What is customer lifetime value (CLV) and why is it important?",
            ground_truth="Customer Lifetime Value (CLV) is the total revenue a business expects from a customer over their entire relationship. Calculate: Average Order Value × Purchase Frequency × Customer Lifespan. Importance: 1) Helps determine how much to spend acquiring customers (CAC should be < CLV), 2) Identifies most valuable customer segments, 3) Guides retention strategies, 4) Informs marketing budget allocation, 5) Helps prioritize customer service investments. Higher CLV = more profitable business. Strategies to increase: improve retention, upsell/cross-sell, increase purchase frequency, enhance customer experience.",
            expected_sources=[],
            category="analytics",
            metadata={"difficulty": "medium", "domain": "metrics"}
        ),
        BenchmarkQuery(
            query="How to use marketing automation effectively?",
            ground_truth="Marketing automation best practices: 1) Map customer journey stages, 2) Create workflows for each stage (welcome series, nurture sequences, re-engagement), 3) Segment audiences for personalized messaging, 4) Set up lead scoring to prioritize prospects, 5) Automate email campaigns based on behavior triggers, 6) Integrate with CRM for seamless handoff to sales, 7) Test and optimize workflows regularly, 8) Monitor performance metrics (open rates, click rates, conversions). Common use cases: lead nurturing, abandoned cart recovery, post-purchase follow-up, event-triggered emails.",
            expected_sources=[],
            category="automation",
            metadata={"difficulty": "medium", "domain": "email"}
        ),
        BenchmarkQuery(
            query="What are the latest trends in digital marketing for 2024?",
            ground_truth="2024 digital marketing trends: 1) AI-powered personalization and content generation, 2) Short-form video content (TikTok, Instagram Reels, YouTube Shorts), 3) Voice search optimization, 4) Privacy-first marketing (cookieless tracking, first-party data), 5) Interactive content (polls, quizzes, AR/VR), 6) Social commerce and shoppable posts, 7) Sustainability and purpose-driven marketing, 8) Micro-influencer partnerships, 9) Conversational marketing (chatbots, messaging apps), 10) Video-first strategies across platforms.",
            expected_sources=[],
            category="trends",
            metadata={"difficulty": "easy", "domain": "general"}
        ),
        BenchmarkQuery(
            query="How to improve open rates for email campaigns?",
            ground_truth="Improve email open rates: 1) Write compelling subject lines (personalization, urgency, curiosity, questions), 2) A/B test subject lines, 3) Send at optimal times (Tuesday-Thursday, 9-11 AM or 1-3 PM), 4) Use sender name that recipients recognize, 5) Clean email list regularly (remove inactive subscribers), 6) Segment audience for relevant content, 7) Avoid spam trigger words, 8) Maintain consistent sending schedule, 9) Use preview text effectively, 10) Monitor and improve sender reputation (SPF, DKIM, DMARC).",
            expected_sources=[],
            category="email_marketing",
            metadata={"difficulty": "easy", "domain": "email"}
        ),
        BenchmarkQuery(
            query="What is account-based marketing (ABM) and how does it work?",
            ground_truth="Account-Based Marketing (ABM) targets specific high-value accounts with personalized campaigns. Process: 1) Identify target accounts (ideal customer profile), 2) Research accounts (decision-makers, pain points, goals), 3) Create personalized content and campaigns, 4) Coordinate sales and marketing efforts, 5) Use multiple channels (email, ads, events, direct mail), 6) Measure account engagement and progress. Benefits: higher conversion rates, better alignment with sales, efficient resource use, stronger relationships. Best for: B2B companies with long sales cycles, high-value deals, complex buying committees.",
            expected_sources=[],
            category="strategy",
            metadata={"difficulty": "medium", "domain": "b2b"}
        ),
        BenchmarkQuery(
            query="How to optimize Google Ads for local businesses?",
            ground_truth="Local Google Ads optimization: 1) Use location extensions to show address/phone, 2) Target specific geographic areas (radius targeting, city targeting), 3) Include location keywords in ad copy ('near me', city names), 4) Use call extensions for phone calls, 5) Set up Google My Business integration, 6) Use ad scheduling for business hours, 7) Create location-specific landing pages, 8) Use local inventory ads if applicable, 9) Monitor location performance reports, 10) Leverage reviews and ratings in ads. Focus on: 'near me' searches, local competitors, mobile optimization.",
            expected_sources=[],
            category="local_marketing",
            metadata={"difficulty": "medium", "domain": "local"}
        ),
        BenchmarkQuery(
            query="What is the difference between organic and paid social media?",
            ground_truth="Organic social media: Free content posted on social platforms, reaches followers and their networks through engagement. Limited reach due to algorithm changes. Paid social media: Sponsored posts/ads that reach broader audiences beyond followers, targeted by demographics, interests, behaviors. Key differences: Organic = free but limited reach, slower results, relies on engagement. Paid = costs money but guaranteed reach, faster results, precise targeting. Best practice: Combine both - use organic for community building and engagement, paid for reach and conversions. Organic builds brand, paid drives action.",
            expected_sources=[],
            category="social_media",
            metadata={"difficulty": "easy", "domain": "social_media"}
        ),
    ]
    
    return BenchmarkDataset(queries)


def load_benchmark_dataset(filepath: Optional[str] = None) -> BenchmarkDataset:
    """
    Load benchmark dataset from file or create default
    
    Args:
        filepath: Optional path to benchmark JSON file. If None, creates default dataset.
        
    Returns:
        BenchmarkDataset
    """
    if filepath:
        return BenchmarkDataset.load(filepath)
    else:
        return create_default_benchmark()
