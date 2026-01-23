"""Agent service for LLM-powered product search and recommendations."""

import os
import logging
import json
import re
from typing import Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_classic.memory.buffer_window import ConversationBufferWindowMemory
from langsmith import Client

from src.agents.tools.product_search_tool import create_product_search_tool
from src.application.services.product_search_service import ProductSearchService
from src.config.settings import settings
from src.config.logging_config import get_logger
from src.infrastructure.llm.prompts import RECOMMENDATION_PROMPT

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
1. If the user asks for products, ALWAYS use the `search_products` tool.
2. If the tool returns products, look at their `stock_status`. 
3. If the user asks for "in stock" items, perform a "Thought" step to filter the results from the observation. 
   Do NOT attempt to use a tool for filtering. 
   If no items match the filter, state that clearly in your Final Answer.
4. If you cannot find exactly what the user wants after one or two searches, provide the best available matches and explain the situation. Do not loop endlessly.

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
- Every 'Action:' MUST be followed by an 'Action Input:'.
- If you have enough information, go straight to 'Final Answer:'.
- Do not make up product details. Only use what is provided in 'Observation:'.

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
            output_key="output"  # Fixes multiple output keys warning
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

    def generate_response(self, query: str, session_id: str = "default") -> dict:
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
    
    def generate_recommendations(
        self, 
        query: str, 
        products: list
    ) -> dict:
        """
        Generate structured recommendations using LLM with system prompt.
        
        Args:
            query: User search query
            products: List of product dictionaries with document and metadata
            
        Returns:
            Dictionary with response_text, recommended_product_ids, reasoning, follow_up_questions
        """
        if not self.llm:
            return self._get_fallback_recommendations(query, products)
        
        if not products:
            return {
                "response_text": f"I couldn't find any products matching '{query}'. Please try different keywords.",
                "recommended_product_ids": [],
                "reasoning": "No products found",
                "follow_up_questions": ["Would you like to try a different search?", "Can you provide more details about what you're looking for?"]
            }
        
        try:
            # Format products for LLM
            formatted_products = []
            for i, product in enumerate(products, 1):
                try:
                    doc = json.loads(product.get("document", "{}"))
                    metadata = product.get("metadata", {})
                    
                    product_id = product.get("id", "")
                    title = doc.get("title", "Unknown Product")
                    price = metadata.get("price", 0)
                    stock_status = str(metadata.get("stock_status", "")).replace("_", " ").title()
                    age_group = metadata.get("age_group", "")
                    
                    # Format price with commas
                    price_str = f"₹{int(price):,}" if price else "Price not available"
                    
                    # Build product string
                    product_str = f"{i}. {product_id} - {title} ({price_str}, {stock_status}"
                    if age_group:
                        product_str += f", {age_group.upper()}"
                    product_str += ")"
                    
                    formatted_products.append(product_str)
                except Exception as e:
                    logger.warning(f"Error formatting product for recommendation: {e}")
                    continue
            
            if not formatted_products:
                return self._get_fallback_recommendations(query, products)
            
            # System prompt
            system_prompt = """You are a product recommendation assistant.

RESPONSE FORMAT (JSON):
{
  "response_text": "Natural language summary highlighting the BEST match first",
  "recommended_product_ids": ["PRD148", "PRD72", "PRD66", "PRD45", "PRD89"],  // ALL products, sorted by relevance
  "reasoning": "Why these products match the query",
  "follow_up_questions": ["Question 1?", "Question 2?"]
}

RULES:
1. Include ALL retrieved products in recommended_product_ids (not just top 3)
2. Sort products: in-stock first, then by relevance
3. Mention stock status in response_text
4. Highlight the #1 recommendation in response_text
5. Include 2 follow-up questions
6. Be concise but helpful
7. Return ONLY valid JSON, no markdown or extra text"""

            
            # User prompt
            user_prompt = f"""User Query: "{query}"

Retrieved Products:
{chr(10).join(formatted_products)}

Generate recommendation response."""
            
            # Call LLM using LangChain format
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse JSON response (handle markdown code blocks if present)
            if response_text.startswith("```"):
                # Remove markdown code blocks
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text)
                response_text = response_text.strip()
            
            # Parse JSON
            try:
                result = json.loads(response_text)
                
                # Validate structure
                if not isinstance(result, dict):
                    raise ValueError("Response is not a dictionary")
                
                return {
                    "response_text": result.get("response_text", ""),
                    "recommended_product_ids": result.get("recommended_product_ids", []),
                    "reasoning": result.get("reasoning", ""),
                    "follow_up_questions": result.get("follow_up_questions", [])
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                logger.error(f"Response text: {response_text}")
                return self._get_fallback_recommendations(query, products)
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self._get_fallback_recommendations(query, products)
    
    def _get_fallback_recommendations(self, query: str, products: list) -> dict:
        """
        Generate fallback recommendations when LLM fails.
        
        Args:
            query: User search query
            products: List of product dictionaries
            
        Returns:
            Dictionary with fallback recommendations
        """
        if not products:
            return {
                "response_text": f"I couldn't find any products matching '{query}'. Please try different keywords.",
                "recommended_product_ids": [],
                "reasoning": "No products found",
                "follow_up_questions": ["Would you like to try a different search?", "Can you provide more details?"]
            }
        
        # Sort products: in-stock first
        sorted_products = sorted(
            products,
            key=lambda p: (str(p.get("metadata", {}).get("stock_status", "")).lower() != "in stock", p.get("id", ""))
        )
        
        recommended_ids = [p.get("id", "") for p in sorted_products[:3] if p.get("id")]
        
        return {
            "response_text": f"I found {len(products)} product(s) matching '{query}'. Here are the top recommendations.",
            "recommended_product_ids": recommended_ids,
            "reasoning": "Products sorted by stock availability",
            "follow_up_questions": ["Would you like to see more options?", "Do you need help with anything else?"]
        }
