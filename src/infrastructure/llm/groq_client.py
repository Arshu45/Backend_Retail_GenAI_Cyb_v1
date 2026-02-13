"""Groq LLM client wrapper."""

import os
import json
import time
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from groq import Groq
from groq import APIConnectionError, RateLimitError, InternalServerError

from src.config.settings import settings
from src.config.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class GroqClient:
    """Wrapper for Groq LLM client with retry logic."""
    
    def __init__(self):
        """Initialize Groq client."""
        try:
            self.client = Groq(api_key=settings.groq_api_key)
            self.model = settings.groq_model
            logger.info(f"Groq client initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {str(e)}")
            raise
    
    def chat_completion(
        self,
        messages: list,
        temperature: float = 0,
        max_retries: int = 3,
        sleep_seconds: int = 3
    ) -> str:
        """
        Call Groq chat completion API with retry logic.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_retries: Maximum number of retry attempts
            sleep_seconds: Seconds to wait between retries
            
        Returns:
            Response content as string
            
        Raises:
            RuntimeError: If all retries fail
        """
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=messages
                )
                
                return response.choices[0].message.content.strip()
            
            except (APIConnectionError, RateLimitError, InternalServerError) as e:
                last_error = e
                logger.warning(f"[Retry {attempt}/{max_retries}] Groq error: {e}")
                
                if attempt < max_retries:
                    time.sleep(sleep_seconds)
                else:
                    break
            
            except Exception as e:
                logger.error(f"Unexpected error in Groq chat completion: {e}")
                raise RuntimeError(f"Unexpected error: {e}")
        
        raise RuntimeError(
            f"Groq API failed after {max_retries} attempts: {last_error}"
        )
    
    def extract_json(
        self,
        system_prompt: str,
        user_query: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Extract structured JSON from LLM response.
        
        Args:
            system_prompt: System prompt for the LLM
            user_query: User query
            max_retries: Maximum number of retry attempts
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValueError: If JSON parsing fails
            RuntimeError: If API call fails
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        raw_response = self.chat_completion(messages, temperature=0, max_retries=max_retries)
        
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON returned from Groq: {raw_response}")
            raise ValueError(f"Invalid JSON returned:\n{raw_response}")


def get_groq_client() -> GroqClient:
    """
    Get Groq client instance.
    
    Returns:
        GroqClient instance
    """
    return GroqClient()