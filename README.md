# Marketing Cortex - Multi-Agent AI System

**Multi-agent AI system for Zocket's ad tech ecosystem**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.1+-orange.svg)](https://langchain.com/)

## 🎯 Overview

Marketing Cortex (ZMC) orchestrates specialized AI agents to deliver end-to-end marketing intelligence through multi-step reasoning, hybrid RAG (Graph + Vector), and real-time web search.

## 🏗️ Architecture

![System Architecture](System%20Archi.png)

The system follows a LangGraph-based workflow orchestration pattern with four specialized tools integrated via LangChain StructuredTools.

## 📝 Technical Write-up

### Tools & Technologies

Marketing Cortex leverages a modern AI agent stack built on **LangGraph** for multi-step workflow orchestration, enabling conditional routing between six workflow nodes (query_analysis → tool_selection → execute_tools → evaluate_results → refine_query → synthesize). **LangChain** provides the abstraction layer for LLM integration and tool binding, with **Groq's Llama-3.1-8B-instant** serving as the primary reasoning engine (6000 RPM rate limit).

The system implements **Agentic RAG** through a hybrid retrieval strategy: **Pinecone** vector database (multilingual-e5-large embeddings) for semantic search across ingested blog content and stored research, **Neo4j** knowledge graph for entity relationship traversal (MarketingEntity nodes with OPTIMIZES_FOR, CONNECTED_TO relationships), and **Tavily** web search API for real-time information retrieval. **Zep** manages conversation memory with session-based persistence, while **Upstash Redis** handles aggressive caching (7-day TTL for research queries) and rate limit tracking.

**LangSmith** provides comprehensive observability, automatically tracing all LangGraph nodes, LLM calls (prompts, responses, tokens, latency), and tool invocations. The frontend uses **React** with **Server-Sent Events (SSE)** for real-time token streaming and tool call visibility.

### Challenges & Solutions

Key challenges included Groq's strict rate limits (30 RPM on Llama-3.3-70B), which caused frequent 429 errors during multi-step workflows. This was resolved by switching to Llama-3.1-8B-instant (6000 RPM) and implementing a client-side sliding window rate limiter (5000 RPM) with exponential backoff retries. The rate limiter uses Redis-backed request tracking to prevent exceeding API limits.

Another persistent issue was a Python virtual environment port conflict (e.g., 5469), where even after changing ports, the app failed to start due to a hidden UnicodeEncodeError in UTF-8 handling during logging and Uvicorn binding. This was fixed by enforcing global UTF-8 encoding in the evaluation script and sanitizing debug outputs. Additionally, synchronous Redis operations were blocking the async event loop, resolved by wrapping all cache operations in `asyncio.run_in_executor()`.

Frontend infinite reload loops were caused by `useEffect` dependency cycles in the BlogDataContext, where `fetchBlogSources` was recreated on every render. This was fixed by using `useRef` for the fetching flag and adding cache staleness checks before triggering refreshes.

### Potential Improvements & Next Steps

1. **Latency Optimization**: Cut response time via adaptive LangGraph timeouts, parallel tool calls, and aggressive Redis caching—target <15s P50. Currently, sequential tool execution and synchronous operations add overhead.

2. **Entity Extraction Quality**: Boost entity extraction F1 from 0.121 to >0.70 via refined Groq prompts and dedicated NER models. Current rule-based extraction misses nuanced entity relationships.

3. **User Authentication & Personalization**: Add JWT user authentication with Postgres for persistent user preferences and MemGPT for per-user long-term memory, enabling personalized marketing strategies.

4. **Live Ad Platform Integration**: Integrate Meta/Google Ads APIs for real-time CSV analysis and campaign optimization, moving beyond static blog content to actionable ad performance data.

5. **Production Deployment**: Deploy on AWS Bedrock with Langfuse feedback loops for automatic prompt refinement based on user interactions and evaluation metrics.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for Neo4j only)
- API keys: Groq, LangSmith, Neo4j, Pinecone, Zep, Upstash Redis, Tavily

### Installation

```bash
# Clone and setup
git clone https://github.com/drew-jay/Zocket-Marketing-Cortex.git
cd Zocket-Marketing-Cortex
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your API keys

# Start Neo4j (Redis is serverless)
docker-compose up -d

# Run application
uvicorn src.main:app --reload --port 5469
```

API available at `http://localhost:5469/docs`

## 🛠️ Technology Stack

| Technology | Purpose |
|------------|---------|
| LangGraph | Multi-step workflow orchestration |
| LangChain | LLM integration & tool binding |
| Groq (Llama-3.1-8B) | Agent reasoning & synthesis |
| Pinecone | Vector RAG (semantic search) |
| Neo4j | Knowledge graph (entity relationships) |
| Tavily | Web search API |
| Zep | Conversation memory |
| Upstash Redis | Caching & rate limiting |
| LangSmith | Observability & tracing |
| FastAPI | Backend API framework |
| React | Frontend with SSE streaming |

## 📊 Key Features

- **Multi-Step Reasoning**: LangGraph workflow with query refinement
- **Hybrid RAG**: Combines vector search (Pinecone), graph traversal (Neo4j), and web search (Tavily)
- **Real-Time Streaming**: SSE-based token streaming with tool call visibility
- **Production Observability**: LangSmith tracing for all workflow nodes
- **Rate Limit Management**: Client-side rate limiting with exponential backoff

## 📈 Evaluation Metrics

**Benchmark Dataset:** 20 marketing queries

| Metric | Mean | Min | Max |
|--------|------|-----|-----|
| **Success Rate** | 100% | - | - |
| **Relevance Score** | 0.076 | 0.034 | 0.151 |
| **ROUGE-1 F1** | 0.151 | 0.084 | 0.232 |
| **ROUGE-2 F1** | 0.034 | 0.008 | 0.093 |
| **ROUGE-L F1** | 0.091 | 0.063 | 0.150 |
| **Response Time** | 58.0s | 25.0s | 103.1s |

**Evaluation Method:** Fast rule-based metrics (Word Overlap for Relevance, ROUGE for Summaries) - no LLM judge required.

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## 📖 Documentation

- [PROJECT_REFERENCE.md](PROJECT_REFERENCE.md) - Comprehensive project documentation
- [API Documentation](http://localhost:5469/docs) - Interactive API docs

## 📄 License

MIT License

---

Built as part of the application for the AI Agent Developer role at Zocket.
