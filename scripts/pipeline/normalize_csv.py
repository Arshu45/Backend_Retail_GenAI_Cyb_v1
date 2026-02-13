#!/usr/bin/env python3
"""
CSV Normalization Script for Ecommerce Product Data (Config-Driven)
Converts messy vendor CSVs into a standardized format using JSON configuration.

Usage:
    python normalize_csv.py input.csv output.csv [config.json]
"""

import sys
import re
import json
import pandas as pd
import numpy as np
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

class HTMLStripper(HTMLParser):
    """Simple HTML tag stripper"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_data(self):
        return ''.join(self.text)


def strip_html(text):
    """Remove HTML tags from text"""
    if pd.isna(text) or text == '':
        return None
    
    try:
        stripper = HTMLStripper()
        stripper.feed(str(text))
        cleaned = stripper.get_data()
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else None
    except Exception:
        # Fallback: simple regex if parser fails
        cleaned = re.sub(r'<[^>]+>', '', str(text))
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else None


def safe_float(value):
    """Safely convert value to float, return None if not possible"""
    if pd.isna(value) or value == '':
        return None
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """Safely convert value to int, return None if not possible"""
    if pd.isna(value) or value == '':
        return None
    
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_date(value, date_formats=None):
    """Parse date to ISO format, return None if not possible"""
    if pd.isna(value) or value == '':
        return None
    
    if date_formats is None:
        date_formats = ['%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']
    
    try:
        # Try specified formats
        for fmt in date_formats:
            try:
                dt = datetime.strptime(str(value), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Fallback: pandas date parser
        dt = pd.to_datetime(value, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%Y-%m-%d')
        
        return None
    except Exception:
        return None


def clean_text(text):
    """Clean and normalize text fields"""
    if pd.isna(text) or text == '':
        return None
    
    text = str(text).strip()
    if text == '':
        return None
    
    return text


def get_first_non_empty(*values):
    """Return first non-empty value from arguments"""
    for val in values:
        cleaned = clean_text(val)
        if cleaned is not None:
            return cleaned
    return None


def normalize_status(status, value_mapping=None):
    """Normalize status field using value mapping"""
    # Keep empty values as-is (don't modify the data)
    if pd.isna(status) or status == '':
        return None
    
    status_lower = str(status).lower().strip()
    
    if value_mapping:
        return value_mapping.get(status_lower, value_mapping.get('default', status_lower))
    
    # Default mapping - only normalize known values
    if status_lower in ('enabled', 'active', '1', 'true', 'in stock', 'available'):
        return 'in_stock'
    elif status_lower in ('disabled', 'inactive', '0', 'false', 'out of stock', 'unavailable'):
        return 'out_of_stock'
    else:
        # Keep original value if not recognized
        return status_lower


def calculate_discount(price, sale_price):
    """Calculate discount value from price and sale_price"""
    if price is None or sale_price is None:
        return None
    
    try:
        discount = float(price) - float(sale_price)
        return round(discount, 2) if discount > 0 else None
    except (ValueError, TypeError):
        return None


# ============================================================================
# CONFIG-DRIVEN NORMALIZATION
# ============================================================================

def get_column_safe(df, *possible_names):
    """Get first existing column from list of possible names (case-insensitive)"""
    col_map = {col.lower(): col for col in df.columns}
    
    for name in possible_names:
        if name.lower() in col_map:
            return df[col_map[name.lower()]]
    
    return pd.Series([None] * len(df))


def apply_transform(series, transform_name, config):
    """Apply transformation to a pandas Series based on config"""
    
    if transform_name == 'clean_text':
        return series.apply(clean_text)
    
    elif transform_name == 'strip_html':
        return series.apply(strip_html)
    
    elif transform_name == 'safe_float':
        return series.apply(safe_float)
    
    elif transform_name == 'safe_int':
        return series.apply(safe_int)
    
    elif transform_name == 'safe_date':
        date_formats = config.get('transformations', {}).get('safe_date', {}).get('date_formats')
        return series.apply(lambda x: safe_date(x, date_formats))
    
    elif transform_name == 'lowercase':
        return series.apply(lambda x: str(x).lower().strip() if pd.notna(x) and x != '' else None)
    
    elif transform_name == 'normalize_status':
        value_mapping = config.get('transformations', {}).get('normalize_status', {}).get('value_mapping')
        return series.apply(lambda x: normalize_status(x, value_mapping))
    
    else:
        # Default: return as-is
        return series


def normalize_dataframe_from_config(df, config):
    """
    Normalize dataframe using JSON configuration
    
    Args:
        df: Input pandas DataFrame
        config: Loaded JSON configuration dict
    
    Returns:
        Normalized pandas DataFrame
    """
    
    normalized = pd.DataFrame()
    schema = config['output_schema']
    
    # Track which input columns have been mapped
    mapped_input_cols = set()
    
    # Process each field in the schema
    for field in schema:
        field_name = field['name']
        aliases = field['aliases']
        transform = field.get('transform', 'clean_text')
        
        # Track aliases that exist in input
        for alias in aliases:
            col_map = {col.lower(): col for col in df.columns}
            if alias.lower() in col_map:
                mapped_input_cols.add(col_map[alias.lower()])
        
        # Handle derived fields
        if field.get('derived'):
            if field_name == 'sale_price':
                # Special handling for sale_price
                price_col = get_column_safe(df, 'price', 'selling_price', 'regular_price').apply(safe_float)
                price_status = get_column_safe(df, 'item_price_status', 'price_status').apply(
                    lambda x: str(x).lower().strip() if pd.notna(x) else ''
                )
                normalized[field_name] = price_col.where(price_status == 'markdown', None)
            
            elif field_name == 'discount_value':
                # Calculate discount
                if 'price' in normalized.columns and 'sale_price' in normalized.columns:
                    normalized[field_name] = normalized.apply(
                        lambda row: calculate_discount(row['price'], row['sale_price']),
                        axis=1
                    )
                else:
                    normalized[field_name] = None
            
            elif field_name == 'stock_status':
                # Normalize status
                status_col = get_column_safe(df, *aliases)
                normalized[field_name] = apply_transform(status_col, transform, config)
            
            else:
                normalized[field_name] = None
        
        # Handle color merge (special case)
        elif field_name == 'color' and field.get('merge_strategy') == 'first_non_empty':
            base_colour = get_column_safe(df, 'base_colour')
            fashion_colour = get_column_safe(df, 'fashion_colour')
            color = get_column_safe(df, 'color', 'colour')
            
            # Track these columns as mapped
            for col_name in ['base_colour', 'fashion_colour', 'color', 'colour']:
                col_map = {col.lower(): col for col in df.columns}
                if col_name.lower() in col_map:
                    mapped_input_cols.add(col_map[col_name.lower()])
            
            normalized[field_name] = pd.Series([
                get_first_non_empty(bc, fc, c)
                for bc, fc, c in zip(base_colour, fashion_colour, color)
            ]).apply(lambda x: x.lower() if isinstance(x, str) else None)
        
        # Standard field mapping
        else:
            source_col = get_column_safe(df, *aliases)
            normalized[field_name] = apply_transform(source_col, transform, config)
    
    # PASS-THROUGH: Add unmapped columns from input as-is
    for col in df.columns:
        if col not in mapped_input_cols and col not in normalized.columns:
            normalized[col] = df[col]
    
    return normalized


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def load_config(config_path):
    """Load JSON configuration file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)


def main(input_csv, output_csv, config_path=None):
    """
    Main processing function
    
    Args:
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        config_path: Path to JSON config file (optional)
    """
    
    # Load configuration
    if config_path is None:
        # Default config path
        script_dir = Path(__file__).parent
        config_path = script_dir / 'normalization_config.json'
    
    print(f"Loading configuration from: {config_path}")
    config = load_config(config_path)
    print(f"✓ Loaded schema with {len(config['output_schema'])} fields")
    
    print(f"\nReading input CSV: {input_csv}")
    
    try:
        # Read CSV with flexible encoding
        encodings = config.get('encoding', {}).get('input', ['utf-8', 'latin-1'])
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(input_csv, encoding=encoding)
                print(f"✓ Successfully read with {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception("Could not read CSV with any supported encoding")
        
        print(f"✓ Loaded {len(df)} rows with {len(df.columns)} columns")
        
    except Exception as e:
        print(f"Error reading input CSV: {e}")
        return 1
    
    print("\nNormalizing data...")
    
    try:
        # Normalize using config
        normalized_df = normalize_dataframe_from_config(df, config)
        
        print(f"✓ Normalized to {len(normalized_df)} rows with {len(normalized_df.columns)} columns")
        
        # Show summary statistics
        print("\n--- Summary Statistics ---")
        for field in config['output_schema']:
            field_name = field['name']
            if field_name in normalized_df.columns:
                count = normalized_df[field_name].notna().sum()
                print(f"{field_name:20} {count:>10,} ({count/len(normalized_df)*100:.1f}%)")
        
    except Exception as e:
        print(f"Error during normalization: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\nWriting output CSV: {output_csv}")
    
    try:
        output_encoding = config.get('encoding', {}).get('output', 'utf-8')
        normalized_df.to_csv(output_csv, index=False, encoding=output_encoding)
        print(f"Successfully wrote {len(normalized_df)} rows to {output_csv}")
        
    except Exception as e:
        print(f"Error writing output CSV: {e}")
        return 1
    
    print("\n✅ Normalization complete!")
    return 0


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python normalize_csv.py <input.csv> <output.csv> [config.json]")
        print("\nExample:")
        print("  python normalize_csv.py data/input.csv data/output.csv")
        print("  python normalize_csv.py data/input.csv data/output.csv custom_config.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    config_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    exit_code = main(input_file, output_file, config_file)
    sys.exit(exit_code)
