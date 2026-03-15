from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, Float

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import Category, Product, ProductCategory
from src.interfaces.api.schemas.category import CategoryResponse
from src.interfaces.api.schemas.filter import FilterConfig, FilterOption, FiltersResponse

router = APIRouter(prefix="/filters", tags=["filters"])


# ============================================================
# DYNAMIC FILTER ENDPOINT
# ============================================================

@router.get("", response_model=FiltersResponse)
async def get_filters(
    category_id: int = Query(..., description="Category ID is required"),
    db: Session = Depends(get_db),
):
    """
    Returns available filters for a category dynamically based on product data.
    """
    
    # Verify category exists
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Base query for products in this category
    product_query = (
        db.query(Product)
        .join(ProductCategory)
        .filter(ProductCategory.category_id == category_id)
    )

    # 1. Get unique Colors
    colors = (
        product_query.with_entities(Product.color)
        .filter(Product.color.isnot(None), Product.color != "NaN")
        .distinct()
        .all()
    )
    color_options = [
        FilterOption(value=c[0], label=c[0]) for c in colors if c[0]
    ]

    # 2. Get unique Sizes
    sizes = (
        product_query.with_entities(Product.size)
        .filter(Product.size.isnot(None), Product.size != "NaN")
        .distinct()
        .all()
    )
    size_options = [
        FilterOption(value=s[0], label=s[0]) for s in sizes if s[0]
    ]

    # 3. Get unique Product Types
    types = (
        product_query.with_entities(Product.product_type)
        .filter(Product.product_type.isnot(None), Product.product_type != "NaN")
        .distinct()
        .all()
    )
    type_options = [
        FilterOption(value=t[0], label=t[0]) for t in types if t[0]
    ]

    # 4. Get Price Range
    price_stats = (
        product_query.with_entities(
            func.min(func.cast(Product.price, Float)).label("min_p"),
            func.max(func.cast(Product.price, Float)).label("max_p")
        ).first()
    )

    # Construct Filter Configs
    filters = []

    if color_options:
        filters.append(FilterConfig(
            attribute_name="color",
            display_name="Color",
            filter_type="multi_select",
            data_type="string",
            options=color_options
        ))

    if size_options:
        filters.append(FilterConfig(
            attribute_name="size",
            display_name="Size",
            filter_type="multi_select",
            data_type="string",
            options=size_options
        ))

    if type_options:
        filters.append(FilterConfig(
            attribute_name="product_type",
            display_name="Product Type",
            filter_type="multi_select",
            data_type="string",
            options=type_options
        ))

    if price_stats and price_stats.min_p is not None:
        filters.append(FilterConfig(
            attribute_name="price",
            display_name="Price",
            filter_type="range",
            data_type="number",
            min_value=float(price_stats.min_p),
            max_value=float(price_stats.max_p)
        ))

    # Always include Stock Status as a standard filter
    filters.append(FilterConfig(
        attribute_name="stock_status",
        display_name="Stock Status",
        filter_type="multi_select",
        data_type="string",
        options=[
            FilterOption(value="in_stock", label="In Stock"),
            FilterOption(value="out_of_stock", label="Out of Stock")
        ]
    ))

    return FiltersResponse(
        category=CategoryResponse.from_orm(category),
        filters=filters
    )