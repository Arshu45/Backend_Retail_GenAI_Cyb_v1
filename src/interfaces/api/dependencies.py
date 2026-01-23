"""FastAPI dependencies for dependency injection."""

from typing import Generator
from sqlalchemy.orm import Session

from src.infrastructure.database.connection import get_db
from src.application.services.product_search_service import ProductSearchService
from src.application.services.agent_service import AgentService


# Global service instances (initialized in lifespan)
_product_search_service: ProductSearchService | None = None
_agent_service: AgentService | None = None


def init_services():
    """Initialize global service instances."""
    global _product_search_service, _agent_service
    
    _product_search_service = ProductSearchService()
    _agent_service = AgentService(_product_search_service)


def get_product_search_service() -> ProductSearchService:
    """
    Get product search service instance.
    
    Returns:
        ProductSearchService instance
    """
    if _product_search_service is None:
        raise RuntimeError("Services not initialized. Call init_services() first.")
    return _product_search_service


def get_agent_service() -> AgentService:
    """
    Get agent service instance.
    
    Returns:
        AgentService instance
    """
    if _agent_service is None:
        raise RuntimeError("Services not initialized. Call init_services() first.")
    return _agent_service

