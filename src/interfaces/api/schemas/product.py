"""Product schemas.
Migrated to flat schema (2026-02-13)
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from src.interfaces.api.schemas.category import CategoryResponse


class ProductImageResponse(BaseModel):
    """Product image schema."""
    id: int
    image_url: str
    is_primary: int 
    display_order: int

    class Config:
        from_attributes = True


class ProductListItem(BaseModel):
    """Product list item schema."""
    product_id: str
    sku: Optional[str] = None
    title: str
    description: Optional[str] = None
    price: Optional[str] = None  # Stored as VARCHAR in DB
    stock_status: Optional[str] = None
    
    # Direct attribute fields
    color: Optional[str] = None
    size: Optional[str] = None
    product_type: Optional[str] = None
    
    primary_image: Optional[str] = None

    class Config:
        from_attributes = True


class ProductDetail(ProductListItem):
    """Detailed product schema."""
    care_instruction: Optional[str] = None
    categories: List[CategoryResponse] = Field(default_factory=list)
    images: List[ProductImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Product list response schema."""
    products: List[ProductListItem]
    total: int
    page: int = 1
    page_size: int = 20
