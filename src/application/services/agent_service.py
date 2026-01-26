"""Agent service for LLM-powered product search and recommendations."""

import os
import logging
import json
import re
from typing import Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_classic.memory.buffer_window import ConversationBufferWindowMemory
from langsmith import Client

from src.agents.tools.product_search_tool import create_product_search_tool
from src.application.services.product_search_service import ProductSearchService
from src.config.settings import settings
from src.config.logging_config import get_logger

load_dotenv()
logger = get_logger(__name__)


class AgentService:
    """Service for LLM agent orchestration with product search tool."""
    
    def __init__(self, product_service: ProductSearchService):
        """Initialize agent service with LLM and product search tool.
        
        Args:
            product_service: ProductSearchService instance (required)
        """
        if not product_service:
            raise ValueError("ProductSearchService is required for AgentService")
        
        try:
            # Configure Groq LLM
            self.llm = ChatGroq(
                model=settings.agent_model,
                groq_api_key=settings.groq_api_key,
                temperature=0,
            )
            
            # Create product search tool
            self.product_search_tool = create_product_search_tool(product_service)
            tools = [self.product_search_tool]
            
            logger.info("Product search tool added to agent")
            
            # Pull ReAct prompt template
            try:
                client = Client()
                self.prompt = client.pull_prompt("hwchase17/react")
            except Exception as e:
                logger.warning(f"Could not pull prompt from LangSmith: {e}. Using default.")
                self.prompt = None
            
            # Store executors and memories per session
            self.sessions = {}
            self.memories = {}
            
            # Save components for dynamic executor creation
            self.tools = tools
            
            logger.info("Agent service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent service: {str(e)}")
            self.llm = None
            self.tools = []
    
    def get_executor(self, session_id: str) -> AgentExecutor:
        """
        Get or create an AgentExecutor for a specific session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            AgentExecutor instance
        """
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Create memory for session
        memory = ConversationBufferWindowMemory(
            k=5,
            return_messages=False,  # ReAct prompt expects string history
            output_key="output",
            memory_key="chat_history"
        )
        self.memories[session_id] = memory
        
        # Define a robust ReAct prompt with chat_history and specific instructions
        template = """You are a helpful E-commerce Shopping Assistant. Your goal is to help users find products from our catalog.

CONVERSATION LOGIC:
1. CHITCHAT: If the user greets you or asks general questions, respond directly without tools.
2. SEARCH: If the user asks for products, ALWAYS use the `search_products` tool.
3. FILTERING & STOCK: 
   - DO NOT filter out products based on `stock_status` unless the user explicitly used keywords like "in stock" or "available". 
   - If the user did NOT specify "in stock", you must present all products returned by the tool (including "out of stock" and "low stock" items) so the user is aware of our full catalog.
4. LIMITS: If you cannot find matches after two searches, provide the best available matches. Do not loop.

TOOLS:
{tools}

REACTION FORMAT (STRICT):
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

IMPORTANT:
- If no tool is needed for the user's request, skip the 'Action:' and 'Action Input:' lines entirely and go straight from 'Thought:' to 'Final Answer:'.
- NEVER use 'Action: None'. If you aren't searching, you aren't taking an Action.
- Every 'Action:' MUST be followed by an 'Action Input:'.
- Use the 'Final Answer:' to speak to the user.

Previous conversation history:
{chat_history}

Question: {input}
Thought: {agent_scratchpad}"""

        react_prompt = PromptTemplate.from_template(template)
        # Create agent
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=react_prompt,
        )
        
        # Create executor
        executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=memory,
            max_iterations=10,
            verbose=True,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            output_key="output"
        )
        
        self.sessions[session_id] = executor
        return executor

    def create_session(self) -> str:
        """
        Create and initialize a new session with a unique UUID.
        
        Returns:
            The new session ID
        """
        import uuid
        session_id = str(uuid.uuid4())
        # Lazy initialization will happen on first use, or we can force it here
        self.get_executor(session_id)
        logger.info(f"Explicitly created new session: {session_id}")
        return session_id

    def get_all_sessions(self) -> list:
        """Get list of all active session IDs."""
        return list(self.sessions.keys())

    def reset_session(self, session_id: str) -> bool:
        """
        Reset/Clear a specific session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session was found and reset, False otherwise
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            if session_id in self.memories:
                del self.memories[session_id]
            logger.info(f"Session {session_id} reset successfully")
            return True
        return False

    def get_session_history(self, session_id: str) -> list:
        """
        Get chat history for a specific session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of messages in the history
        """
        if session_id in self.memories:
            memory = self.memories[session_id]
            # Convert memory buffer to list of dicts
            messages = []
            for msg in memory.chat_memory.messages:
                messages.append({
                    "type": msg.type,
                    "content": msg.content
                })
            return messages
        return []

    def generate_response(self, query: str, session_id: str) -> dict:
        """
        Generate chatbot response using LLM agent with session memory.
        
        Args:
            query: User search query
            session_id: Unique session identifier
            
        Returns:
            Dictionary with response_text and found_products
        """
        if not self.llm:
            return {"response_text": self._get_fallback_response(query), "products": []}
        
        try:
            # Get session-specific executor
            executor = self.get_executor(session_id)
            
            # Invoke agent
            result = executor.invoke({"input": query})
            
            # Extract response text
            response_text = result.get("output", "")
            
            # Extract products from tool observations if any (Deduplicated by ID)
            products_dict = {}
            intermediate_steps = result.get("intermediate_steps", [])
            for action, observation in intermediate_steps:
                if action.tool == "search_products":
                    try:
                        obs_data = json.loads(observation)
                        if obs_data.get("found") and obs_data.get("products"):
                            for p in obs_data["products"]:
                                pid = p.get("product_id")
                                if pid:
                                    products_dict[pid] = p
                    except Exception as e:
                        logger.warning(f"Failed to parse observation for product extraction: {e}")
            
            found_products = list(products_dict.values())
            
            if not response_text:
                return {"response_text": self._get_fallback_response(query), "products": []}
            
            return {
                "response_text": response_text,
                "products": found_products
            }
            
        except Exception as e:
            logger.error(f"Error generating agent response for session {session_id}: {str(e)}")
            return {"response_text": self._get_fallback_response(query), "products": []}
    
    def _get_fallback_response(self, query: str) -> str:
        """
        Generate fallback response when LLM fails.
        
        Args:
            query: User search query
            
        Returns:
            Fallback response text
        """
        return (
            f"I apologize, but I'm having trouble processing your query: '{query}'. "
            "Please try again or rephrase your question."
        )
