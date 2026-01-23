"""
Product API endpoints with dynamic category-based filtering
"""

import json
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import exists, func

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import (
    Product,
    Category,
    Attribute,
    AttributeValue,
    CategoryAttribute,
    ProductImage,
    AttributeDataType,
)
from src.interfaces.api.schemas.product import (
    ProductListItem,
    ProductDetail,
    ProductListResponse,
    ProductAttributeResponse,
    ProductImageResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


# ============================================================
# HELPERS
# ============================================================

def get_primary_image_url(product_id: str, db: Session) -> Optional[str]:
    """Get primary image URL for a product, with fallback to temp images."""
    image = (
        db.query(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.is_primary.is_(True),
        )
        .first()
    )
    
    # Return image URL if found, otherwise None
    if image:
        return image.image_url
    else:
        return None  # TODO: Implement fallback image logic


def apply_attribute_filters(
    query,
    filter_dict: Dict[str, Any],
    category_id: int,
    db: Session,
):
    """
    Apply dynamic attribute filters using CategoryAttribute mapping.
    Ensures:
    - Only category-allowed attributes are used
    - ENUM / NUMBER / BOOLEAN / STRING are handled correctly
    - Case-insensitive string matching
    """

    # Load allowed attributes for category
    allowed_attrs = {
        ca.attribute.name: ca.attribute
        for ca in (
            db.query(CategoryAttribute)
            .join(Attribute)
            .filter(
                CategoryAttribute.category_id == category_id,
                CategoryAttribute.is_filterable.is_(True),
            )
            .all()
        )
    }

    for attr_name, values in filter_dict.items():
        attribute = allowed_attrs.get(attr_name)

        if not attribute or values is None:
            continue

        # =======================
        # ENUM (multi-select)
        # =======================
        if attribute.data_type == AttributeDataType.ENUM:
            if not isinstance(values, list):
                raise HTTPException(
                    status_code=400,
                    detail=f"Attribute '{attr_name}' expects a list",
                )

            # ✅ FIX: Case-insensitive matching
            # Convert filter values to lowercase for comparison
            lower_values = [v.lower() for v in values]
            
            query = query.filter(
                exists().where(
                    AttributeValue.product_id == Product.product_id,
                    AttributeValue.attribute_id == attribute.attribute_id,
                    func.lower(AttributeValue.value_string).in_(lower_values),
                )
            )

        # =======================
        # NUMBER (range)
        # =======================
        elif attribute.data_type == AttributeDataType.NUMBER:
            if not isinstance(values, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"Attribute '{attr_name}' expects min/max object",
                )

            conditions = [
                AttributeValue.product_id == Product.product_id,
                AttributeValue.attribute_id == attribute.attribute_id,
            ]

            if values.get("min") is not None:
                conditions.append(AttributeValue.value_number >= values["min"])
            if values.get("max") is not None:
                conditions.append(AttributeValue.value_number <= values["max"])

            query = query.filter(exists().where(*conditions))

        # =======================
        # BOOLEAN
        # =======================
        elif attribute.data_type == AttributeDataType.BOOLEAN:
            if not isinstance(values, bool):
                raise HTTPException(
                    status_code=400,
                    detail=f"Attribute '{attr_name}' expects boolean",
                )

            query = query.filter(
                exists().where(
                    AttributeValue.product_id == Product.product_id,
                    AttributeValue.attribute_id == attribute.attribute_id,
                    AttributeValue.value_boolean == values,
                )
            )

        # =======================
        # STRING (text search)
        # =======================
        elif attribute.data_type == AttributeDataType.STRING:
            if not isinstance(values, str):
                raise HTTPException(
                    status_code=400,
                    detail=f"Attribute '{attr_name}' expects string",
                )

            query = query.filter(
                exists().where(
                    AttributeValue.product_id == Product.product_id,
                    AttributeValue.attribute_id == attribute.attribute_id,
                    AttributeValue.value_string.ilike(f"%{values}%"),
                )
            )

    return query


# ============================================================
# LIST PRODUCTS
# ============================================================

@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),

    brand: Optional[str] = None,
    stock_status: Optional[str] = None,
    category_id: Optional[int] = Query(None, description="Required for filters"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),

    filters: Optional[str] = Query(
        None,
        description='{"color":["pink"],"gsm":{"min":120,"max":180}}',
    ),

    sort_by: str = Query("product_id"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),

    db: Session = Depends(get_db),
):
    """
    List products with static and dynamic filtering.
    
    Example filters param:
    {
        "color": ["Peach", "Pink"],
        "gender": ["Girls"],
        "gsm": {"min": 100, "max": 200},
        "skin_friendly": true
    }
    """
    
    # ✅ ADD: Debug logging
    # print(f"[PRODUCTS] Received filters: {filters}")
    # print(f"[PRODUCTS] Category ID: {category_id}")
    
    if filters and not category_id:
        raise HTTPException(
            status_code=400,
            detail="category_id is required when using dynamic filters",
        )

    query = db.query(Product)

    # =======================
    # STATIC FILTERS
    # =======================
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))

    if stock_status:
        query = query.filter(Product.stock_status == stock_status)

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # =======================
    # DYNAMIC FILTERS
    # =======================
    if filters:
        try:
            filter_dict = json.loads(filters)
            # print(f"[PRODUCTS] Parsed filter_dict: {filter_dict}")  # ✅ Debug
        except Exception as e:
            print(f"[PRODUCTS] JSON parse error: {e}")  # ✅ Debug
            raise HTTPException(status_code=400, detail="Invalid filters JSON")

        query = apply_attribute_filters(
            query=query,
            filter_dict=filter_dict,
            category_id=category_id,
            db=db,
        )

    # Prevent duplicates from EXISTS joins
    query = query.distinct(Product.product_id)

    # =======================
    # SORTING
    # =======================
    sort_col = {
        "price": Product.price,
        "title": Product.title,
    }.get(sort_by, Product.product_id)

    query = query.order_by(
        sort_col.desc() if sort_order == "desc" else sort_col.asc()
    )

    # =======================
    # PAGINATION
    # =======================
    total = query.count()
    
    print(f"[PRODUCTS] Total results after filtering: {total}")  # ✅ Debug

    products = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        ProductListItem(
            product_id=p.product_id,
            title=p.title,
            brand=p.brand,
            product_type=p.product_type,
            price=p.price,
            mrp=p.mrp,
            discount_percent=p.discount_percent,
            currency=p.currency,
            stock_status=p.stock_status,
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
                    title=product.title,
                    brand=product.brand,
                    product_type=product.product_type,
                    price=product.price,
                    mrp=product.mrp,
                    discount_percent=product.discount_percent,
                    currency=product.currency,
                    stock_status=product.stock_status,
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

    attribute_values = (
        db.query(AttributeValue)
        .join(Attribute)
        .filter(AttributeValue.product_id == product_id)
        .all()
    )

    attributes = []
    for av in attribute_values:
        if av.value_string is not None:
            val = av.value_string
        elif av.value_number is not None:
            val = str(av.value_number)
        else:
            val = str(av.value_boolean)

        attributes.append(
            ProductAttributeResponse(
                attribute_id=av.attribute.attribute_id,
                attribute_name=av.attribute.name,
                attribute_type=av.attribute.data_type.value,
                value=val,
            )
        )

    images = (
        db.query(ProductImage)
        .filter(ProductImage.product_id == product_id)
        .order_by(ProductImage.is_primary.desc(), ProductImage.display_order)
        .all()
    )
    
    # ⚠️ TEMPORARY: Use fallback images if DB is empty
    if not images:
        # Fallback images temporarily disabled - need to implement fallback logic
        images = []

    return ProductDetail(
        product_id=product.product_id,
        title=product.title,
        brand=product.brand,
        product_type=product.product_type,
        price=product.price,
        mrp=product.mrp,
        discount_percent=product.discount_percent,
        currency=product.currency,
        stock_status=product.stock_status,
        primary_image=get_primary_image_url(product_id, db),
        category=product.category,
        attributes=attributes,
        images=images,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )