"""Search request/response schemas."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search request schema."""
    query: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(default="default", description="Unique session identifier for multi-turn chat")


class ProductResult(BaseModel):
    """Minimal product result for chat display."""
    id: str
    title: str
    price: str
    key_features: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Search response schema."""
    response_text: str
    session_id: Optional[str] = None
    products: List[ProductResult] = Field(default_factory=list)  # Legacy: minimal product info for chat
    recommended_products: List[Dict[str, Any]] = Field(default_factory=list)  # New: full product data for catalog
    follow_up_questions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
