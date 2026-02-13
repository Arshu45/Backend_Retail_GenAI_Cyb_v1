"""
Database Setup & CSV Seeder
1. Creates all necessary tables with the dynamic schema
2. Seeds data from CSV file
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_DIR = os.getenv("DATA_DIR", "data/raw")  # Base directory for data files
CSV_FILENAME = os.getenv("CSV_FILENAME") 
CSV_PATH = os.path.join(DATA_DIR, CSV_FILENAME)
CATEGORY_NAME = "Kids Dresses"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def create_tables(db):
    """Create all database tables"""
    print("🔨 Creating database tables...")
    
    # Drop existing tables (optional - comment out if you want to preserve data)
    db.execute(text("""
        DROP TABLE IF EXISTS product_images CASCADE;
        DROP TABLE IF EXISTS attribute_values CASCADE;
        DROP TABLE IF EXISTS attribute_options CASCADE;
        DROP TABLE IF EXISTS category_attributes CASCADE;
        DROP TABLE IF EXISTS attribute_master CASCADE;
        DROP TABLE IF EXISTS products CASCADE;
        DROP TABLE IF EXISTS categories CASCADE;
        DROP TYPE IF EXISTS attribute_data_type CASCADE;
    """))
    
    # Create ENUM type
    db.execute(text("""
        CREATE TYPE attribute_data_type AS ENUM (
            'string',
            'number',
            'boolean',
            'enum'
        );
    """))
    
    # Create categories table
    db.execute(text("""
        CREATE TABLE categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            parent_id INTEGER NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT fk_category_parent
                FOREIGN KEY (parent_id)
                REFERENCES categories(id)
                ON DELETE SET NULL
        );
    """))
    
    db.execute(text("""
        CREATE UNIQUE INDEX uq_category_name_parent
        ON categories(name, parent_id);
    """))
    
    # Create products table
    db.execute(text("""
        CREATE TABLE products (
            product_id VARCHAR(50) PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            brand VARCHAR(255),
            product_type VARCHAR(255),
            category_id INTEGER NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            mrp DOUBLE PRECISION,
            discount_percent DOUBLE PRECISION,
            currency VARCHAR(10) DEFAULT 'INR',
            stock_status VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT fk_product_category
                FOREIGN KEY (category_id)
                REFERENCES categories(id)
                ON DELETE RESTRICT
        );
    """))
    
    db.execute(text("""
        CREATE INDEX ix_products_category_id ON products(category_id);
    """))
    
    db.execute(text("""
        CREATE INDEX ix_products_price ON products(price);
    """))
    
    # Create attribute_master table
    db.execute(text("""
        CREATE TABLE attribute_master (
            attribute_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            data_type attribute_data_type NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """))
    
    # Create category_attributes table
    db.execute(text("""
        CREATE TABLE category_attributes (
            id SERIAL PRIMARY KEY,
            category_id INTEGER NOT NULL,
            attribute_id INTEGER NOT NULL,
            is_required BOOLEAN DEFAULT FALSE,
            is_filterable BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 0,
            CONSTRAINT uq_category_attribute
                UNIQUE (category_id, attribute_id),
            CONSTRAINT fk_category_attribute_category
                FOREIGN KEY (category_id)
                REFERENCES categories(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_category_attribute_attribute
                FOREIGN KEY (attribute_id)
                REFERENCES attribute_master(attribute_id)
                ON DELETE CASCADE
        );
    """))
    
    db.execute(text("""
        CREATE INDEX ix_category_attributes_category
        ON category_attributes(category_id);
    """))
    
    # Create attribute_options table
    db.execute(text("""
        CREATE TABLE attribute_options (
            option_id SERIAL PRIMARY KEY,
            attribute_id INTEGER NOT NULL,
            option_value VARCHAR(100) NOT NULL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_attribute_option
                UNIQUE (attribute_id, option_value),
            CONSTRAINT fk_option_attribute
                FOREIGN KEY (attribute_id)
                REFERENCES attribute_master(attribute_id)
                ON DELETE CASCADE
        );
    """))
    
    db.execute(text("""
        CREATE INDEX ix_attribute_options_attribute
        ON attribute_options(attribute_id);
    """))
    
    # Create attribute_values table
    db.execute(text("""
        CREATE TABLE attribute_values (
            value_id SERIAL PRIMARY KEY,
            product_id VARCHAR(50) NOT NULL,
            attribute_id INTEGER NOT NULL,
            value_string VARCHAR(255),
            value_number NUMERIC(10,2),
            value_boolean BOOLEAN,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_product_attribute
                UNIQUE (product_id, attribute_id),
            CONSTRAINT fk_value_product
                FOREIGN KEY (product_id)
                REFERENCES products(product_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_value_attribute
                FOREIGN KEY (attribute_id)
                REFERENCES attribute_master(attribute_id)
                ON DELETE CASCADE,
            CONSTRAINT ck_single_value_only CHECK (
                (value_string IS NOT NULL)::int +
                (value_number IS NOT NULL)::int +
                (value_boolean IS NOT NULL)::int = 1
            )
        );
    """))
    
    db.execute(text("""
        CREATE INDEX ix_attr_value_string
        ON attribute_values(attribute_id, value_string);
    """))
    
    db.execute(text("""
        CREATE INDEX ix_attr_value_number
        ON attribute_values(attribute_id, value_number);
    """))
    
    db.execute(text("""
        CREATE INDEX ix_attr_value_boolean
        ON attribute_values(attribute_id, value_boolean);
    """))
    
    # Create product_images table
    db.execute(text("""
        CREATE TABLE product_images (
            id SERIAL PRIMARY KEY,
            product_id VARCHAR(50) NOT NULL,
            image_url VARCHAR(1000) NOT NULL,
            is_primary BOOLEAN DEFAULT FALSE,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT fk_product_image_product
                FOREIGN KEY (product_id)
                REFERENCES products(product_id)
                ON DELETE CASCADE
        );
    """))
    
    db.execute(text("""
        CREATE INDEX ix_product_images_product
        ON product_images(product_id);
    """))
    
    db.commit()
    print("✅ Tables created successfully")


def get_or_create_category(db):
    """Get existing category or create new one"""
    result = db.execute(
        text("SELECT id FROM categories WHERE name = :name"),
        {"name": CATEGORY_NAME},
    ).fetchone()

    if result:
        return result[0]

    category_id = db.execute(
        text("""
            INSERT INTO categories (name)
            VALUES (:name)
            RETURNING id
        """),
        {"name": CATEGORY_NAME},
    ).scalar()

    return category_id


def infer_data_type(series):
    """Infer appropriate data type for attribute"""
    if series.dropna().isin([True, False]).all():
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if series.nunique() < 50:
        return "enum"
    return "string"


def seed_data(db):
    """Seed database from CSV file"""
    print("📊 Reading CSV data...")
    df = pd.read_csv(CSV_PATH)
    
    print(f"📦 Processing {len(df)} products...")
    
    category_id = get_or_create_category(db)

    core_columns = {
        "product_id",
        "title",
        "brand",
        "product_type",
        "price",
        "mrp",
        "discount_percent",
        "currency",
        "stock_status",
    }

    attribute_columns = [c for c in df.columns if c not in core_columns]

    # ---------------------------
    # Attribute Master
    # ---------------------------
    print("🏷️  Creating attributes...")
    attribute_map = {}

    for col in attribute_columns:
        dtype = infer_data_type(df[col])

        attr_id = db.execute(
            text("""
                INSERT INTO attribute_master (name, data_type)
                VALUES (:name, :type)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING attribute_id
            """),
            {"name": col, "type": dtype},
        ).scalar()

        attribute_map[col] = (attr_id, dtype)

        db.execute(
            text("""
                INSERT INTO category_attributes (category_id, attribute_id)
                VALUES (:cid, :aid)
                ON CONFLICT DO NOTHING
            """),
            {"cid": category_id, "aid": attr_id},
        )

    # ---------------------------
    # Products
    # ---------------------------
    print("🛍️  Inserting products...")
    for idx, row in df.iterrows():
        if (idx + 1) % 100 == 0:
            print(f"   Progress: {idx + 1}/{len(df)} products")
            
        db.execute(
            text("""
                INSERT INTO products (
                    product_id, title, brand, product_type,
                    category_id, price, mrp, discount_percent,
                    currency, stock_status
                )
                VALUES (
                    :product_id, :title, :brand, :product_type,
                    :category_id, :price, :mrp, :discount,
                    :currency, :stock_status
                )
                ON CONFLICT (product_id) DO NOTHING
            """),
            {
                "product_id": row["product_id"],
                "title": row["title"],
                "brand": row["brand"],
                "product_type": row["product_type"],
                "category_id": category_id,
                "price": row["price"],
                "mrp": row["mrp"],
                "discount": row["discount_percent"],
                "currency": row["currency"],
                "stock_status": row["stock_status"],
            },
        )

        # ---------------------------
        # Attribute Values
        # ---------------------------
        for col, value in row.items():
            if col not in attribute_map or pd.isna(value):
                continue

            attr_id, dtype = attribute_map[col]

            payload = {
                "product_id": row["product_id"],
                "attribute_id": attr_id,
                "value_string": None,
                "value_number": None,
                "value_boolean": None,
            }

            if dtype in ("string", "enum"):
                payload["value_string"] = str(value)
            elif dtype == "number":
                payload["value_number"] = float(value)
            elif dtype == "boolean":
                payload["value_boolean"] = bool(value)

            db.execute(
                text("""
                    INSERT INTO attribute_values (
                        product_id, attribute_id,
                        value_string, value_number, value_boolean
                    )
                    VALUES (
                        :product_id, :attribute_id,
                        :value_string, :value_number, :value_boolean
                    )
                    ON CONFLICT (product_id, attribute_id) DO NOTHING
                """),
                payload,
            )

            if dtype == "enum":
                db.execute(
                    text("""
                        INSERT INTO attribute_options (attribute_id, option_value)
                        VALUES (:aid, :val)
                        ON CONFLICT DO NOTHING
                    """),
                    {"aid": attr_id, "val": str(value)},
                )

    db.commit()
    print("✅ CSV data seeded successfully")


def main():
    """Main execution function"""
    # Validate required environment variables
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not found in .env file")
    
    # Check if CSV file exists
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV file not found at: {CSV_PATH}")
    
    print(f"📁 Using data directory: {DATA_DIR}")
    print(f"📄 Reading CSV file: {CSV_FILENAME}")
    
    db = SessionLocal()

    try:
        print("\n" + "="*50)
        print("🚀 Starting Database Setup & Seeding")
        print("="*50 + "\n")
        
        # Step 1: Create tables
        create_tables(db)
        
        # Step 2: Seed data
        seed_data(db)
        
        print("\n" + "="*50)
        print("🎉 Database setup and seeding completed!")
        print("="*50 + "\n")

    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()