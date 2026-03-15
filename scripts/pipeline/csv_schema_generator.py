import os
import sys
import csv
import json
import time
from logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)
from collections import defaultdict
from typing import Dict, Optional

# Add project root to Python path for src imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from src.utils.value_parsers import is_number, is_date
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# CSV file path is required as command-line argument
if len(sys.argv) < 2:
    print("❌ Error: CSV file path not provided")
    print("Usage: python csv_schema_generator.py <csv_file_path>")
    sys.exit(1)

CSV_FILE_PATH = sys.argv[1]
SCHEMA_DIR = os.getenv("SCHEMA_DIR")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# Use COLLECTION_NAME for schema filename (consistent across vendors)
SCHEMA_FILE = f"{COLLECTION_NAME}_schema.json"
output_schema_path = os.path.join(SCHEMA_DIR, SCHEMA_FILE)

DOCUMENT_COLUMNS = {
    col.strip().lower()
    for col in os.getenv("DOCUMENT_COLUMNS", "").split(",")
    if col.strip()
}

ENUM_MAX_UNIQUE_VALUES = int(os.getenv("ENUM_MAX_UNIQUE_VALUES", 50))

# Columns that should always be treated as enum regardless of cardinality.
# Use this for attributes like "color" that may have many unique values in
# large catalogs but must remain enum so the LLM can validate against real values.
# Configure in .env as a comma-separated list: FORCE_ENUM_COLUMNS=color,material
FORCE_ENUM_COLUMNS = {
    col.strip().lower()
    for col in os.getenv("FORCE_ENUM_COLUMNS", "").split(",")
    if col.strip()
}


def generate_schema_from_csv(csv_file_path: str) -> Dict:
    """
    Generate attribute schema from a CSV file.

    Type detection logic (in priority order):
    1. FORCE_ENUM_COLUMNS  — always enum, regardless of cardinality
    2. Pure numeric        — number_range
    3. Pure date           — date
    4. Low cardinality     — enum (up to ENUM_MAX_UNIQUE_VALUES unique values)
    5. Fallback            — free-text string
    """
    start_time = time.time()
    column_values = defaultdict(set)
    numeric_count = defaultdict(int)
    string_count = defaultdict(int)
    date_count = defaultdict(int)

    with open(csv_file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            for col, val in row.items():
                if not col:
                    continue

                col_name = col.strip().lower()

                if col_name in DOCUMENT_COLUMNS:
                    continue

                if val is None:
                    continue

                val = val.strip()
                if not val:
                    continue

                if is_number(val):
                    numeric_count[col_name] += 1
                elif is_date(val):
                    date_count[col_name] += 1
                else:
                    string_count[col_name] += 1
                    column_values[col_name].add(val.lower())

    schema = {}

    all_columns = set(numeric_count) | set(string_count) | set(date_count)

    if FORCE_ENUM_COLUMNS:
        logger.debug(f"Force-enum columns: {FORCE_ENUM_COLUMNS}")

    for col in all_columns:

        # -------------------------------------------------------
        # PRIORITY 1: FORCE_ENUM_COLUMNS
        # -------------------------------------------------------
        # Columns explicitly listed in FORCE_ENUM_COLUMNS are always
        # classified as enum, regardless of how many unique values they have.
        # This is critical for attributes like "color" in large catalogs
        # where values like "rose gold" or "crystal pink" exceed the normal
        # ENUM_MAX_UNIQUE_VALUES threshold but must still be validated by
        # the LLM against real values rather than treated as free text.
        # If the column has no string values at all (e.g. all numeric),
        # fall through to normal type detection below.
        if col in FORCE_ENUM_COLUMNS and col in column_values:
            unique_values = sorted(column_values[col])
            schema[col] = {
                "type": "enum",
                "rules": {
                    "values": unique_values
                }
            }
            logger.debug(f"  [{col}] → force-enum ({len(unique_values)} unique values)")
            continue

        # -------------------------------------------------------
        # PRIORITY 2: Pure numeric → number_range
        # -------------------------------------------------------
        if numeric_count[col] > 0 and string_count[col] == 0:
            schema[col] = {
                "type": "number_range",
                "rules": {
                    "operators": ["$eq", "$lt", "$gt", "$gte", "$lte"]
                }
            }
            logger.debug(f"  [{col}] → number_range")
            continue

        # -------------------------------------------------------
        # PRIORITY 3: Pure date → date
        # -------------------------------------------------------
        if date_count[col] > 0 and numeric_count[col] == 0 and string_count[col] == 0:
            schema[col] = {
                "type": "date",
                "rules": {
                    "operators": ["$eq", "$lt", "$gt", "$gte", "$lte"]
                }
            }
            logger.debug(f"  [{col}] → date")
            continue

        # -------------------------------------------------------
        # PRIORITY 4: Low cardinality strings → enum
        # -------------------------------------------------------
        if 0 < len(column_values[col]) <= ENUM_MAX_UNIQUE_VALUES:
            schema[col] = {
                "type": "enum",
                "rules": {
                    "values": sorted(column_values[col])
                }
            }
            logger.debug(f"  [{col}] → enum ({len(column_values[col])} unique values)")
            continue

        # -------------------------------------------------------
        # PRIORITY 5: Fallback → free-text string
        # -------------------------------------------------------
        schema[col] = {
            "type": "string",
            "rules": {
                "description": "free text attribute"
            }
        }
        logger.debug(f"  [{col}] → string (free text, {len(column_values[col])} unique values)")

    # -------------------------------------------------------
    # Write schema to file
    # -------------------------------------------------------
    if output_schema_path:
        os.makedirs(os.path.dirname(output_schema_path), exist_ok=True)
        with open(output_schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)

    elapsed = time.time() - start_time

    logger.debug("✅ Schema generation completed")
    logger.debug(f"🔢 Total attributes: {len(schema)}")
    logger.debug(f"⏱ Time taken: {elapsed:.4f} seconds")

    if output_schema_path:
        logger.debug(f"Schema written to: {output_schema_path}")


if __name__ == "__main__":
    generate_schema_from_csv(CSV_FILE_PATH)