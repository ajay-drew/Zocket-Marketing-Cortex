"""
Research Assistant Agent - Web research with Tavily and Pinecone RAG
"""
from typing import AsyncIterator, Dict, Any, Optional, List
from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from src.config import settings
from src.integrations.tavily_client import tavily_client
from src.knowledge.vector_store import vector_store
from src.core.memory import memory_manager
import logging
import json

logger = logging.getLogger(__name__)


class ResearchAssistant:
    """
    Research Assistant Agent for web research and analysis
    
    Capabilities:
    - Web search via Tavily
    - Semantic search in stored research (Pinecone)
    - Citation tracking
    - Streaming responses
    - Conversation memory via Zep
    """
    
    def __init__(self):
        """Initialize Research Assistant with tools and LLM"""
        self.llm = ChatGroq(
            model=settings.groq_model,
            temperature=0.3,
            groq_api_key=settings.groq_api_key
        )
        
        # Create tools
        self.tools = self._create_tools()
        
        # Bind tools to LLM
        self.agent = self.llm.bind_tools(self.tools)
        
        logger.info("Research Assistant initialized")
    
    def _create_tools(self) -> List[Tool]:
        """Create LangChain tools for the agent"""
        import asyncio
        
        # Define input schemas for structured tools
        class TavilySearchInput(BaseModel):
            query: str = Field(description="Search query string for web search")
        
        class PineconeSearchInput(BaseModel):
            query: str = Field(description="Search query string for semantic search in stored research")
        
        class BlogSearchInput(BaseModel):
            query: str = Field(description="Search query string for marketing blog content")
        
        # Create async tool functions that accept the query string directly
        # StructuredTool will unpack the dict and pass the query parameter
        async def tavily_search_tool(query: str) -> str:
            """
            Search the web using Tavily API for current information.
            
            Use this tool when you need to:
            - Find recent information or news
            - Research competitors or market trends
            - Get up-to-date data about companies, products, or events
            
            Args:
                query: Search query string
            """
            try:
                logger.debug(f"[TOOL] tavily_search_tool called with query: {query}")
                result = await self._tavily_search_async(query)
                logger.debug(f"[TOOL] tavily_search_tool result length: {len(result)}")
                return result
            except Exception as e:
                logger.error(f"Tavily search error: {e}", exc_info=True)
                return f"Error searching: {str(e)}"
        
        async def pinecone_search_tool(query: str) -> str:
            """
            Search stored research results using semantic search.
            
            Use this tool when you need to:
            - Find previously researched information
            - Get context from past research sessions
            - Retrieve similar research that was done before
            
            Args:
                query: Search query string
            """
            try:
                logger.debug(f"[TOOL] pinecone_search_tool called with query: {query}")
                result = await self._pinecone_search_async(query)
                logger.debug(f"[TOOL] pinecone_search_tool result length: {len(result)}")
                return result
            except Exception as e:
                logger.error(f"Pinecone search error: {e}", exc_info=True)
                return f"Error searching stored research: {str(e)}"
        
        async def blog_search_tool(query: str) -> str:
            """
            Search marketing blog content from ingested blog posts.
            
            Use this tool when you need to:
            - Find information from marketing blogs
            - Get insights from industry experts
            - Research best practices from marketing publications
            - Find examples and case studies from marketing blogs
            
            Args:
                query: Search query string
            """
            try:
                logger.debug(f"[TOOL] blog_search_tool called with query: {query}")
                result = await self._blog_search_async(query)
                logger.debug(f"[TOOL] blog_search_tool result length: {len(result)}")
                return result
            except Exception as e:
                logger.error(f"Blog search error: {e}", exc_info=True)
                return f"Error searching marketing blogs: {str(e)}"
        
        # Create LangChain structured tools for better Groq compatibility
        # Use coroutine parameter for async functions
        # Note: StructuredTool with coroutine expects the function to accept unpacked args
        tools = [
            StructuredTool.from_function(
                func=tavily_search_tool,
                name="tavily_web_search",
                description=(
                    "Search the web for current information, news, competitor analysis, "
                    "and market trends. Returns recent, up-to-date information with citations."
                ),
                args_schema=TavilySearchInput
            ),
            StructuredTool.from_function(
                func=pinecone_search_tool,
                name="search_stored_research",
                description=(
                    "Search previously stored research results using semantic search. "
                    "Useful for finding related research from past sessions."
                ),
                args_schema=PineconeSearchInput
            ),
            StructuredTool.from_function(
                func=blog_search_tool,
                name="search_marketing_blogs",
                description=(
                    "Search marketing blog content from ingested blog posts. "
                    "Use this for finding insights, best practices, examples, and case studies "
                    "from marketing industry blogs like HubSpot, Moz, Content Marketing Institute, etc. "
                    "Returns blog posts with citations."
                ),
                args_schema=BlogSearchInput
            )
        ]
        
        return tools
    
    async def _tavily_search_async(self, query: str) -> str:
        """Async helper for Tavily search"""
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
        
        # Format results for agent
        return self._format_tavily_results(result)
    
    async def _pinecone_search_async(self, query: str) -> str:
        """Async helper for Pinecone search"""
        results = await vector_store.search_similar(
            query=query,
            top_k=5
        )
        
        if not results:
            return "No similar research found in stored results."
        
        # Format results
        formatted = "Stored Research Results:\n"
        for i, result in enumerate(results, 1):
            formatted += f"\n{i}. {result['title']}\n"
            formatted += f"   URL: {result['url']}\n"
            formatted += f"   Relevance: {result['score']:.2f}\n"
            formatted += f"   Content: {result['content'][:200]}...\n"
        
        return formatted
    
    async def _blog_search_async(self, query: str) -> str:
        """Async helper for blog search - filters by content_type=blog_post"""
        results = await vector_store.search_similar(
            query=query,
            top_k=5,
            filter_metadata={"content_type": "blog_post"}
        )
        
        if not results:
            return "No relevant blog posts found. Try a different query or ensure blogs have been ingested."
        
        # Format results with blog-specific information
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
    
    def _format_tavily_results(self, result: Dict[str, Any]) -> str:
        """Format Tavily results for agent consumption"""
        formatted = f"Web Search Results for: {result.get('query', 'Unknown')}\n\n"
        
        # Add answer if available
        if result.get("answer"):
            formatted += f"Summary: {result['answer']}\n\n"
        
        # Add results
        if result.get("results"):
            formatted += "Sources:\n"
            for i, res in enumerate(result["results"], 1):
                formatted += f"\n{i}. {res.get('title', 'No title')}\n"
                formatted += f"   URL: {res.get('url', 'No URL')}\n"
                if res.get("content"):
                    formatted += f"   Content: {res.get('content', '')[:300]}...\n"
        
        # Add metadata
        if result.get("_cached"):
            formatted += "\n[Note: Results from cache]"
        
        return formatted
    
    def _create_agent(self):
        """Create LangChain agent with tools bound to LLM"""
        # Bind tools to LLM for function calling
        return self.llm.bind_tools(self.tools)
    
    async def get_memory_context(self, session_id: str) -> List:
        """Get conversation history from Zep memory"""
        try:
            memory = memory_manager.get_memory(session_id)
            if not memory:
                return []
            
            # Convert Zep messages to LangChain format
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
    
    async def stream_response(
        self,
        query: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Stream agent response token by token
        
        Args:
            query: User query
            session_id: Session identifier
            metadata: Optional metadata
            
        Yields:
            Response tokens as strings
        """
        try:
            logger.info(f"[AGENT] Starting stream_response - Session: {session_id}, Query: {query[:100]}")
            
            # Get conversation history
            logger.debug(f"[AGENT] Fetching memory context for session: {session_id}")
            chat_history = await self.get_memory_context(session_id)
            logger.debug(f"[AGENT] Retrieved {len(chat_history)} messages from history")
            
            # Create system message with tool descriptions
            system_message = SystemMessage(content=f"""You are a Research Assistant for Marketing Cortex.

You have access to these tools:
1. tavily_web_search - Search the web for current information, news, competitor analysis, and market trends
2. search_stored_research - Search previously stored research results using semantic search
3. search_marketing_blogs - Search marketing blog content from ingested blog posts (HubSpot, Moz, Content Marketing Institute, etc.)

When you need information:
- Use tavily_web_search for current information, news, and trends
- Use search_stored_research to find related past research
- Use search_marketing_blogs for marketing insights, best practices, examples, and case studies from industry blogs

Always provide citations with URLs when using search results.
Be concise but comprehensive. Focus on marketing, advertising, and ad tech topics.""")

            # Prepare messages
            messages = [system_message] + chat_history + [HumanMessage(content=query)]
            logger.debug(f"[AGENT] Prepared {len(messages)} messages for LLM")
            
            # Simple agent loop: call LLM, check for tool calls, execute tools, repeat
            max_iterations = 3
            iteration = 0
            final_response = ""
            
            logger.info(f"[AGENT] Starting agent loop (max {max_iterations} iterations)")
            
            while iteration < max_iterations:
                try:
                    logger.debug(f"[AGENT] Iteration {iteration + 1}/{max_iterations} - Invoking LLM with {len(messages)} messages")
                    # Get response from LLM with tools bound
                    response = await self.agent.ainvoke(messages)
                    logger.debug(f"[AGENT] LLM response received - Type: {type(response)}")
                    
                    # Check if response has tool calls
                    tool_calls = getattr(response, 'tool_calls', None) or []
                    logger.debug(f"[AGENT] Tool calls found: {len(tool_calls)}")
                    
                    if tool_calls:
                        logger.info(f"[AGENT] Processing {len(tool_calls)} tool call(s)")
                        # Execute tools
                        messages.append(response)  # Add AI message with tool calls
                        
                        for idx, tool_call in enumerate(tool_calls):
                            logger.debug(f"[AGENT] Processing tool call {idx + 1}/{len(tool_calls)}")
                            # Handle different tool call formats
                            if isinstance(tool_call, dict):
                                tool_name = tool_call.get('name', '')
                                tool_args = tool_call.get('args', {})
                                tool_call_id = tool_call.get('id', f"call_{iteration}")
                            else:
                                # Handle object format
                                tool_name = getattr(tool_call, 'name', '')
                                tool_args = getattr(tool_call, 'args', {})
                                tool_call_id = getattr(tool_call, 'id', f"call_{iteration}")
                            
                            # Find and execute the tool
                            tool_result = None
                            for tool in self.tools:
                                if tool.name == tool_name:
                                    try:
                                        # Extract query from args dict
                                        if isinstance(tool_args, dict):
                                            query_value = tool_args.get('query', '')
                                            logger.info(f"Executing tool: {tool_name} with query: {query_value}")
                                            # For structured tools with coroutine, pass the query directly
                                            # StructuredTool will handle the schema validation
                                            tool_result = await tool.ainvoke({"query": query_value})
                                        else:
                                            # Fallback: extract query if args is not a dict
                                            query_arg = str(tool_args) if tool_args else ''
                                            logger.info(f"Executing tool: {tool_name} with query: {query_arg}")
                                            tool_result = await tool.ainvoke({"query": query_arg})
                                        break
                                    except Exception as e:
                                        logger.error(f"Tool execution error for {tool_name}: {e}", exc_info=True)
                                        import traceback
                                        logger.error(f"Traceback: {traceback.format_exc()}")
                                        tool_result = f"Error executing tool {tool_name}: {str(e)}"
                            
                            if tool_result is None:
                                tool_result = f"Tool {tool_name} not found or execution failed"
                            
                            # Add tool result to messages
                            messages.append(ToolMessage(
                                content=str(tool_result),
                                tool_call_id=tool_call_id
                            ))
                        
                        iteration += 1
                        continue
                    
                    # No tool calls - this is the final response
                    logger.info(f"[AGENT] No tool calls - extracting final response")
                    if hasattr(response, 'content'):
                        final_response = response.content
                        logger.debug(f"[AGENT] Extracted content from response.content (length: {len(final_response)})")
                    elif isinstance(response, str):
                        final_response = response
                        logger.debug(f"[AGENT] Response is string (length: {len(final_response)})")
                    else:
                        final_response = str(response)
                        logger.debug(f"[AGENT] Converted response to string (length: {len(final_response)})")
                    logger.info(f"[AGENT] Final response length: {len(final_response)}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error in agent loop iteration {iteration}: {e}", exc_info=True)
                    final_response = f"I encountered an error: {str(e)}. Please try again."
                    break
            
            # Stream output in chunks
            logger.info(f"[AGENT] Starting to stream response (length: {len(final_response)})")
            chunk_size = 10
            chunk_count = 0
            for i in range(0, len(final_response), chunk_size):
                chunk = final_response[i:i + chunk_size]
                chunk_count += 1
                yield chunk
                import asyncio
                await asyncio.sleep(0.01)
            logger.info(f"[AGENT] Finished streaming {chunk_count} chunks")
            
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
                metadata={"agent": "research_assistant", **(metadata or {})}
            )
            
        except Exception as e:
            logger.error(f"Error streaming response: {e}", exc_info=True)
            yield f"Error: {str(e)}"
    
    async def get_response(
        self,
        query: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get complete agent response (non-streaming)
        
        Args:
            query: User query
            session_id: Session identifier
            metadata: Optional metadata
            
        Returns:
            Complete response string
        """
        response_parts = []
        async for chunk in self.stream_response(query, session_id, metadata):
            response_parts.append(chunk)
        return "".join(response_parts)


# Global research assistant instance
research_assistant = ResearchAssistant()
