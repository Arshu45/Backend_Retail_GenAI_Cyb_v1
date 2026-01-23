"""
CSV → Database Seeder
Compatible with the dynamic schema (attribute_master + category_attributes).
"""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test_ecommerce_db"

CSV_PATH = r"/Users/arsh/Downloads/POC_Ecom_Agent_1/data/catalog_corrected.csv"

CATEGORY_NAME = "Kids Dresses"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_or_create_category(db):
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
    if series.dropna().isin([True, False]).all():
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if series.nunique() < 50:
        return "enum"
    return "string"


def main():
    df = pd.read_csv(CSV_PATH)
    db = SessionLocal()

    try:
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
        for _, row in df.iterrows():
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
        print("✅ CSV data ingested successfully")

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
