"""Product schemas."""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from src.interfaces.api.schemas.category import CategoryResponse


class ProductImageResponse(BaseModel):
    """Product image schema."""
    id: int
    image_url: str
    is_primary: bool
    display_order: int

    class Config:
        from_attributes = True


class ProductAttributeResponse(BaseModel):
    """Attribute values attached to a product."""
    attribute_id: int
    attribute_name: str
    attribute_type: str
    value: Optional[str] = None

    class Config:
        from_attributes = True


class ProductListItem(BaseModel):
    """Product list item schema."""
    product_id: str
    title: str
    brand: Optional[str] = None
    product_type: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    discount_percent: Optional[float] = None
    currency: str
    stock_status: Optional[str] = None
    primary_image: Optional[str] = None

    class Config:
        from_attributes = True


class ProductDetail(ProductListItem):
    """Detailed product schema."""
    category: Optional[CategoryResponse] = None
    attributes: List[ProductAttributeResponse] = Field(default_factory=list)
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
