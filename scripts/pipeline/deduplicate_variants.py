#!/usr/bin/env python3
"""
Dynamic Product Deduplication (Config-Aware)

This script reads normalization_config.json to determine which fields exist,
making it resilient to config changes.

Usage:
    python deduplicate_variants_dynamic.py <input_csv> <output_csv> [config_json]

Example:
    python deduplicate_variants_dynamic.py data/normalized_output.csv data/products.csv normalization_config.json
"""

import sys
import json
import pandas as pd
from pathlib import Path


def load_config(config_path):
    """Load normalization config to determine available fields"""
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Extract field names from output_schema
    field_names = [field['name'] for field in config['output_schema']]
    return field_names


def parse_sku(sku):
    """
    Parse SKU into base and size components by splitting at FIRST separator.
    Matches the logic from the original deduplicate_variants.py script.
    
    Examples:
        '25774103-08' → ('25774103', '08')
        '10111004-M-L' → ('10111004', 'M-L')
        '10111004-S-M' → ('10111004', 'S-M')
        '10202501-m_l' → ('10202501', 'm_l')
        'ABC123' → ('ABC123', None)
    """
    if pd.isna(sku) or not sku:
        return None, None
    
    sku_str = str(sku).strip()
    
    # Find the first separator (dash or underscore)
    dash_pos = sku_str.find('-')
    underscore_pos = sku_str.find('_')
    
    # Get the position of the first separator
    if dash_pos == -1 and underscore_pos == -1:
        # No separator found, entire SKU is the base
        return sku_str, None
    elif dash_pos == -1:
        separator_pos = underscore_pos
    elif underscore_pos == -1:
        separator_pos = dash_pos
    else:
        separator_pos = min(dash_pos, underscore_pos)
    
    # Split at the separator
    base_sku = sku_str[:separator_pos]
    size = sku_str[separator_pos + 1:]  # Everything after separator
    
    # Clean up empty sizes
    if not size or size in ['-', '_']:
        return base_sku, None
    
    return base_sku, size


def create_products_table(df, available_fields):
    """
    Create aggregated products table by grouping variants
    
    Args:
        df: Input DataFrame with normalized product data
        available_fields: List of field names from config
    
    Returns:
        DataFrame with Unique products
    """
    
    # Parse SKUs
    df['sku_base'], df['sku_size'] = zip(*df['sku'].apply(parse_sku))
    
    # Group by SKU base
    grouped = df.groupby('sku_base', dropna=False)
    
    products = []
    
    # Define core fields that should always exist
    core_fields = ['product_id', 'sku', 'title', 'price', 'stock_status']
    
    # Define fields that should be aggregated (if they exist)
    aggregate_fields = ['brand', 'product_type', 'gender', 'age_group', 'occasion']
    
    # Define fields that should use master value (if they exist)
    master_fields = ['description', 'url_key', 'categories', 'created_at', 'updated_at']
    
    for sku_base, group in grouped:
        if pd.isna(sku_base):
            continue
        
        # Select master variant (most complete data)
        group = group.copy()
        group['completeness_score'] = group.notna().sum(axis=1)
        master = group.sort_values(
            by=['completeness_score', 'price', 'sku'],
            ascending=[False, True, True]
        ).iloc[0]
        
        # Helper function to safely get field value
        def safe_get(row, field_name, default=None):
            """Safely get field value if it exists"""
            if field_name in available_fields and field_name in row.index:
                val = row[field_name]
                return val if pd.notna(val) else default
            return default
        
        # Helper function to aggregate multi-value fields
        def aggregate_field(field_name):
            """Get unique non-null values as comma-separated string"""
            if field_name not in available_fields or field_name not in group.columns:
                return None
            
            unique_vals = group[field_name].dropna().unique()
            if len(unique_vals) == 0:
                return None
            elif len(unique_vals) == 1:
                return str(unique_vals[0])
            else:
                return ','.join(sorted(str(v) for v in unique_vals))
        
        # Extract available sizes from SKU suffixes
        available_sizes = sorted([
            size for size in group['sku_size'].dropna().unique() 
            if size
        ])
        available_sizes_str = ','.join(str(s) for s in available_sizes) if available_sizes else None
        
        # Aggregate prices
        unique_prices = sorted(group['price'].dropna().unique())
        if len(unique_prices) == 0:
            prices_str = None
        elif len(unique_prices) == 1:
            prices_str = str(unique_prices[0])
        else:
            prices_str = ','.join(str(p) for p in unique_prices)
        
        # Aggregate product IDs
        product_ids_list = sorted(group['product_id'].dropna().unique())
        product_ids_str = ','.join(str(pid) for pid in product_ids_list) if product_ids_list else None
        
        # Build product record with EXACT column order to match old format
        # Order: sku, title, description, brand, product_type, gender, age_group, occasion,
        #        url_key, categories, created_at, updated_at, variant_count, product_ids,
        #        size, color, price, stock_status
        product = {
            'sku': sku_base,
            'title': safe_get(master, 'title'),
            'description': safe_get(master, 'description'),
            'brand': aggregate_field('brand') if 'brand' in available_fields else None,
            'product_type': aggregate_field('product_type') if 'product_type' in available_fields else None,
            'gender': aggregate_field('gender') if 'gender' in available_fields else None,
            'age_group': aggregate_field('age_group') if 'age_group' in available_fields else None,
            'occasion': aggregate_field('occasion') if 'occasion' in available_fields else None,
            'url_key': safe_get(master, 'url_key'),
            'categories': safe_get(master, 'categories'),
            'created_at': safe_get(master, 'created_at'),
            'updated_at': safe_get(master, 'updated_at'),
            'variant_count': len(group),
            'product_ids': product_ids_str,
            'size': available_sizes_str if 'size' in available_fields else None,
            'color': aggregate_field('color') if 'color' in available_fields else None,
            'price': prices_str,
            'stock_status': aggregate_field('stock_status'),
        }
        
        products.append(product)
    
    products_df = pd.DataFrame(products)
    
    print(f"Created {len(products_df):,} unique products")
    
    # Analysis
    avg_variants = df.shape[0] / len(products_df) if len(products_df) > 0 else 0
    
    
    # Check for products with multiple prices
    multi_price = products_df['price'].str.contains(',', na=False).sum()
    
    # Check for products with multiple stock statuses
    multi_status = products_df['stock_status'].str.contains(',', na=False).sum()
    
    # Check for products with multiple brands
    if 'brand' in products_df.columns:
        multi_brand = products_df['brand'].str.contains(',', na=False).sum()
        
    
    return products_df


def print_analysis(df, products_df):
    """Print analysis"""
    print("UNIQUE PRODUCTS ANALYSIS (SKU-Based)")
    
    print("\n📊 Input:")
    print(f"  Total rows:                  {len(df):,}")
    print(f"  Unique SKUs:                 {df['sku'].nunique():,}")
    print(f"  Unique SKU bases:            {df['sku_base'].nunique():,}")
    
    print("\n📦 Products Output:")
    print(f"  Unique products:             {len(products_df):,}")
    avg_variants = len(df) / len(products_df) if len(products_df) > 0 else 0
    print(f"  Avg variants/product:     {avg_variants:8.1f}")
    

def main():
    if len(sys.argv) < 3:
        print("Usage: python deduplicate_variants_dynamic.py <input_csv> <output_csv> [config_json]")
        print("\nExample:")
        print("  python deduplicate_variants_dynamic.py data/normalized_output.csv data/products.csv normalization_config.json")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    config_json = sys.argv[3] if len(sys.argv) > 3 else 'normalization_config.json'
    
    # Load config to get available fields
    available_fields = load_config(config_json)
    
    # Read input CSV
    print(f"\n📥 Reading input CSV: {input_csv}")
    try:
        df = pd.read_csv(input_csv, low_memory=False)
        print(f"✓ Loaded {len(df):,} rows with {len(df.columns)} columns")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)
    
    # Create products table
    products_df = create_products_table(df, available_fields)
    
    # Print analysis
    print_analysis(df, products_df)
    
    # Write output
    print(f"\n📤 Writing output file...")
    print("-" * 80)
    try:
        products_df.to_csv(output_csv, index=False)
        print(f"✓ Products saved to: {output_csv}")
        print(f"  Rows: {len(products_df):,}")
        print(f"  Columns: {len(products_df.columns)}")
    except Exception as e:
        print(f"❌ Error writing CSV: {e}")
        sys.exit(1)
    

if __name__ == '__main__':
    main()
