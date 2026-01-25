"""
FastAPI application entrypoint.
Thin layer that wires up routers and middleware.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from src.config.settings import settings
from src.config.logging_config import setup_logging, get_logger
from src.interfaces.api.middleware import setup_middleware
from src.interfaces.api.dependencies import init_services
from src.interfaces.api.routers import health, search, products, categories, filters, sessions
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

# Static & templates
# Since main.py is in the 'app' subfolder, we go one level up to the root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app.mount(
   "/static",
   StaticFiles(directory=os.path.join(BASE_DIR, "static")),
   name="static",
)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.globals["url_for_static"] = lambda p: f"/static/{p}"

# ============================================================
# Frontend pages
# ============================================================
@app.get("/")
async def read_root(request: Request):
   return templates.TemplateResponse(
       "index.html",
       {"request": request},
   )

@app.get("/product/{product_id}")
async def read_product_page(request: Request, product_id: str):
   return templates.TemplateResponse(
       "product.html",
       {"request": request, "product_id": product_id},
   )


# Setup middleware
setup_middleware(app)
# Register routers
app.include_router(health.router)
app.include_router(search.router)
app.include_router(products.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(filters.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
logger.info("Application startup complete")