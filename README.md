# Marketing Cortex - Multi-Agent AI System

**Production-grade multi-agent AI system for Zocket's ad tech ecosystem**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.1+-orange.svg)](https://langchain.com/)

## 🎯 Overview

Marketing Cortex (ZMC) is a sophisticated multi-agent AI system that orchestrates specialized agents to deliver end-to-end marketing intelligence:

- **Multi-Agent Orchestration**: Supervisor-driven architecture with specialized agents
- **Graph RAG & Agentic RAG**: Hybrid knowledge retrieval (Neo4j + Pinecone + Tavily)
- **Production Observability**: LangSmith tracing and comprehensive evaluation metrics
- **Real-World Integration**: Meta/Google Ads APIs, Creative Studio, Snoop AI

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for Neo4j only)
- Neo4j AuraDB account (or local Neo4j)
- Upstash Redis account (serverless)
- API keys for: Groq, LangSmith, Pinecone, Zep, Tavily

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/Zocket-Marketing-Cortex.git
cd Zocket-Marketing-Cortex
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp env.example .env
# Edit .env with your API keys and Upstash Redis URL
# Get your Upstash Redis URL from: https://console.upstash.com/redis
```

5. **Start infrastructure (Neo4j only - Redis is serverless)**
```bash
docker-compose up -d
```

6. **Initialize database and seed sample data**
```bash
python scripts/seed_data.py
```

7. **Run the application**
```bash
uvicorn src.main:app --reload
```

The API will be available at `http://localhost:5469`

## 📚 API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:5469/docs
- **Alternative Docs**: http://localhost:5469/redoc

### Key Endpoints

- `GET /` - Root endpoint with system info
- `GET /api/health` - Health check for all services
- `POST /api/run-agent` - Main agent orchestration endpoint
- `POST /api/campaigns` - Create campaign in knowledge graph
- `GET /api/campaigns/{id}` - Get campaign hierarchy
- `GET /api/high-performers` - Query high-performing creatives

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Marketing Cortex (ZMC)          │
│           FastAPI Backend               │
├─────────────────────────────────────────┤
│  Supervisor Agent (LangGraph)           │
│       ↓         ↓         ↓             │
│  Performance  Research  Creative        │
│   Analyst    Assistant  Optimizer       │
│       ↓         ↓         ↓             │
│  Knowledge Layer (Neo4j + Pinecone)     │
│  Observability (LangSmith + Langfuse)   │
└─────────────────────────────────────────┘
```

### Components

- **Supervisor Agent**: Intent classification and routing (Phase 2)
- **Performance Analyst**: CSV analysis and insights (Phase 2)
- **Research Assistant**: Web research with Tavily (Phase 2)
- **Creative Optimizer**: Ad copy generation (Phase 2)
- **Knowledge Graph**: Neo4j for structured campaign data
- **Vector Store**: Pinecone for semantic search (Phase 2)
- **Memory**: Zep for conversation persistence
- **Cache**: Redis for performance optimization

## 🧪 Testing

### Test Structure

The project includes comprehensive test coverage:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user workflows
- **Pipeline Tests**: CI/CD automated testing

### Running Tests

**Quick test run:**
```bash
# Run all tests
pytest tests/ -v

# Run specific test types
pytest tests/ -m unit -v          # Unit tests only
pytest tests/ -m integration -v    # Integration tests only
pytest tests/ -m e2e -v            # E2E tests only
```

**With coverage:**
```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
# View coverage report: open htmlcov/index.html
```

**Using test scripts:**
```bash
# Linux/Mac
./scripts/run_tests.sh
./scripts/run_tests.sh --e2e        # Include E2E tests
./scripts/run_tests.sh --coverage   # With coverage

# Windows
scripts\run_tests.bat
scripts\run_tests.bat --e2e
scripts\run_tests.bat --coverage
```

### Test Files

- `tests/test_api_blog_endpoints.py` - Blog API endpoint tests
- `tests/test_blog_ingestion.py` - Blog ingestion unit tests
- `tests/test_vector_store_blog.py` - Vector store blog methods tests
- `tests/test_research_assistant_blog_tool.py` - Agent blog tool tests
- `tests/test_integration.py` - Integration tests
- `tests/test_e2e.py` - End-to-end workflow tests
- `tests/test_frontend_components.py` - Frontend component structure tests

### CI/CD Pipeline

The project includes GitHub Actions CI pipeline (`.github/workflows/ci.yml`) that:
- Runs backend tests with Neo4j service
- Runs frontend linting and TypeScript checks
- Runs integration tests
- Generates coverage reports

### Test Coverage Goals

- Unit tests: >80% coverage
- Integration tests: All critical paths
- E2E tests: All major user workflows

## 📊 Phase 1 Status (Current)

**✅ Completed:**
- [x] Project structure and dependencies
- [x] Neo4j knowledge graph schema
- [x] Zep memory integration
- [x] FastAPI skeleton with /run-agent endpoint
- [x] Health check and monitoring
- [x] Sample data and test infrastructure
- [x] Docker Compose setup
- [x] Render deployment configuration

**📈 Success Criteria Met:**
- ✅ Server responds to health checks
- ✅ Neo4j stores and retrieves campaigns
- ✅ Zep recalls conversation history
- ✅ Basic API documentation generated
- ✅ Sample data loaded successfully

## 🔜 Next Steps (Phase 2)

- [ ] Build Performance Analyst agent
- [ ] Build Research Assistant agent
- [ ] Build Creative Optimizer agent
- [ ] Implement Supervisor orchestration
- [ ] Add LangGraph state management
- [ ] Integrate Pinecone vector store

## 📖 Documentation

- [PROJECT_REFERENCE.md](PROJECT_REFERENCE.md) - Comprehensive project documentation (742 lines)
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference guide (250 lines)
- [API Documentation](http://localhost:5469/docs) - Interactive API docs

## 🛠️ Technology Stack

| Technology | Purpose |
|------------|---------|
| Python 3.10+ | Core language |
| FastAPI | Backend API framework |
| LangGraph | Agent orchestration |
| LangChain | LLM integration |
| Neo4j | Knowledge graph |
| Pinecone | Vector database |
| Zep | Memory management |
| Redis | Caching layer |
| LangSmith | Observability |
| Tavily | Web search |

## 🤝 Contributing

This is a portfolio project for the Zocket AI Agent Developer position. For questions or feedback, please reach out.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🎓 Project Context

This project demonstrates:
- Multi-agent system architecture
- Graph RAG and Agentic RAG implementation
- Production-ready observability and evaluation
- Integration with external APIs and services
- Scalable, modular design patterns

Built as part of the application for the AI Agent Developer role at Zocket.