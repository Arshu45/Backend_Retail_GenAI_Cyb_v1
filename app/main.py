"""
FastAPI application entrypoint.
Thin layer that wires up routers and middleware.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config.settings import settings
from src.config.logger import setup_logging, get_logger
from src.interfaces.api.middleware import setup_middleware
from src.interfaces.api.dependencies import init_services
from src.interfaces.api.routers import health, search, products, categories, filters, sessions, templates

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Initializing services...")
    try:
        init_services()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        raise
    
    yield
    
    logger.info("Shutting down services...")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    description="Dynamic product search with category-based filters",
    version=settings.api_version,
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Mount static files
PROJECT_ROOT = Path(__file__).parent.parent
static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register routers
# Template routes (must come before API routes to avoid conflicts)
app.include_router(templates.router)
# API routes
app.include_router(health.router)
app.include_router(search.router)
app.include_router(products.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(filters.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")

logger.info("Application startup complete")