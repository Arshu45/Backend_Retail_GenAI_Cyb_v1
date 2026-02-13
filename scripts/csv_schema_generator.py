import os
import csv
import json
import time
from collections import defaultdict
from typing import Dict, Optional
from src.utils.value_parsers import is_number, is_date
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CSV_FILE_PATH = os.getenv("CSV_FILE_PATH")
SCHEMA_DIR = os.getenv("SCHEMA_DIR")
CATALOG_NAME = os.getenv("COLLECTION_NAME")

SCHEMA_FILE = f"{CATALOG_NAME}_schema.json"
output_schema_path = os.path.join(SCHEMA_DIR, SCHEMA_FILE)

DOCUMENT_COLUMNS = {
    col.strip().lower()
    for col in os.getenv("DOCUMENT_COLUMNS", "").split(",")
    if col.strip()
}

ENUM_MAX_UNIQUE_VALUES = int(os.getenv("ENUM_MAX_UNIQUE_VALUES", 50))

def generate_schema_from_csv(csv_file_path: str) -> Dict:
    """
    Generate attribute schema from a CSV file.
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

    for col in all_columns:

        # âœ… Pure numeric â†’ number_range
        if numeric_count[col] > 0 and string_count[col] == 0:
            schema[col] = {
                "type": "number_range",
                "rules": {
                    "operators": ["$eq", "$lt", "$gt", "$gte", "$lte"]
                }
            }
            continue

        # âœ… Pure date â†’ date
        if date_count[col] > 0 and numeric_count[col] == 0 and string_count[col] == 0:
            schema[col] = {
                "type": "date",
                "rules": {
                    "operators": ["$eq", "$lt", "$gt", "$gte", "$lte"]
                }
            }
            continue

        # âœ… Enum â†’ low cardinality strings
        if 0 < len(column_values[col]) <= ENUM_MAX_UNIQUE_VALUES:
            schema[col] = {
                "type": "enum",
                "rules": {
                    "values": sorted(column_values[col])
                }
            }
            continue

        # âœ… Fallback â†’ free text
        schema[col] = {
            "type": "string",
            "rules": {
                "description": "free text attribute"
            }
        }
    # Optional file write
    if output_schema_path:
        os.makedirs(os.path.dirname(output_schema_path), exist_ok=True)
        with open(output_schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)

    elapsed = time.time() - start_time

    print("âœ… Schema generation completed")
    print(f"ðŸ”¢ Total attributes: {len(schema)}")
    print(f"â�± Time taken: {elapsed:.4f} seconds")

    if output_schema_path:
        print(f"ðŸ“� Schema written to: {output_schema_path}")

    #return schema


if __name__ == "__main__":
    generate_schema_from_csv(CSV_FILE_PATH)
    