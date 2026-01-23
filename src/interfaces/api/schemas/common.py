"""Common schemas used across the API."""

from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    agent_service: bool
    product_service: bool
    message: Optional[str] = None
