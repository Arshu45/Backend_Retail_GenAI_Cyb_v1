"""
Product API endpoints with simplified flat schema filtering
Migrated from EAV to direct column queries (2026-02-13)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, Float

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import (
    Product,
    Category,
    ProductCategory,
    ProductImage,
)
from src.interfaces.api.schemas.product import (
    ProductListItem,
    ProductDetail,
    ProductListResponse,
    ProductImageResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


# ============================================================
# HELPERS
# ============================================================

def get_primary_image_url(product_id: str, db: Session) -> Optional[str]:
    """Get primary image URL for a product, with fallback to temp images."""
    try:
        image = (
            db.query(ProductImage)
            .filter(
                ProductImage.product_id == product_id,
                ProductImage.is_primary == 1,  # Changed from Boolean to Integer
            )
            .first()
        )
        
        # Return image URL if found, otherwise use fallback
        if image:
            return image.image_url
        else:
            return None  #TODO : Add fallback image
    except Exception:
        # Table doesn't exist yet or other DB error - use fallback
        return None  #TODO : Add fallback image


# ============================================================
# LIST PRODUCTS
# ============================================================

@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),

    # Static filters (direct columns)
    stock_status: Optional[str] = None,
    category_id: Optional[int] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    
    # Direct attribute filters
    color: Optional[str] = Query(None, description="Filter by color"),
    size: Optional[str] = Query(None, description="Filter by size"),
    product_type: Optional[str] = Query(None, description="Filter by product type"),

    sort_by: str = Query("product_id"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),

    db: Session = Depends(get_db),
):
    """
    List products with direct column filtering.
    
    Example:
    /products?category_id=123&color=Red&min_price=100&max_price=500
    """
    
    query = db.query(Product)

    # =======================
    # STATIC FILTERS
    # =======================
    if stock_status:
        query = query.filter(Product.stock_status == stock_status)

    if category_id:
        # Join with product_categories junction table
        query = query.join(ProductCategory).filter(
            ProductCategory.category_id == category_id
        )

    if min_price is not None:
        # Price is stored as VARCHAR, so we need to cast it
        query = query.filter(func.cast(Product.price, Float) >= min_price)

    if max_price is not None:
        query = query.filter(func.cast(Product.price, Float) <= max_price)

    # =======================
    # DIRECT ATTRIBUTE FILTERS
    # =======================
    if color:
        query = query.filter(Product.color.ilike(f"%{color}%"))
    
    if size:
        query = query.filter(Product.size.ilike(f"%{size}%"))
    
    if product_type:
        query = query.filter(Product.product_type.ilike(f"%{product_type}%"))

    # Prevent duplicates from joins
    query = query.distinct(Product.product_id)

    # =======================
    # SORTING
    # =======================
    sort_col = {
        "price": func.cast(Product.price, Float),  # Cast for numeric sorting
        "title": Product.title,
    }.get(sort_by, Product.product_id)

    query = query.order_by(
        sort_col.desc() if sort_order == "desc" else sort_col.asc()
    )

    # =======================
    # PAGINATION
    # =======================
    total = query.count()

    products = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        ProductListItem(
            product_id=p.product_id,
            sku=p.sku,
            title=p.title,
            description=p.description,
            price=p.price,
            stock_status=p.stock_status,
            color=p.color,
            size=p.size,
            product_type=p.product_type,
            primary_image=get_primary_image_url(p.product_id, db),
        )
        for p in products
    ]

    return ProductListResponse(
        products=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================
# BATCH RETRIEVAL (for agent recommendations)
# ============================================================

@router.post("/batch", response_model=list[ProductListItem])
async def get_products_by_ids(
    product_ids: list[str],
    db: Session = Depends(get_db)
):
    """
    Retrieve multiple products by their IDs.
    Used by agent to convert recommendations into full product data.
    
    Args:
        product_ids: List of product IDs to retrieve
        
    Returns:
        List of ProductListItem objects with full product data
    """
    if not product_ids:
        return []
    
    # Query products by IDs
    products = (
        db.query(Product)
        .filter(Product.product_id.in_(product_ids))
        .all()
    )
    
    # Create a mapping to preserve order and handle missing products
    product_map = {p.product_id: p for p in products}
    
    # Build response in the same order as requested IDs
    items = []
    for product_id in product_ids:
        product = product_map.get(product_id)
        if product:
            items.append(
                ProductListItem(
                    product_id=product.product_id,
                    sku=product.sku,
                    title=product.title,
                    description=product.description,
                    price=product.price,
                    stock_status=product.stock_status,
                    color=product.color,
                    size=product.size,
                    product_type=product.product_type,
                    primary_image=get_primary_image_url(product.product_id, db),
                )
            )
    
    return items


# ============================================================
# PRODUCT DETAIL
# ============================================================

@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(product_id: str, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .filter(Product.product_id == product_id)
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get categories for this product
    categories = (
        db.query(Category)
        .join(ProductCategory)
        .filter(ProductCategory.product_id == product_id)
        .all()
    )

    # Get images (if table exists)
    try:
        images = (
            db.query(ProductImage)
            .filter(ProductImage.product_id == product_id)
            .order_by(ProductImage.is_primary.desc(), ProductImage.display_order)
            .all()
        )
        # If no images found, use fallback
        if not images:
            # Fallback images will be added later
            images = []
    except Exception:
        # Table doesn't exist yet - use fallback
        images = []

    return ProductDetail(
        product_id=product.product_id,
        sku=product.sku,
        title=product.title,
        description=product.description,
        price=product.price,
        stock_status=product.stock_status,
        color=product.color,
        size=product.size,
        care_instruction=product.care_instruction,
        product_type=product.product_type,
        primary_image=get_primary_image_url(product_id, db),
        categories=categories,
        images=images,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )