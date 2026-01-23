"""
Filter metadata API endpoints
Category-aware dynamic filter discovery
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import (
    Category,
    Attribute,
    AttributeOption,
    AttributeValue,
    CategoryAttribute,
    AttributeDataType,
)
from src.interfaces.api.schemas.filter import (
    FiltersResponse,
    FilterConfig,
    FilterOption,
)
from src.interfaces.api.schemas.category import CategoryResponse

router = APIRouter(prefix="/filters", tags=["filters"])


# ============================================================
# Helpers
# ============================================================

def format_display_name(name: str) -> str:
    return name.replace("_", " ").title()


def determine_filter_type(data_type: AttributeDataType) -> str:
    return {
        AttributeDataType.ENUM: "multi_select",
        AttributeDataType.NUMBER: "range",
        AttributeDataType.BOOLEAN: "toggle",
        AttributeDataType.STRING: "text",
    }.get(data_type, "text")


# ============================================================
# FILTER METADATA ENDPOINT
# ============================================================

@router.get("", response_model=FiltersResponse)
async def get_filters(
    category_id: int = Query(..., description="Category ID is required"),
    db: Session = Depends(get_db),
):
    """
    Returns available filters for a category.

    - Only attributes mapped via CategoryAttribute are returned
    - ENUM filters include option counts
    - NUMBER filters include min/max
    """

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category_response = CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
    )

    # Load category attributes
    category_attrs = (
        db.query(CategoryAttribute)
        .join(Attribute)
        .filter(
            CategoryAttribute.category_id == category_id,
            CategoryAttribute.is_filterable.is_(True),
        )
        .order_by(CategoryAttribute.display_order)
        .all()
    )

    filters = []

    for ca in category_attrs:
        attr = ca.attribute

        filter_config = FilterConfig(
            attribute_id=attr.attribute_id,
            attribute_name=attr.name,
            display_name=format_display_name(attr.name),
            data_type=attr.data_type.value,
            filter_type=determine_filter_type(attr.data_type),
            is_required=ca.is_required,
        )

        # =======================
        # ENUM FILTERS
        # =======================
        if attr.data_type == AttributeDataType.ENUM:
            options = (
                db.query(
                    AttributeOption.option_value,
                    func.count(AttributeValue.product_id).label("count"),
                )
                .outerjoin(
                    AttributeValue,
                    (AttributeValue.attribute_id == AttributeOption.attribute_id)
                    & (AttributeValue.value_string == AttributeOption.option_value),
                )
                .filter(AttributeOption.attribute_id == attr.attribute_id)
                .group_by(
                    AttributeOption.option_value,
                    AttributeOption.display_order,
                )
                .order_by(
                    AttributeOption.display_order,
                    AttributeOption.option_value,
                )
                .all()
            )

            filter_config.options = [
                FilterOption(
                    value=o.option_value,
                    label=o.option_value.title(),
                    count=o.count or 0,
                )
                for o in options
            ]

        # =======================
        # NUMBER FILTERS
        # =======================
        elif attr.data_type == AttributeDataType.NUMBER:
            min_max = (
                db.query(
                    func.min(AttributeValue.value_number),
                    func.max(AttributeValue.value_number),
                )
                .filter(
                    AttributeValue.attribute_id == attr.attribute_id,
                    AttributeValue.value_number.isnot(None),
                )
                .first()
            )

            if min_max and min_max[0] is not None:
                filter_config.min_value = float(min_max[0])
                filter_config.max_value = float(min_max[1])

        # BOOLEAN filters need no metadata

        filters.append(filter_config)

    return FiltersResponse(
        category=category_response,
        filters=filters,
    )
