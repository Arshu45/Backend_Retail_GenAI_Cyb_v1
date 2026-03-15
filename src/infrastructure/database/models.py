"""
SQLAlchemy database models
Migrated to flat schema (2026-02-13)
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.database.connection import Base


# =========================
# CATEGORIES
# =========================

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    parent_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    product_categories = relationship(
        "ProductCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )


# =========================
# PRODUCTS (Flat Schema)
# =========================

class Product(Base):
    __tablename__ = "products"

    # Primary identifiers
    product_id = Column(String(50), primary_key=True, index=True)
    sku = Column(String(255), index=True)
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Categories stored as comma-separated string (legacy field)
    categories = Column(String(500), nullable=True)
    
    # Pricing
    price = Column(String(50), nullable=True)
    
    # Status and timestamps
    stock_status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Product attributes (all VARCHAR)
    color = Column(String(255), nullable=True)
    size = Column(String(255), nullable=True)
    care_instruction = Column(Text, nullable=True)
    product_type = Column(String(255), nullable=True, index=True)
    attribute_set_id = Column(String(50), nullable=True)
    barcode = Column(String(255), nullable=True)
    released_date = Column(String(255), nullable=True)
    item_price_status = Column(String(255), nullable=True)
    country_of_manufacture = Column(String(255), nullable=True)
    dinkus = Column(String(255), nullable=True)
    dinkus_hex_colour = Column(String(255), nullable=True)
    style_code = Column(String(255), nullable=True)
    swatch_hex_colour = Column(String(255), nullable=True)
    url_key = Column(String(500), nullable=True)
    url_path = Column(String(500), nullable=True)

    # Relationships
    product_categories = relationship(
        "ProductCategory",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    images = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
    )


# =========================
# PRODUCT-CATEGORY JUNCTION
# =========================

class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        String(50),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("product_id", "category_id", name="uq_product_category"),
    )

    # Relationships
    product = relationship("Product", back_populates="product_categories")
    category = relationship("Category", back_populates="product_categories")


# =========================
# PRODUCT IMAGES
# =========================

class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        String(50),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url = Column(String(1000), nullable=False)
    is_primary = Column(Integer, default=0)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="images")
