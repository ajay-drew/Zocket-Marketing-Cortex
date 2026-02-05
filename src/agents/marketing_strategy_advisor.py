"""
Marketing Strategy Advisor Agent - LangGraph-based multi-step reasoning agent
Implements Agentic RAG with query refinement and multi-source synthesis
"""
from typing import AsyncIterator, Dict, Any, Optional, List, TypedDict, Annotated
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from src.core.groq_rate_limited import RateLimitedChatGroq as ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from src.config import settings
from src.integrations.tavily_client import tavily_client
from src.knowledge.vector_store import vector_store
from src.core.memory import memory_manager
from src.observability import (
    trace_agent_execution,
    get_structured_logger,
    set_session_id,
    get_alert_manager
)
from src.observability.langsmith_config import get_langsmith_tracer
from langchain_core.callbacks import CallbackManager
import logging
import json
import time

logger = get_structured_logger(__name__)
alert_manager = get_alert_manager()


class AgentState(TypedDict):
    """State for LangGraph workflow"""
    messages: Annotated[List, add_messages]
    query: str
    original_query: str
    tool_results: Dict[str, Any]
    selected_tools: List[str]
    result_quality: Dict[str, float]
    refined_query: Optional[str]
    synthesis_input: Optional[Dict[str, Any]]
    final_response: Optional[str]
    tool_call_events: List[Dict[str, Any]]  # For SSE streaming


class MarketingStrategyAdvisor:
    """
    Marketing Strategy Advisor Agent with LangGraph workflow
    
    Capabilities:
    - Multi-step reasoning with LangGraph
    - Dynamic tool selection
    - Query refinement based on result quality
    - Multi-source synthesis with contradiction resolution
    - Streaming responses with tool call visibility
    - Conversation memory via Zep
    """
    
    def __init__(self):
        """Initialize Marketing Strategy Advisor with tools and LLM"""
        self.llm = ChatGroq(
            model=settings.groq_model,
            temperature=0.3,
            groq_api_key=settings.groq_api_key
        )
        
        # Create tools
        self.tools = self._create_tools()
        
        # Bind tools to LLM
        self.agent = self.llm.bind_tools(self.tools)
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
        
        logger.info("Marketing Strategy Advisor initialized with LangGraph workflow")
    
    def _create_tools(self) -> List[StructuredTool]:
        """Create LangChain tools for the agent"""
        
        # Define input schemas
        class TavilySearchInput(BaseModel):
            query: str = Field(description="Search query string for web search")
        
        class PineconeSearchInput(BaseModel):
            query: str = Field(description="Search query string for semantic search in stored research")
        
        class BlogSearchInput(BaseModel):
            query: str = Field(description="Search query string for marketing blog content")
        
        class GraphSearchInput(BaseModel):
            query: str = Field(description="Search query string for graph-based entity retrieval")
        
        # Tool functions (need to capture self for async methods)
        advisor_self = self
        
        async def tavily_search_tool(query: str) -> str:
            """Search the web using Tavily API for current information, news, and trends."""
            try:
                logger.debug(f"[TOOL] tavily_web_search called with query: {query}")
                result = await tavily_client.search_with_fallback(
                    query=query,
                    search_type="research",
                    max_results=5
                )
                
                # Store results in Pinecone for future RAG
                if result.get("results"):
                    await vector_store.upsert_research(
                        query=query,
                        research_results=result.get("results", []),
                        metadata={"source": "tavily", "search_type": "research"}
                    )
                
                return advisor_self._format_tavily_results(result)
            except Exception as e:
                logger.error(f"Tavily search error: {e}", exc_info=True)
                return f"Error searching web: {str(e)}"
        
        async def pinecone_search_tool(query: str) -> str:
            """Search previously stored research results using semantic search."""
            try:
                logger.debug(f"[TOOL] search_stored_research called with query: {query}")
                results = await vector_store.search_similar(
                    query=query,
                    top_k=5
                )
                
                if not results:
                    return "No similar research found in stored results."
                
                formatted = "Stored Research Results:\n"
                for i, result in enumerate(results, 1):
                    formatted += f"\n{i}. {result['title']}\n"
                    formatted += f"   URL: {result['url']}\n"
                    formatted += f"   Relevance: {result['score']:.2f}\n"
                    formatted += f"   Content: {result['content'][:200]}...\n"
                
                return formatted
            except Exception as e:
                logger.error(f"Pinecone search error: {e}", exc_info=True)
                return f"Error searching stored research: {str(e)}"
        
        async def blog_search_tool(query: str) -> str:
            """Search marketing blog content from ingested blog posts."""
            try:
                logger.debug(f"[TOOL] search_marketing_blogs called with query: {query}")
                results = await vector_store.search_similar(
                    query=query,
                    top_k=5,
                    filter_metadata={"content_type": "blog_post"}
                )
                
                if not results:
                    return "No relevant blog posts found. Try a different query or ensure blogs have been ingested."
                
                formatted = f"Marketing Blog Results for: {query}\n\n"
                for i, result in enumerate(results, 1):
                    blog_name = result.get('metadata', {}).get('blog_name', 'Unknown Blog')
                    title = result.get('title', result.get('metadata', {}).get('title', 'No title'))
                    url = result.get('url', '')
                    content = result.get('content', '')
                    
                    formatted += f"{i}. {title}\n"
                    formatted += f"   Blog: {blog_name}\n"
                    formatted += f"   URL: {url}\n"
                    formatted += f"   Relevance: {result['score']:.2f}\n"
                    formatted += f"   Excerpt: {content[:300]}...\n\n"
                
                return formatted
            except Exception as e:
                logger.error(f"Blog search error: {e}", exc_info=True)
                return f"Error searching marketing blogs: {str(e)}"
        
        async def graph_search_tool(query: str) -> str:
            """Search marketing entities and relationships using knowledge graph."""
            try:
                logger.debug(f"[TOOL] search_marketing_graph called with query: {query}")
                from src.knowledge.graph_schema import graph_schema
                from src.knowledge.vector_store import vector_store
                
                # Find entities matching the query
                matching_entities = await graph_schema.find_entities_by_query(
                    query_text=query,
                    limit=5
                )
                
                if not matching_entities:
                    return "No matching entities found in knowledge graph. Try a different query or ensure entities have been extracted from blog content."
                
                formatted = f"Graph-Based Search Results for: {query}\n\n"
                formatted += "Found Entities:\n"
                
                # Collect chunk IDs from related blog posts
                chunk_ids_to_retrieve = set()
                
                for entity in matching_entities:
                    entity_id = entity.get("id")
                    entity_name = entity.get("name")
                    entity_type = entity.get("entity_type")
                    
                    formatted += f"\n- {entity_name} ({entity_type})\n"
                    
                    # Get entity context (related entities and blog posts)
                    context = await graph_schema.get_entity_context(
                        entity_id=entity_id,
                        include_blog_posts=True,
                        max_related=3,
                        max_blog_posts=5
                    )
                    
                    # Add related entities
                    if context.get("related_entities"):
                        formatted += "  Related entities:\n"
                        for rel in context["related_entities"][:3]:
                            rel_entity = rel["entity"]
                            formatted += f"    - {rel_entity.get('name')} ({rel['relationship_type']})\n"
                    
                    # Collect blog post chunk IDs
                    for blog_post in context.get("blog_posts", []):
                        chunk_id = blog_post.get("chunk_id")
                        if chunk_id:
                            chunk_ids_to_retrieve.add(chunk_id)
                
                # Retrieve blog chunks from Pinecone using chunk IDs
                if chunk_ids_to_retrieve:
                    formatted += "\n\nRelated Blog Content:\n"
                    # Note: Pinecone doesn't support direct ID lookup in the current implementation
                    # We'll use the entity names to search Pinecone instead
                    for entity in matching_entities[:3]:  # Limit to top 3 entities
                        entity_name = entity.get("name")
                        # Search Pinecone for content mentioning this entity
                        search_results = await vector_store.search_similar(
                            query=f"{entity_name} {query}",
                            top_k=3,
                            filter_metadata={"content_type": "blog_post"}
                        )
                        
                        for result in search_results:
                            formatted += f"\n- {result.get('title', 'No title')}\n"
                            formatted += f"  URL: {result.get('url', '')}\n"
                            formatted += f"  Relevance: {result.get('score', 0):.2f}\n"
                            formatted += f"  Excerpt: {result.get('content', '')[:200]}...\n"
                
                return formatted
            except Exception as e:
                logger.error(f"Graph search error: {e}", exc_info=True)
                return f"Error searching knowledge graph: {str(e)}"
        
        # Create structured tools with coroutine parameter for async functions
        tools = [
            StructuredTool.from_function(
                coroutine=tavily_search_tool,
                name="tavily_web_search",
                description=(
                    "Search the web for current information, news, competitor analysis, "
                    "and market trends. Returns recent, up-to-date information with citations."
                ),
                args_schema=TavilySearchInput
            ),
            StructuredTool.from_function(
                coroutine=pinecone_search_tool,
                name="search_stored_research",
                description=(
                    "Search previously stored research results using semantic search. "
                    "Useful for finding related research from past sessions."
                ),
                args_schema=PineconeSearchInput
            ),
            StructuredTool.from_function(
                coroutine=blog_search_tool,
                name="search_marketing_blogs",
                description=(
                    "Search marketing blog content from ingested blog posts. "
                    "Use this for finding insights, best practices, examples, and case studies "
                    "from marketing industry blogs like HubSpot, Moz, Content Marketing Institute, etc. "
                    "Returns blog posts with citations."
                ),
                args_schema=BlogSearchInput
            ),
            StructuredTool.from_function(
                coroutine=graph_search_tool,
                name="search_marketing_graph",
                description=(
                    "Search marketing entities and relationships using knowledge graph. "
                    "Use this when you need to find connections between marketing concepts, platforms, strategies, or intents. "
                    "Returns entities with their relationships and related blog content. "
                    "Best for queries about entity relationships, e.g., 'What platforms optimize for purchase intent?' "
                    "or 'What strategies are connected to seasonal campaigns?'"
                ),
                args_schema=GraphSearchInput
            )
        ]
        
        return tools
    
    def _format_tavily_results(self, result: Dict[str, Any]) -> str:
        """Format Tavily results for agent consumption"""
        formatted = f"Web Search Results for: {result.get('query', 'Unknown')}\n\n"
        
        if result.get("answer"):
            formatted += f"Summary: {result['answer']}\n\n"
        
        if result.get("results"):
            formatted += "Sources:\n"
            for i, res in enumerate(result["results"], 1):
                formatted += f"\n{i}. {res.get('title', 'No title')}\n"
                formatted += f"   URL: {res.get('url', 'No URL')}\n"
                if res.get("content"):
                    formatted += f"   Content: {res.get('content', '')[:300]}...\n"
        
        if result.get("_cached"):
            formatted += "\n[Note: Results from cache]"
        
        return formatted
    
    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("query_analysis", self._query_analysis_node)
        workflow.add_node("tool_selection", self._tool_selection_node)
        workflow.add_node("execute_tools", self._execute_tools_node)
        workflow.add_node("evaluate_results", self._evaluate_results_node)
        workflow.add_node("refine_query", self._refine_query_node)
        workflow.add_node("synthesize", self._synthesize_node)
        
        # Add tool execution node
        tool_node = ToolNode(self.tools)
        workflow.add_node("tools", tool_node)
        
        # Define edges
        workflow.set_entry_point("query_analysis")
        workflow.add_edge("query_analysis", "tool_selection")
        workflow.add_edge("tool_selection", "execute_tools")
        workflow.add_conditional_edges(
            "execute_tools",
            self._should_use_tools,
            {
                "tools": "tools",
                "evaluate": "evaluate_results"
            }
        )
        workflow.add_edge("tools", "evaluate_results")
        workflow.add_conditional_edges(
            "evaluate_results",
            self._should_refine_query,
            {
                "refine": "refine_query",
                "synthesize": "synthesize"
            }
        )
        workflow.add_edge("refine_query", "tool_selection")
        workflow.add_edge("synthesize", END)
        
        return workflow.compile()
    
    async def _query_analysis_node(self, state: AgentState) -> AgentState:
        """Analyze query intent and determine required tools"""
        query = state.get("query") or state.get("original_query", "")
        
        logger.info(f"[WORKFLOW] Query analysis: {query[:100]}")
        
        # Analyze query to determine which tools are needed
        analysis_prompt = f"""Analyze this marketing query and determine which tools are needed:
Query: {query}

Available tools:
1. search_marketing_blogs - For marketing insights, best practices, case studies from industry blogs
2. tavily_web_search - For current information, news, trends, competitor analysis
3. search_stored_research - For related past research

Respond with a JSON object:
{{
    "needed_tools": ["tool1", "tool2"],
    "query_type": "insight|news|research|mixed",
    "reasoning": "brief explanation"
}}"""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=analysis_prompt)])
            analysis_text = response.content
            
            # Parse JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', analysis_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                # Fallback: use all tools for complex queries
                analysis = {
                    "needed_tools": ["search_marketing_blogs", "tavily_web_search"],
                    "query_type": "mixed",
                    "reasoning": "Defaulting to comprehensive search"
                }
            
            state["selected_tools"] = analysis.get("needed_tools", ["search_marketing_blogs"])
            
            # Emit detailed reasoning event
            reasoning_steps = [
                {
                    "step": 1,
                    "action": "Query Analysis",
                    "reasoning": analysis.get("reasoning", "Analyzing query intent"),
                    "decision": f"Query type: {analysis.get('query_type', 'mixed')}. Selected tools: {', '.join(analysis.get('needed_tools', []))}",
                    "tools": analysis.get("needed_tools", [])
                }
            ]
            
            state["tool_call_events"].append({
                "type": "query_analysis",
                "query": query,
                "analysis": analysis,
                "reasoning_steps": reasoning_steps
            })
            
            logger.info(f"[WORKFLOW] Selected tools: {state['selected_tools']}")
        except Exception as e:
            logger.error(f"Query analysis error: {e}", exc_info=True)
            # Default to blog search
            state["selected_tools"] = ["search_marketing_blogs"]
        
        return state
    
    async def _tool_selection_node(self, state: AgentState) -> AgentState:
        """Prepare tool calls based on selected tools"""
        query = state.get("refined_query") or state.get("query") or state.get("original_query", "")
        selected_tools = state.get("selected_tools", [])
        
        logger.info(f"[WORKFLOW] Tool selection: {selected_tools}")
        
        # Create tool call messages
        tool_calls = []
        for tool_name in selected_tools:
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if tool:
                # Create a tool call message
                tool_calls.append({
                    "name": tool_name,
                    "args": {"query": query}
                })
                state["tool_call_events"].append({
                    "type": "tool_call_start",
                    "tool": tool_name,
                    "query": query
                })
        
        state["messages"].append(HumanMessage(content=f"Query: {query}"))
        
        return state
    
    async def _execute_tools_node(self, state: AgentState) -> AgentState:
        """Execute selected tools"""
        selected_tools = state.get("selected_tools", [])
        query = state.get("refined_query") or state.get("query") or state.get("original_query", "")
        
        logger.info(f"[WORKFLOW] Executing tools: {selected_tools}")
        
        # Prepare messages for LLM with tool calls
        messages = state.get("messages", [])
        
        # Add system message
        system_msg = SystemMessage(content="""You are a Marketing Strategy Advisor. 
Use the available tools to research the query. Call the appropriate tools based on the query type.""")
        
        # Get LLM response with tool calls
        try:
            response = await self.agent.ainvoke([system_msg] + messages[-1:])
            state["messages"].append(response)
            
            # Check for tool calls
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls:
                # Handle both list and single tool call, or Mock objects
                try:
                    tool_call_count = len(tool_calls) if isinstance(tool_calls, (list, tuple)) else 1
                    logger.info(f"[WORKFLOW] LLM requested {tool_call_count} tool calls")
                except (TypeError, AttributeError):
                    # Handle Mock objects or other types
                    logger.debug(f"[WORKFLOW] Tool calls detected but couldn't get count")
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
        
        return state
    
    def _should_use_tools(self, state: AgentState) -> str:
        """Determine if tools should be called"""
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "evaluate"
    
    async def _evaluate_results_node(self, state: AgentState) -> AgentState:
        """Evaluate result quality"""
        messages = state.get("messages", [])
        tool_results = {}
        result_quality = {}
        
        # Extract tool results from messages
        for msg in messages:
            if isinstance(msg, ToolMessage):
                # ToolMessage doesn't have name, need to track from tool_call_id
                # For now, use content to infer tool or track from previous tool calls
                content = msg.content if hasattr(msg, 'content') else str(msg)
                
                # Try to infer tool name from content or use generic
                tool_name = "unknown"
                if "Marketing Blog Results" in content:
                    tool_name = "search_marketing_blogs"
                elif "Web Search Results" in content or "Sources:" in content:
                    tool_name = "tavily_web_search"
                elif "Stored Research Results" in content:
                    tool_name = "search_stored_research"
                elif "Graph-Based Search Results" in content or "Found Entities:" in content:
                    tool_name = "search_marketing_graph"
                
                tool_results[tool_name] = content
                
                # Evaluate quality
                quality = self._evaluate_result_quality(content)
                result_quality[tool_name] = quality
                
                # Calculate result metrics
                results_count = len(content.split('\n')) if content else 0
                word_count = len(content.split()) if content else 0
                
                # Emit detailed reasoning about tool results
                reasoning = f"Tool '{tool_name}' returned {results_count} result lines with quality score {quality:.2f}. "
                if quality < 0.5:
                    reasoning += "Results are below optimal quality threshold."
                elif quality >= 0.8:
                    reasoning += "Results meet high quality standards."
                else:
                    reasoning += "Results are acceptable but could be improved."
                
                state["tool_call_events"].append({
                    "type": "tool_call_result",
                    "tool": tool_name,
                    "results_count": results_count,
                    "quality_score": quality,
                    "word_count": word_count,
                    "reasoning": reasoning
                })
        
        state["tool_results"] = tool_results
        state["result_quality"] = result_quality
        
        # Calculate overall quality
        if result_quality:
            avg_quality = sum(result_quality.values()) / len(result_quality)
            result_count = sum(1 for r in tool_results.values() if r and len(r) > 50)
        else:
            avg_quality = 0.0
            result_count = 0
        
        state["result_quality"]["overall"] = avg_quality
        state["result_quality"]["result_count"] = result_count
        
        # Emit evaluation reasoning
        evaluation_reasoning = f"Evaluated {len(tool_results)} tool results. "
        evaluation_reasoning += f"Average quality: {avg_quality:.2f}, Total results: {result_count}. "
        
        if avg_quality < 0.6 or result_count < 2:
            evaluation_reasoning += "Results are insufficient. Query refinement may be needed."
            next_action = "refine_query"
        else:
            evaluation_reasoning += "Results are sufficient. Proceeding to synthesis."
            next_action = "synthesize"
        
        state["tool_call_events"].append({
            "type": "evaluation",
            "overall_quality": avg_quality,
            "result_count": result_count,
            "reasoning": evaluation_reasoning,
            "next_action": next_action
        })
        
        logger.info(f"[WORKFLOW] Result quality: {result_quality}")
        
        return state
    
    def _evaluate_result_quality(self, content: str) -> float:
        """Evaluate quality of tool result (0.0 to 1.0)"""
        if not content or len(content) < 50:
            return 0.2
        
        # Check for error messages
        if "error" in content.lower() or "no results" in content.lower():
            return 0.1
        
        # Check for actual content
        if "http" in content or "URL" in content:
            return 0.8
        
        # Default quality based on length
        if len(content) > 500:
            return 0.7
        elif len(content) > 200:
            return 0.5
        else:
            return 0.3
    
    def _should_refine_query(self, state: AgentState) -> str:
        """Determine if query should be refined"""
        quality = state.get("result_quality", {})
        overall_quality = quality.get("overall", 0.0)
        result_count = quality.get("result_count", 0)
        
        # Refine if quality is low or results are insufficient
        if overall_quality < 0.6 or result_count < 2:
            # Check if we've already refined
            if state.get("refined_query"):
                # Already refined once, proceed to synthesis
                return "synthesize"
            return "refine"
        
        return "synthesize"
    
    async def _refine_query_node(self, state: AgentState) -> AgentState:
        """Refine query if results are insufficient"""
        original_query = state.get("original_query") or state.get("query", "")
        tool_results = state.get("tool_results", {})
        result_quality = state.get("result_quality", {})
        
        logger.info(f"[WORKFLOW] Refining query: {original_query}")
        
        refinement_prompt = f"""The original query "{original_query}" returned insufficient results.

Current results quality: {result_quality.get('overall', 0.0):.2f}
Result count: {result_quality.get('result_count', 0)}

Refine the query to get better results. You can:
1. Broaden the query (add related terms)
2. Narrow the query (be more specific)
3. Rephrase using different terminology

Respond with a JSON object:
{{
    "refined_query": "improved query text",
    "strategy": "broaden|narrow|rephrase",
    "reasoning": "why this refinement will help"
}}"""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=refinement_prompt)])
            refinement_text = response.content
            
            # Parse JSON
            import re
            json_match = re.search(r'\{[^}]+\}', refinement_text, re.DOTALL)
            if json_match:
                refinement = json.loads(json_match.group())
                refined_query = refinement.get("refined_query", original_query)
            else:
                # Fallback: add marketing context
                refined_query = f"{original_query} marketing strategy best practices"
            
            state["refined_query"] = refined_query
            state["query"] = refined_query
            
            refinement_strategy = refinement.get("strategy", "rephrase")
            refinement_reasoning = refinement.get("reasoning", "Improving query to get better results")
            
            state["tool_call_events"].append({
                "type": "query_refinement",
                "original": original_query,
                "refined": refined_query,
                "strategy": refinement_strategy,
                "reasoning": f"Refinement strategy: {refinement_strategy}. {refinement_reasoning}"
            })
            
            logger.info(f"[WORKFLOW] Query refined: {original_query} -> {refined_query}")
        except Exception as e:
            logger.error(f"Query refinement error: {e}", exc_info=True)
            # Fallback: proceed to synthesis
            state["refined_query"] = original_query
        
        return state
    
    async def _synthesize_node(self, state: AgentState) -> AgentState:
        """Synthesize results from multiple sources"""
        query = state.get("original_query") or state.get("query", "")
        tool_results = state.get("tool_results", {})
        
        logger.info(f"[WORKFLOW] Synthesizing results from {len(tool_results)} sources")
        
        # Emit synthesis reasoning
        sources_list = list(tool_results.keys())
        synthesis_reasoning = f"Combining insights from {len(sources_list)} sources: {', '.join(sources_list)}. "
        synthesis_reasoning += "Identifying key themes, resolving contradictions, and prioritizing recommendations by relevance."
        
        state["tool_call_events"].append({
            "type": "synthesis_start",
            "sources": sources_list,
            "reasoning": synthesis_reasoning
        })
        
        # Prepare synthesis input
        synthesis_input = {
            "query": query,
            "blog_results": tool_results.get("search_marketing_blogs", ""),
            "web_results": tool_results.get("tavily_web_search", ""),
            "stored_results": tool_results.get("search_stored_research", ""),
            "graph_results": tool_results.get("search_marketing_graph", "")
        }
        
        state["synthesis_input"] = synthesis_input
        
        # Generate synthesis
        synthesis_prompt = f"""You are synthesizing marketing research from multiple sources to answer this query: {query}

Sources:
- Marketing Blogs: {synthesis_input['blog_results'][:1000] if synthesis_input['blog_results'] else 'No blog results'}
- Web Search: {synthesis_input['web_results'][:1000] if synthesis_input['web_results'] else 'No web results'}
- Stored Research: {synthesis_input['stored_results'][:1000] if synthesis_input['stored_results'] else 'No stored results'}
- Knowledge Graph: {synthesis_input['graph_results'][:1000] if synthesis_input['graph_results'] else 'No graph results'}

Task:
1. Identify key insights from each source
2. Resolve any contradictions between sources
3. Prioritize recommendations by relevance and authority
4. Generate a coherent marketing strategy with actionable recommendations

Format your response as:
- Executive Summary (2-3 sentences)
- Key Insights (numbered list with citations)
- Recommended Strategy (actionable steps)
- Sources (list of URLs)

Always include citations (URLs) for each insight."""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=synthesis_prompt)])
            final_response = response.content
            
            state["final_response"] = final_response
            state["messages"].append(AIMessage(content=final_response))
            
            logger.info(f"[WORKFLOW] Synthesis complete: {len(final_response)} characters")
        except Exception as e:
            logger.error(f"Synthesis error: {e}", exc_info=True)
            state["final_response"] = f"Error synthesizing results: {str(e)}"
        
        return state
    
    async def get_memory_context(self, session_id: str) -> List:
        """Get conversation history from Zep memory"""
        try:
            memory = await memory_manager.get_memory_async(session_id)
            if not memory:
                return []
            
            messages = []
            for message in memory.messages:
                if message.role == "user":
                    messages.append(HumanMessage(content=message.content))
                elif message.role == "assistant":
                    messages.append(AIMessage(content=message.content))
                elif message.role == "system":
                    messages.append(SystemMessage(content=message.content))
            
            return messages
        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            return []
    
    @trace_agent_execution
    async def stream_response(
        self,
        query: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream agent response with tool call events
        
        Yields:
            Dict with 'type' and 'content' keys for SSE streaming
        """
        start_time = time.time()
        set_session_id(session_id)
        
        try:
            logger.log_with_context(
                logging.INFO,
                "Starting agent stream response",
                query=query[:200],
                session_id=session_id
            )
            
            # Get conversation history
            chat_history = await self.get_memory_context(session_id)
            
            # Initialize state
            initial_state: AgentState = {
                "messages": chat_history,
                "query": query,
                "original_query": query,
                "tool_results": {},
                "selected_tools": [],
                "result_quality": {},
                "refined_query": None,
                "synthesis_input": None,
                "final_response": None,
                "tool_call_events": []
            }
            
            # Run workflow with LangSmith tracing
            # Get LangSmith tracer for automatic tracing of all nodes
            tracer = get_langsmith_tracer()
            config = {}
            if tracer:
                callback_manager = CallbackManager([tracer])
                config = {"callbacks": callback_manager}
                logger.debug(f"[LangSmith] Tracing workflow execution with callbacks - Session: {session_id}")
            
            final_state = await self.workflow.ainvoke(initial_state, config=config)
            
            # Stream tool call events (reasoning steps)
            for event in final_state.get("tool_call_events", []):
                # Emit event with full details for frontend reasoning display
                yield {
                    "type": event["type"],
                    **event  # Include all event properties
                }
            
            # Stream final response
            final_response = final_state.get("final_response", "No response generated")
            
            # Stream response in chunks
            chunk_size = 10
            for i in range(0, len(final_response), chunk_size):
                chunk = final_response[i:i + chunk_size]
                yield {
                    "type": "token",
                    "content": chunk
                }
                import asyncio
                await asyncio.sleep(0.01)
            
            # Store in memory
            await memory_manager.add_message(
                session_id=session_id,
                role="user",
                content=query,
                metadata=metadata
            )
            await memory_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=final_response,
                metadata={"agent": "marketing_strategy_advisor", **(metadata or {})}
            )
            
            # Track performance
            duration = time.time() - start_time
            alert_manager.record_latency(duration, "agent", "stream_response")
            logger.log_with_context(
                logging.INFO,
                f"Agent stream response completed in {duration:.2f}s",
                query=query[:200],
                session_id=session_id,
                metadata={"duration": duration, "response_length": len(final_response)}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            alert_manager.record_error("stream_response_error", "agent", {"error": str(e), "query": query[:200]})
            logger.log_with_context(
                logging.ERROR,
                f"Error streaming response: {e}",
                query=query[:200],
                session_id=session_id,
                metadata={"duration": duration, "error": str(e)}
            )
            yield {
                "type": "error",
                "content": f"Error: {str(e)}"
            }
    
    async def get_response(
        self,
        query: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get complete agent response (non-streaming)"""
        set_session_id(session_id)
        
        # Get conversation history
        chat_history = await self.get_memory_context(session_id)
        
        # Initialize state
        initial_state: AgentState = {
            "messages": chat_history,
            "query": query,
            "original_query": query,
            "tool_results": {},
            "selected_tools": [],
            "result_quality": {},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        # Run workflow
        final_state = await self.workflow.ainvoke(initial_state)
        
        # Get final response
        final_response = final_state.get("final_response", "No response generated")
        
        # Store in memory
        await memory_manager.add_message(
            session_id=session_id,
            role="user",
            content=query,
            metadata=metadata
        )
        await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=final_response,
            metadata={"agent": "marketing_strategy_advisor", **(metadata or {})}
        )
        
        return final_response


# Global marketing strategy advisor instance
marketing_strategy_advisor = MarketingStrategyAdvisor()
