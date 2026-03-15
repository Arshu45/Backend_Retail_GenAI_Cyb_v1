#!/usr/bin/env python3
"""
Occasion Tag Products Script

Runs after post_normalize.py to add an occasion `tags` column to the product CSV.

For each product row, it concatenates all string column values into a single
text block, then matches against the keywords defined in occasion_config.json.
If a keyword is found, the corresponding occasion name is added to the product's tags.
A product can have multiple tags (stored as a comma-separated string in the CSV,
split into a native list by chromadb_ingestion.py at ingest time).

Usage:
    python tag_products.py <input_csv> <output_csv> <occasion_config_json>

    This script is called as a pipeline step by pipeline.py.

Example:
    python tag_products.py \\
        data/processed_data/post_normalized_magento_products.csv \\
        data/processed_data/tagged_magento_products.csv \\
        scripts/config/occasion_config.json
"""

import re
import sys
import json
import pandas as pd
from pathlib import Path
from logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)


def print_usage():
    print("""
Usage: python tag_products.py <input_csv> <output_csv> <occasion_config_json>

Arguments:
  input_csv              Path to post-normalized CSV (output of post_normalize.py)
  output_csv             Path to write the tagged CSV
  occasion_config_json   Path to occasion_config.json

This script is called as a pipeline step by pipeline.py.
""")


def load_occasion_config(config_path):
    """
    Load and validate the occasion configuration JSON.

    Args:
        config_path: Path to occasion_config.json

    Returns:
        dict: { occasion_name: [keyword, ...], ... }
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error loading occasion config: {e}")
        sys.exit(1)

    occasions = config.get('occasions', {})
    if not occasions:
        print("⚠️  Warning: No occasions defined in occasion_config.json")

    # Flatten to { occasion_name: [keywords] } with lowercase tag names and keywords.
    # If the same tag name appears multiple times under different cases (e.g. "Birthday"
    # and "birthday"), their keyword lists are merged into a single entry.
    occasion_keywords = {}
    for occasion_name, occasion_data in occasions.items():
        normalised_name = occasion_name.lower().strip()
        keywords = [kw.lower().strip() for kw in occasion_data.get('keywords', []) if kw.strip()]
        if normalised_name in occasion_keywords:
            occasion_keywords[normalised_name].extend(keywords)
        else:
            occasion_keywords[normalised_name] = keywords
        logger.debug(f"  Occasion '{normalised_name}': {len(keywords)} keywords")

    return occasion_keywords


def tokenise(text: str) -> set:
    """
    Split a lowercase string into a set of pure alphanumeric tokens,
    stripping all punctuation and special characters.

    Using a token-set approach (rather than a plain substring or regex word-boundary
    check) guarantees that keywords only match whole, standalone words — so e.g.
    'bow' will never match inside 'elbow', and 'led' won't match inside 'called',
    regardless of surrounding punctuation or hyphens.

    Args:
        text: Lowercased string to tokenise.

    Returns:
        set: Set of alphanumeric token strings.
    """
    return set(re.findall(r"[a-z0-9]+", text))


def build_combined_text(row):
    """
    Concatenate all non-null string values in a row into a single
    lowercase searchable text block.

    Args:
        row: pandas Series (a single product row)

    Returns:
        str: combined lowercase text from all string columns
    """
    parts = []
    for val in row.values:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        str_val = str(val).strip()
        if str_val:
            parts.append(str_val.lower())
    return " ".join(parts)


def assign_tags(row, occasion_keywords):
    """
    Match a product row against all occasion keywords and return
    a comma-separated string of matched occasion names.

    Matching uses exact token comparison: the row text is split into a set of
    clean alphanumeric tokens, and each keyword must appear as a complete token
    (or all tokens present for multi-word keywords). This prevents partial-word
    false positives such as 'bow' matching 'elbow'.

    Args:
        row: pandas Series
        occasion_keywords: dict { occasion_name: [keyword, ...] }

    Returns:
        str: comma-separated occasion names (e.g. "birthday,festival"),
             or "" if no match
    """
    combined_text = build_combined_text(row)
    row_tokens = tokenise(combined_text)
    matched = []

    for occasion_name, keywords in occasion_keywords.items():
        for keyword in keywords:
            keyword_tokens = tokenise(keyword)
            # All tokens in the keyword must be present in the row token set.
            # This also supports multi-word keywords (e.g. "birthday party").
            if keyword_tokens and keyword_tokens.issubset(row_tokens):
                matched.append(occasion_name)
                break  # One keyword match per occasion is enough

    return ",".join(matched)


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
    occasion_config_json = sys.argv[3]

    # =========================================================
    # LOAD OCCASION CONFIG
    # =========================================================
    logger.debug("=" * 80)
    logger.debug("LOADING OCCASION CONFIG")
    logger.debug("=" * 80)
    occasion_keywords = load_occasion_config(occasion_config_json)
    logger.debug(f"Loaded {len(occasion_keywords)} occasions from config")

    # =========================================================
    # LOAD INPUT CSV
    # =========================================================
    logger.debug(f"Reading input CSV: {input_csv}")
    try:
        df = pd.read_csv(input_csv, low_memory=False)
        logger.debug(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    except Exception as e:
        print(f"❌ Error reading input CSV: {e}")
        sys.exit(1)

    # =========================================================
    # ASSIGN TAGS COLUMN
    # =========================================================
    logger.debug("Assigning occasion tags to products...")
    df['tags'] = df.apply(lambda row: assign_tags(row, occasion_keywords), axis=1)

    # Tagging summary
    tagged_count = (df['tags'] != "").sum()
    untagged_count = (df['tags'] == "").sum()
    logger.debug(f"  Tagged products:   {tagged_count:,}")
    logger.debug(f"  Untagged products: {untagged_count:,}")

    # Per-occasion breakdown
    for occasion_name in occasion_keywords:
        count = df['tags'].str.contains(occasion_name, na=False).sum()
        logger.debug(f"  [{occasion_name}]: {count:,} products")

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

    logger.debug("✅ Tag products complete!")


if __name__ == '__main__':
    main()