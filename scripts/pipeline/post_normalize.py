#!/usr/bin/env python3
"""
Post-Normalization Processing Script

Runs after normalize_csv.py to:
1. Add 'sku_base' column (derived from 'sku' by stripping size/variant suffix)
2. Strip pass-through columns — only keep columns defined in normalization_config.json

This ensures the output CSV is strictly schema-compliant with no extra vendor columns.

Usage:
    python post_normalize.py <input_csv> <output_csv> <config_json>

    This script must be run via pipeline.py.
"""

import sys
import json
import pandas as pd
from pathlib import Path
from logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)


def print_usage():
    print("""
Usage: python post_normalize.py <input_csv> <output_csv> <config_json>

Arguments:
  input_csv     Path to normalized CSV (output of normalize_csv.py)
  output_csv    Path to write the post-processed CSV
  config_json   Path to normalization_config.json

This script must be run via pipeline.py.
""")


def parse_sku(sku):
    """
    Parse SKU into base and size components by splitting at FIRST separator.

    Examples:
        '25774103-08'  → ('25774103', '08')
        '10111004-M-L' → ('10111004', 'M-L')
        '10202501-m_l' → ('10202501', 'm_l')
        'ABC123'       → ('ABC123', None)
    """
    if pd.isna(sku) or not sku:
        return None, None

    sku_str = str(sku).strip()

    # Find the first separator (dash or underscore)
    dash_pos = sku_str.find('-')
    underscore_pos = sku_str.find('_')

    # Get the position of the first separator
    if dash_pos == -1 and underscore_pos == -1:
        # No separator found — entire SKU is the base
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


def get_schema_columns(config_path):
    """
    Read the config and return the ordered list of column names defined in output_schema.

    Args:
        config_path: Path to normalization_config.json

    Returns:
        List of field names in schema order
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

    schema = config.get('output_schema', [])
    return [field['name'] for field in schema]


def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print_usage()
        sys.exit(0)

    if len(sys.argv) < 4:
        print("❌ Error: Missing required arguments")
        print_usage()
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    config_json = sys.argv[3]

    # =========================================================
    # LOAD CONFIG — get allowed columns
    # =========================================================
    schema_columns = get_schema_columns(config_json)
    logger.debug(f"Schema defines {len(schema_columns)} columns: {schema_columns}")

    # sku_base will be inserted right after sku
    if 'sku' in schema_columns:
        sku_idx = schema_columns.index('sku')
        final_columns = schema_columns[:sku_idx + 1] + ['sku_base'] + schema_columns[sku_idx + 1:]
    else:
        final_columns = schema_columns + ['sku_base']

    # =========================================================
    # LOAD INPUT CSV
    # =========================================================
    logger.debug(f"Reading input CSV: {input_csv}")
    try:
        df = pd.read_csv(input_csv, low_memory=False)
        logger.debug(f"Loaded {len(df):,} rows with {len(df.columns)} columns")
    except Exception as e:
        print(f"❌ Error reading input CSV: {e}")
        sys.exit(1)

    # =========================================================
    # STEP 1: ADD sku_base COLUMN
    # =========================================================
    if 'sku' in df.columns:
        df['sku_base'], _ = zip(*df['sku'].apply(parse_sku))
        logger.debug("Derived sku_base column from sku")
    else:
        print("⚠️  Warning: 'sku' column not found — sku_base will be empty")
        df['sku_base'] = None

    # =========================================================
    # STEP 2: STRIP PASS-THROUGH COLUMNS
    # Keep only columns defined in config schema (+ sku_base)
    # =========================================================
    available = [col for col in final_columns if col in df.columns]
    missing = [col for col in final_columns if col not in df.columns]

    if missing:
        logger.debug(f"Columns in schema but not in CSV (will be skipped): {missing}")

    dropped = [col for col in df.columns if col not in final_columns]
    if dropped:
        logger.debug(f"Dropping {len(dropped)} pass-through columns: {dropped}")

    df = df[available]
    logger.debug(f"Output: {len(df):,} rows × {len(df.columns)} columns")

    # =========================================================
    # WRITE OUTPUT CSV
    # =========================================================
    try:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False, encoding='utf-8')
        logger.debug(f"Written to: {output_csv}")
    except Exception as e:
        print(f"❌ Error writing output CSV: {e}")
        sys.exit(1)

    logger.debug("✅ Post-normalization complete!")


if __name__ == '__main__':
    main()
