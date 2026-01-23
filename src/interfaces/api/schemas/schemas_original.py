"""
Pydantic schemas for request/response models
Aligned with dynamic category-attribute architecture
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================
# Agent / Search Schemas
# ============================================================

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class ProductResult(BaseModel):
    id: str
    title: str
    price: str
    key_features: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    response_text: str
    products: List[ProductResult] = Field(default_factory=list)  # Legacy: minimal product info for chat
    recommended_products: List["ProductListItem"] = Field(default_factory=list)  # New: full product data for catalog
    follow_up_questions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None



# ============================================================
# CATEGORY SCHEMAS
# ============================================================

class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# ATTRIBUTE / FILTER SCHEMAS
# ============================================================

class AttributeMasterResponse(BaseModel):
    attribute_id: int
    name: str
    data_type: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CategoryAttributeResponse(BaseModel):
    attribute: AttributeMasterResponse
    is_required: bool
    is_filterable: bool
    display_order: int

    class Config:
        from_attributes = True


class ProductAttributeResponse(BaseModel):
    """
    Attribute values attached to a product
    """
    attribute_id: int
    attribute_name: str
    attribute_type: str
    value: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# PRODUCT IMAGE SCHEMA
# ============================================================

class ProductImageResponse(BaseModel):
    id: int
    image_url: str
    is_primary: bool
    display_order: int

    class Config:
        from_attributes = True


# ============================================================
# PRODUCT SCHEMAS
# ============================================================

class ProductListItem(BaseModel):
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
    category: Optional[CategoryResponse] = None
    attributes: List[ProductAttributeResponse] = Field(default_factory=list)
    images: List[ProductImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: List[ProductListItem]
    total: int
    page: int = 1
    page_size: int = 20


# ============================================================
# FILTER METADATA (FACET CONFIG)
# ============================================================

class FilterOption(BaseModel):
    value: str
    label: str
    count: int = 0


class FilterConfig(BaseModel):
    attribute_id: int
    attribute_name: str
    display_name: str
    data_type: str = Field(..., description="enum | number | boolean | string")
    filter_type: str = Field(
        ...,
        description="multi_select | range | toggle | text"
    )

    options: Optional[List[FilterOption]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_required: bool = False


class FiltersResponse(BaseModel):
    """
    Used by: GET /categories/{id}/filters
    """
    category: CategoryResponse
    filters: List[FilterConfig] = Field(default_factory=list)