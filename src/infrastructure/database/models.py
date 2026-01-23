"""
SQLAlchemy database models
Dynamic category-driven attribute system
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Boolean,
    DateTime,
    Text,
    Enum,
    Numeric,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from src.infrastructure.database.connection import Base


# =========================
# ENUMS
# =========================

class AttributeDataType(enum.Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


# =========================
# CATEGORIES (HIERARCHY)
# =========================

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),
    )

    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")
    category_attributes = relationship(
        "CategoryAttribute",
        back_populates="category",
        cascade="all, delete-orphan",
    )


# =========================  
# PRODUCTS
# =========================

class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(50), primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    brand = Column(String(255), index=True)
    product_type = Column(String(255))

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    price = Column(Float, nullable=False)
    mrp = Column(Float)
    discount_percent = Column(Float)
    currency = Column(String(10), default="INR")
    stock_status = Column(String(50), index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    category = relationship("Category", back_populates="products")
    attribute_values = relationship(
        "AttributeValue",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    images = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
    )


# =========================
# ATTRIBUTE MASTER (GLOBAL)
# =========================

class Attribute(Base):
    """
    Global attribute definition
    Example: color, size, gsm, warranty_years
    """
    __tablename__ = "attribute_master"

    attribute_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    # data_type = Column(Enum(AttributeDataType), nullable=False)
    data_type = Column(
                    Enum(
                        AttributeDataType,
                        values_callable=lambda enum_cls: [e.value for e in enum_cls],
                        native_enum=True,
                        name="attributedatatype",
                    ),
                    nullable=False,
                )

    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category_mappings = relationship(
        "CategoryAttribute",
        back_populates="attribute",
        cascade="all, delete-orphan",
    )
    attribute_values = relationship(
        "AttributeValue",
        back_populates="attribute",
        cascade="all, delete-orphan",
    )
    options = relationship(
        "AttributeOption",
        back_populates="attribute",
        cascade="all, delete-orphan",
    )


# =========================
# CATEGORY ↔ ATTRIBUTE MAP
# =========================

class CategoryAttribute(Base):
    """
    Defines which attributes apply to which category
    """
    __tablename__ = "category_attributes"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("attribute_master.attribute_id"), nullable=False)

    is_required = Column(Boolean, default=False)
    is_filterable = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("category_id", "attribute_id", name="uq_category_attribute"),
    )

    category = relationship("Category", back_populates="category_attributes")
    attribute = relationship("Attribute", back_populates="category_mappings")


# =========================
# ATTRIBUTE VALUES (EAV)
# =========================

class AttributeValue(Base):
    """
    Stores product-specific attribute values
    """
    __tablename__ = "attribute_values"

    value_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        String(50),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attribute_id = Column(
        Integer,
        ForeignKey("attribute_master.attribute_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    value_string = Column(String(255))
    value_number = Column(Numeric(10, 2))
    value_boolean = Column(Boolean)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("product_id", "attribute_id", name="uq_product_attribute"),
        CheckConstraint(
            """
            (value_string IS NOT NULL)::int +
            (value_number IS NOT NULL)::int +
            (value_boolean IS NOT NULL)::int = 1
            """,
            name="ck_single_value_only",
        ),
    )

    product = relationship("Product", back_populates="attribute_values")
    attribute = relationship("Attribute", back_populates="attribute_values")


# =========================
# ATTRIBUTE OPTIONS (ENUM)
# =========================

class AttributeOption(Base):
    """
    ENUM values for attributes
    """
    __tablename__ = "attribute_options"

    option_id = Column(Integer, primary_key=True, index=True)
    attribute_id = Column(
        Integer,
        ForeignKey("attribute_master.attribute_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_value = Column(String(100), nullable=False)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("attribute_id", "option_value", name="uq_attribute_option"),
    )

    attribute = relationship("Attribute", back_populates="options")


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
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="images")
