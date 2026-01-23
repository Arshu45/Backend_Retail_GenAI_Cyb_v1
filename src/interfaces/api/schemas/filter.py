"""Filter schemas."""

from typing import Optional, List
from pydantic import BaseModel, Field

from src.interfaces.api.schemas.category import CategoryResponse


class FilterOption(BaseModel):
    """Filter option schema."""
    value: str
    label: str
    count: int = 0


class AttributeMasterResponse(BaseModel):
    """Attribute master response schema."""
    attribute_id: int
    name: str
    data_type: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CategoryAttributeResponse(BaseModel):
    """Category attribute response schema."""
    attribute: AttributeMasterResponse
    is_required: bool
    is_filterable: bool
    display_order: int

    class Config:
        from_attributes = True


class FilterConfig(BaseModel):
    """Filter configuration schema."""
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
    """Filters response schema."""
    category: CategoryResponse
    filters: List[FilterConfig] = Field(default_factory=list)
