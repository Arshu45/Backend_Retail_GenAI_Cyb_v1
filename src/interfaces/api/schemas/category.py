"""Category schemas."""

from typing import Optional
from pydantic import BaseModel


class CategoryResponse(BaseModel):
    """Category response schema."""
    id: int
    name: str
    parent_id: Optional[int] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True
