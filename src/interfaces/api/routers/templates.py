"""
Template router for serving HTML pages.
Provides Jinja2 templating support for FastAPI.
"""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Get the project root directory (assuming this file is in src/interfaces/api/routers/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

router = APIRouter(tags=["templates"])


def url_for_static(path: str) -> str:
    """Generate URL for static files."""
    return f"/static/{path}"


def url_for(route_name: str, **kwargs) -> str:
    """Generate URL for routes (FastAPI-compatible)."""
    routes = {
        "read_root": "/",
        "product_detail": "/product/{product_id}",
    }
    
    route_path = routes.get(route_name, "/")
    
    # Replace path parameters
    if kwargs:
        for key, value in kwargs.items():
            route_path = route_path.replace(f"{{{key}}}", str(value))
    
    return route_path


# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Add helper functions to template globals
templates.env.globals["url_for"] = url_for
templates.env.globals["url_for_static"] = url_for_static


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main products listing page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: str):
    """Serve the product detail page."""
    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "product_id": product_id,
        },
    )
