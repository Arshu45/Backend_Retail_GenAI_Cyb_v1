#!/usr/bin/env python3
"""
Dynamic PostgreSQL Import with Auto-Schema Generation

Reads CSV headers and auto-creates PostgreSQL schema.
All columns stored as VARCHAR for maximum flexibility.
Categories are auto-populated from the 'categories' column.

Usage:
    python import_normalized_data.py <csv_file> [db_connection_string]

Examples:
    # Using DATABASE_URL from .env
    python import_normalized_data.py data/normalized_output.csv
    
    # With explicit connection string
    python import_normalized_data.py data/normalized_output.csv "postgresql://user:pass@localhost/dbname"
"""

import sys
import os
import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def table_exists(cur, table_name):
    """Check if a table exists in the public schema"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]

def ensure_categories_tables_exist(cur, conn):
    """Create categories and product_categories tables if they don't exist"""
    
    # Create categories table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255),
            parent_id INTEGER,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # Create product_categories junction table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_categories (
            id SERIAL PRIMARY KEY,
            product_id VARCHAR(50) NOT NULL,
            category_id INTEGER NOT NULL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_product_category UNIQUE (product_id, category_id)
        )
    """)
    
    # Create index on product_categories
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_categories_product 
        ON product_categories(product_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_categories_category 
        ON product_categories(category_id)
    """)
    
    conn.commit()
    

def populate_categories(df, cur, conn):
    """Extract unique category IDs from dataframe and populate categories table"""
    
    print("POPULATING CATEGORIES TABLE")
    
    # Check if categories column exists
    if 'categories' not in df.columns:
        print("⚠️  No 'categories' column found, skipping category population")
        return
    
    # Extract all unique category IDs
    all_categories = set()
    
    for idx, row in df.iterrows():
        categories_str = row.get('categories')
        if pd.notna(categories_str) and categories_str != '':
            try:
                cat_ids = [int(cat_id.strip()) for cat_id in str(categories_str).split(',') if cat_id.strip()]
                all_categories.update(cat_ids)
            except ValueError:
                continue
    
    if not all_categories:
        print("⚠️  No valid category IDs found")
        return
    
    print(f"Found {len(all_categories):,} unique category IDs")
    
    # Upsert categories (update if exists, insert if new)
    inserted = 0
    updated = 0
    
    for cat_id in sorted(all_categories):
        try:
            cur.execute("""
                INSERT INTO categories (id, name, parent_id, description)
                VALUES (%s, %s, NULL, NULL)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name
            """, (cat_id, f"Category {cat_id}"))
            
            if cur.rowcount > 0:
                # Check if it was an insert or update
                cur.execute("SELECT xmax FROM categories WHERE id = %s", (cat_id,))
                xmax = cur.fetchone()[0]
                if xmax == 0:
                    inserted += 1
                else:
                    updated += 1
                
        except Exception as e:
            print(f"  Warning: Could not upsert category {cat_id}: {e}")
            continue
    
    conn.commit()
    print(f"✓ Inserted {inserted:,} new categories")
    print(f"✓ Updated {updated:,} existing categories")


def create_or_update_products_table(df, cur, conn):
    """Create products table or add missing columns dynamically"""
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'products'
        )
    """)
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        # Create new table with all columns as VARCHAR
        columns_sql = []
        
        for col in df.columns:
            # Use TEXT for potentially long fields, VARCHAR(500) for others
            if col in ['description', 'care_instruction', 'dinkus']:
                col_type = 'TEXT'
            else:
                col_type = 'VARCHAR(500)'
            
            columns_sql.append(f'"{col}" {col_type}')
        
        # Use product_id as primary key (no auto-increment id)
        create_sql = f"""
            CREATE TABLE products (
                {', '.join(columns_sql)},
                PRIMARY KEY (product_id)
            )
        """
        
        cur.execute(create_sql)
        conn.commit()
        
        # Create indexes on common fields
        index_fields = ['product_id', 'sku', 'brand', 'product_type']
        for field in index_fields:
            if field in df.columns:
                try:
                    cur.execute(f'CREATE INDEX idx_products_{field} ON products ("{field}")')
                except Exception as e:
                    print(f"  Warning: Could not create index on {field}: {e}")
        
        conn.commit()
        
    else:
        # Table exists - add any missing columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products'
        """)
        
        existing_cols = {row[0] for row in cur.fetchall()}
        missing_cols = set(df.columns) - existing_cols
        
        if missing_cols:
            print(f"Adding {len(missing_cols)} missing columns...")
            for col in missing_cols:
                # Use TEXT for potentially long fields, VARCHAR(500) for others
                if col in ['description', 'care_instruction', 'dinkus']:
                    col_type = 'TEXT'
                else:
                    col_type = 'VARCHAR(500)'
                
                cur.execute(f'ALTER TABLE products ADD COLUMN "{col}" {col_type}')
                print(f"  ✓ Added column: {col} ({col_type})")
            
            conn.commit()
        else:
            print("✓ All columns already exist")
    



def populate_product_categories(df, cur, conn):
    """Populate product_categories junction table"""
    
    # Check if required columns exist
    if 'product_id' not in df.columns or 'categories' not in df.columns:
        print("⚠️  Missing required columns (product_id or categories), skipping")
        return
    
    mappings = []
    
    for idx, row in df.iterrows():
        product_id = row.get('product_id')
        categories_str = row.get('categories')
        
        if pd.notna(product_id) and pd.notna(categories_str) and categories_str != '':
            try:
                cat_ids = [int(cat_id.strip()) for cat_id in str(categories_str).split(',') if cat_id.strip()]
                for cat_id in cat_ids:
                    mappings.append((str(product_id), cat_id, 0))
            except ValueError:
                continue
    
    if not mappings:
        print("⚠️  No valid product-category mappings found")
        return
    
    print(f"Found {len(mappings):,} product-category relationships")
    
    # Insert mappings
    inserted = 0
    
    for product_id, category_id, display_order in mappings:
        try:
            cur.execute("""
                INSERT INTO product_categories (product_id, category_id, display_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (product_id, category_id) DO NOTHING
            """, (product_id, category_id, display_order))
            
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            # Skip if foreign key constraint fails
            continue
    
    conn.commit()
    print(f"Inserted {inserted:,} new mappings")


def import_products(csv_file, conn_string):
    """Import products from CSV with dynamic schema generation"""
    
    print(f"\n📥 Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file, low_memory=False)
    
    # Convert all columns to string to avoid type issues
    for col in df.columns:
        df[col] = df[col].astype(str).replace('nan', None)
    
    print(f"Loaded {len(df):,} rows with {len(df.columns)} columns")
    print(f"Columns: {', '.join(df.columns[:10])}{'...' if len(df.columns) > 10 else ''}")
    
    # Connect to database
    print("Connecting to database...")
    conn = psycopg2.connect(conn_string)
    cur = conn.cursor()
    print("Successfully connected to database.")
    
    try:
        # Step 0: Ensure categories tables exist
        ensure_categories_tables_exist(cur, conn)

        # UPSERT STRATEGY: Update existing data + add new data
        # No truncation - preserves existing records
        
        # Step 1: Populate categories
        populate_categories(df, cur, conn)
        
        # Step 2: Create/update products table schema
        create_or_update_products_table(df, cur, conn)
        
        
        # Step 3: Upsert products (update existing + insert new)
        print(f"\n{'='*80}")
        print("UPSERTING PRODUCTS")
        print(f"{'='*80}")
        print(f"Processing {len(df):,} products...")
        
        # Build dynamic upsert query
        columns = list(df.columns)
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join([f'"{col}"' for col in columns])
        
        # Build UPDATE SET clause (all columns except product_id)
        update_cols = [col for col in columns if col != 'product_id']
        update_set = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in update_cols])
        
        # Add updated_at = NOW() only if it's not already in the CSV columns
        if 'updated_at' not in columns:
            update_set += ', updated_at = NOW()'
        
        upsert_sql = f"""
            INSERT INTO products ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT (product_id) DO UPDATE SET
                {update_set}
        """
        
        # Execute upsert in batches
        batch_size = 500
        inserted = 0
        updated = 0
        
        # Get existing product IDs for tracking
        print("Checking existing products...")
        cur.execute("SELECT product_id FROM products")
        existing_product_ids = {row[0] for row in cur.fetchall()}
        print(f"Found {len(existing_product_ids):,} existing products in database")
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            
            for _, row in batch.iterrows():
                product_id = row['product_id']
                values = tuple(row[col] for col in columns)
                
                # Track if this is an insert or update
                is_update = product_id in existing_product_ids
                
                cur.execute(upsert_sql, values)
                
                if is_update:
                    updated += 1
                else:
                    inserted += 1
                    existing_product_ids.add(product_id)  # Add to set for future checks
            
            conn.commit()
            
            if (i + batch_size) % 2000 == 0:
                print(f"  Processed {min(i + batch_size, len(df)):,} / {len(df):,} products...")
        
        print(f"✓ Inserted {inserted:,} new products")
        print(f"✓ Updated {updated:,} existing products")
        print(f"✓ Total processed: {len(df):,} products")
        
        # Step 4: Populate product_categories junction table
        populate_product_categories(df, cur, conn)
        
        # Summary
        print("✅ IMPORT COMPLETED SUCCESSFULLY!")
        
        # Get counts
        cur.execute("SELECT COUNT(*) FROM products")
        product_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM categories")
        category_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM product_categories")
        mapping_count = cur.fetchone()[0]
        
        print(f"\n📊 Database Summary:")
        print(f"   Products:              {product_count:,}")
        print(f"   Categories:            {category_count:,}")
        print(f"   Product-Category Maps: {mapping_count:,}")
        
        return 0
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_normalized_data.py <csv_file> [db_connection_string]")
        print("\nExamples:")
        print('  python import_normalized_data.py data/normalized_output.csv')
        print()
        print('  # With explicit connection string:')
        print('  python import_normalized_data.py data/normalized_output.csv "postgresql://user:pass@localhost/dbname"')
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Get connection string from argument or environment variable
    if len(sys.argv) >= 3:
        conn_string = sys.argv[2]
        print("Using database connection from command line argument")
    else:
        conn_string = os.getenv('DATABASE_URL')
        if not conn_string:
            print("❌ Error: DATABASE_URL not found in .env file")
            print("Please either:")
            print("  1. Add DATABASE_URL to your .env file, or")
            print("  2. Pass the connection string as a command line argument")
            sys.exit(1)
        print("Using DATABASE_URL from .env file")
    
    exit_code = import_products(csv_file, conn_string)
    sys.exit(exit_code)
