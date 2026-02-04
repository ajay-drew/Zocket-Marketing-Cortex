# Marketing Cortex - Project Reference

**Multi-Agent AI System for Zocket's Ad Tech Ecosystem**

---

## 🎯 Project Overview

Marketing Cortex (ZMC) is a production-grade multi-agent AI system designed to provide end-to-end marketing intelligence for Zocket. It combines Graph RAG, Agentic RAG, and multi-agent orchestration to deliver actionable insights for ad campaigns.

### Core Capabilities
- **Performance Analysis** - Analyze campaign metrics and identify optimization opportunities
- **Market Research** - Real-time competitor analysis and trend identification
- **Creative Optimization** - Generate and optimize ad copy based on performance data
- **Intelligent Routing** - Supervisor agent classifies intent and routes to specialized agents

---

## 🏗️ System Architecture

```
User Query
    ↓
Supervisor Agent (LangGraph)
    ↓
├─ Performance Analyst → Neo4j Graph RAG
├─ Research Assistant → Tavily + Pinecone Vector RAG
└─ Creative Optimizer → GPT-4 + Performance Data
    ↓
Unified Response
```

### Technology Stack
- **Backend:** FastAPI, Python 3.10+
- **Agent Framework:** LangChain, LangGraph
- **Knowledge:** Neo4j (graph), Pinecone (vector)
- **Memory:** Zep (conversation persistence)
- **Cache:** Redis
- **Observability:** LangSmith, Langfuse
- **External APIs:** Tavily, Meta/Google Ads

---

## 📋 Implementation Phases

### Phase 1: Foundation (Week 1) ✅ COMPLETE

**Goal:** Build core infrastructure

**Deliverables:**
- ✅ FastAPI backend with 9 endpoints
- ✅ Neo4j knowledge graph (Campaign→AdSet→Creative→Performance)
- ✅ Zep memory integration
- ✅ Redis caching layer
- ✅ Sample data (2 campaigns, 3 adsets, 4 creatives)
- ✅ Test suite with pytest
- ✅ Docker Compose setup
- ✅ Health monitoring

**Success Criteria:**
- ✅ Server responds to health checks
- ✅ Neo4j stores/retrieves campaigns
- ✅ Zep recalls conversation history
- ✅ API documentation generated
- ✅ Sample data loaded

**Key Files:**
```
src/main.py              - FastAPI application
src/api/routes.py        - 9 API endpoints
src/knowledge/graph_schema.py - Neo4j operations
src/core/memory.py       - Zep integration
src/core/cache.py        - Redis caching
scripts/seed_data.py     - Sample data loader
```

---

### Phase 2: Agent Development (Weeks 2-3) 🔄 IN PROGRESS

**Goal:** Build multi-agent system with LangGraph orchestration

**Agents to Build:**

#### 1. Performance Analyst Agent
**File:** `src/agents/performance_analyst.py`
- Parse CSV performance data
- Calculate metrics (CTR, CVR, ROAS, CPC)
- Query Neo4j for campaign insights
- Generate performance reports
- Identify underperforming campaigns

#### 2. Research Assistant Agent
**File:** `src/agents/research_assistant.py`
- Web search via Tavily API
- Competitor analysis
- Trend identification
- Citation tracking
- Self-correction loops

#### 3. Creative Optimizer Agent
**File:** `src/agents/creative_optimizer.py`
- Generate ad copy with Groq (Llama 3)
- A/B test suggestions
- Brand voice consistency
- Performance-based recommendations
- Creative variation generation

#### 4. Supervisor Agent
**File:** `src/agents/supervisor.py`
- Intent classification (performance/research/creative)
- Route queries to appropriate agent
- LangGraph StateGraph implementation
- Multi-agent coordination
- Response aggregation

**Additional Components:**

#### 5. Pinecone Vector Store
**File:** `src/knowledge/vector_store.py`
- Initialize Pinecone index
- Embed documents (sentence-transformers)
- Semantic search
- RAG integration

#### 6. Update /run-agent Endpoint
**File:** `src/api/routes.py`
- Replace placeholder logic
- Initialize Supervisor agent
- Handle multi-turn conversations
- Stream responses (optional)

**Success Criteria:**
- [ ] Intent classification accuracy >90%
- [ ] All 3 agents functional
- [ ] Supervisor routes correctly
- [ ] LangGraph workflows operational
- [ ] Pinecone vector search working

---

### Phase 3: Observability & Evaluation (Week 4)

**Goal:** Add production monitoring and evaluation metrics

**Components to Build:**

#### 1. LangSmith Tracing
**File:** `src/observability/tracing.py`
- Configure LangSmith client
- Add tracing decorators
- Custom run tracking
- Metadata logging

#### 2. Evaluation Metrics
**File:** `src/evaluation/metrics.py`
- Intent classification accuracy
- Task success rate
- Relevance scoring (LLM-as-judge)
- Hallucination detection
- Latency tracking (P95 <10s)

#### 3. Feedback Loops
- User feedback collection
- Automated evaluation runs
- Performance monitoring
- Error tracking

**Success Criteria:**
- [ ] LangSmith traces all agent calls
- [ ] Evaluation metrics computed
- [ ] Feedback loop operational
- [ ] Performance dashboard available

---

### Phase 4: Frontend & Deployment (Weeks 5-6)

**Goal:** Deploy production system with user interface

**Components to Build:**

#### 1. Frontend Dashboard
**Tech:** React/Vue
- Chat interface for queries
- Campaign performance visualizations
- Agent activity monitoring
- WebSocket streaming (optional)

#### 2. Production Deployment
**Platform:** Render
- Deploy FastAPI backend
- Configure Redis service
- Set up Neo4j AuraDB
- Environment variable management
- Health check endpoints

#### 3. Integration with Zocket Products
- Creative Studio API integration
- Snoop AI data pipeline
- Meta/Google Ads API connections
- Real-time data sync

**Success Criteria:**
- [ ] Frontend deployed and accessible
- [ ] Backend deployed on Render
- [ ] All services connected
- [ ] Integration tests passing
- [ ] Uptime >99%

---

## 🎯 Project Goals

### Business Value
1. **Reduce Analysis Time** - Automate campaign performance analysis
2. **Improve ROAS** - Data-driven creative optimization
3. **Competitive Intelligence** - Real-time market insights
4. **Scale Operations** - Handle growing campaign volume

### Technical Excellence
1. **Production-Ready** - Error handling, monitoring, logging
2. **Scalable Architecture** - Modular, async, cacheable
3. **Observable** - Full tracing and metrics
4. **Maintainable** - Clean code, tested, documented

### Innovation
1. **Graph RAG** - Structured reasoning over campaign data
2. **Agentic RAG** - Dynamic information synthesis
3. **Multi-Agent System** - Specialized agents for complex tasks
4. **Self-Correction** - Agents verify and improve outputs

---

## 📊 Success Metrics

### Phase 1 (Complete)
- ✅ 9 API endpoints operational
- ✅ Neo4j stores campaign hierarchy
- ✅ Memory system functional
- ✅ All tests passing

### Phase 2 (Target)
- Intent classification: >90% accuracy
- Task success rate: >85%
- Agent response time: <5s average
- All 3 agents operational

### Phase 3 (Target)
- Relevance score: >4/5
- Hallucination rate: <5%
- P95 latency: <10s
- LangSmith traces: 100% coverage

### Phase 4 (Target)
- System uptime: >99%
- Frontend load time: <2s
- API response time: <1s (P95)
- User satisfaction: >4/5

---

## 🔗 Integration Points

### Zocket Products
- **Creative Studio** - Generate ad creatives based on insights
- **Snoop AI** - Leverage existing competitor intelligence
- **Ad Platforms** - Meta/Google Ads API for real-time data

### External Services
- **Tavily** - Web search and research
- **Groq** - Fast LLM inference (Llama 3, Mixtral)
- **LangSmith** - Tracing and observability
- **Neo4j AuraDB** - Managed graph database
- **Pinecone** - Managed vector database
- **Zep** - Managed memory service

---

## 🚀 Getting Started

### Quick Setup
```bash
# 1. Clone and setup
git clone <repo>
cd Zocket-Marketing-Cortex
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp env.example .env
# Add your API keys to .env

# 4. Start services
docker-compose up -d

# 5. Load sample data
python scripts/seed_data.py

# 6. Run application
uvicorn src.main:app --reload

# 7. Visit http://localhost:8000/docs
```

### Development Workflow
1. Make changes to code
2. Run tests: `pytest -v`
3. Check health: `curl http://localhost:8000/api/v1/health`
4. Test endpoints via Swagger UI
5. Commit and push

---

## 📁 Project Structure

```
Zocket-Marketing-Cortex/
├── src/
│   ├── agents/          # Phase 2: Agent implementations
│   ├── api/             # ✅ API routes and models
│   ├── core/            # ✅ Memory, cache, config
│   ├── knowledge/       # ✅ Graph + Phase 2: Vector
│   ├── observability/   # Phase 3: Tracing
│   └── evaluation/      # Phase 3: Metrics
├── tests/               # ✅ Test suite
├── scripts/             # ✅ Utilities
├── docs/                # Documentation
├── requirements.txt     # ✅ Dependencies
├── docker-compose.yml   # ✅ Infrastructure
└── README.md            # ✅ Overview
```

---

## 🎓 Key Learnings

### What Makes This Strong
1. **Modular Architecture** - Easy to extend and maintain
2. **Production Patterns** - Error handling, logging, monitoring
3. **Test Coverage** - Comprehensive test suite
4. **Clear Documentation** - Easy onboarding
5. **Scalable Design** - Async, cached, distributed

### Best Practices Applied
- Async/await throughout
- Type hints everywhere
- Pydantic validation
- Environment-based config
- Health checks
- Graceful shutdown
- Connection pooling

---

**Status:** Phase 1 Complete ✅ | Phase 2 In Progress 🔄  
**Timeline:** 4-6 weeks total  
**Next:** Build Performance Analyst Agent
