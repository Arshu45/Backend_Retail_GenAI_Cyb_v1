"""Health check router."""

from fastapi import APIRouter

from src.interfaces.api.schemas.common import HealthResponse
from src.interfaces.api.dependencies import (
    get_product_search_service,
    get_agent_service
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Health status of the application and services
    """
    try:
        product_service = get_product_search_service()
        agent_service = get_agent_service()
        
        return HealthResponse(
            status="healthy",
            agent_service=agent_service is not None,
            product_service=product_service is not None,
            message="All services operational"
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            agent_service=False,
            product_service=False,
            message=str(e)
        )
