"""Search router for product search and recommendations."""

import json
from fastapi import APIRouter, Depends

from src.interfaces.api.schemas.search import SearchRequest, SearchResponse, ProductResult
from src.interfaces.api.dependencies import (
    get_product_search_service,
    get_agent_service
)
from src.application.services.product_search_service import ProductSearchService
from src.application.services.agent_service import AgentService
from src.utils.formatters import format_price, extract_key_features, generate_follow_up_questions
from src.config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    agent_service: AgentService = Depends(get_agent_service)
) -> SearchResponse:
    """
    Search for products and generate recommendations.
    
    Args:
        request: Search request with query
        product_service: Product search service (injected)
        recommendation_service: Recommendation service (injected)
        
    Returns:
        Search response with products and recommendations
    """
    try:
        # Generate conversational response using Path 1 (Autonomous Agent)
        result = agent_service.generate_response(
            query=request.query,
            session_id=request.session_id
        )

        response_text = result.get("response_text", "")
        agent_products = result.get("products", [])

        # Format products for UI consumption
        formatted_products = []
        for p in agent_products:
            try:
                formatted_products.append(
                    ProductResult(
                        id=p.get("product_id"),
                        title=p.get("title", "Unknown Product"),
                        price=f"₹{int(p.get('price', 0)):,}" if p.get('price') else "Price not available",
                        key_features=[p.get("brand", ""), p.get("color", ""), p.get("size", "")]
                    )
                )
            except Exception as e:
                logger.warning(f"Error formatting product result: {e}")
                continue
        
        # Generate dynamic follow-up questions
        follow_up_questions = agent_service.generate_follow_ups(
            query=request.query,
            response_text=response_text
        )
        
        # Fallback to static if dynamic fails or returns empty
        if not follow_up_questions:
            follow_up_questions = generate_follow_up_questions(agent_products)

        return SearchResponse(
            response_text=response_text,
            session_id=request.session_id,
            products=formatted_products,
            follow_up_questions=follow_up_questions,
            metadata={
                "session_id": request.session_id,
                "mode": "autonomous_agent",
                "total_results": len(formatted_products)
            },
            success=True,
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        return SearchResponse(
            response_text="Something went wrong. Please try again.",
            products=[],
            follow_up_questions=[],
            metadata={},
            success=False,
            error_message=str(e),
        )
