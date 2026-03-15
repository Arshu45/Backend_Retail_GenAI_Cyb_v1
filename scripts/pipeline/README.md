# Data Processing Pipeline

## Overview

The pipeline processes vendor provided CSV files through multiple stages:
1. **Normalize** - Standardize column names and data formats
2. **Post-Normalize** - Add `sku_base` and enforce strict schema (It didn't include  pass-through columns)
3. **Extract Unique Products** - Group product variants using sku_base
4. **Import to PostgreSQL** - Populate database with categories and products (optional)
5. **Ingest to Vector Database** - Create vector embeddings for semantic search (optional)
6. **Generate Attribute Schema** - Generate attribute schema for metadata filtering.

## Quick Start

### Show Help
```bash
python3 scripts/pipeline/pipeline.py --help
```
### Full Pipeline (Default)
```bash
python3 scripts/pipeline/pipeline.py data/raw/magento_products.csv scripts/config/normalization_config.json
```
Runs all steps: Normalize → Post-Normalize → Extract unique products → PostgreSQL → Vector DB ingestion → Attribute Schema generation

### Skip Vector DB Ingestion
```bash
python3 scripts/pipeline/pipeline.py data/raw/magento_products.csv scripts/config/normalization_config.json --skip-ingestion
```
Runs: Normalize → Post-Normalize → Extract unique products → PostgreSQL → Attribute Schema generation

### Skip PostgreSQL Import
```bash
python3 scripts/pipeline/pipeline.py data/raw/magento_products.csv scripts/config/normalization_config.json --no-import-data
```
Runs: Normalize → Post-Normalize → Extract unique products → Vector DB ingestion → Attribute Schema generation


## Pipeline Components

### 1. normalize_csv.py
Standardizes vendor provided CSV files using a configuration schema json file. The configuration json file contains the mapping of columns and their data types. 

**Input:**
- Raw CSV file (e.g., `data/raw/magento_products.csv`)
- Configuration JSON (e.g., `scripts/config/normalization_config.json`)

**Output:**
- `data/processed_data/normalized_*.csv` - Full standardized data (all columns). This file is used for PostgreSQL import.

**Features:**
- Dynamic column mapping based on config
- Type conversion and validation
- Handles missing fields gracefully
- Preserves original data integrity

### 2. post_normalize.py
Cleans the normalized data and adds internal derived fields (sku_base). It also enforces a strict schema by stripping all pass-through columns.

**Input:**
- Normalized CSV from step 1

**Output:**
- `data/processed_data/post_normalized_*.csv` - Strictly schema-compliant data + `sku_base`. Used for grouping product variants.

**Features:**
- Adds `sku_base` field (derived from `sku`)
- Enforces strict schema by stripping all pass-through columns

### 3. consolidate_product_variants.py
Groups product variants (same SKU base, different sizes/colors) into unique products. 

**Input:**
- Post-normalized CSV from step 2

**Output:**
- `data/processed_data/unique_*.csv` - Note : Currently we are not using this file.

**Features:**
- SKU-based grouping (removes size/color suffixes)
- Stores colors, prices etc. data comma separated
- Preserves all variant information

### 4. import_normalized_data.py
Imports data into PostgreSQL with dynamic schema generation. It also creates the necessary tables and populates them with the data from the CSV file.
Note : Database (yourdatabasename) must be created in postgresql before running this script.

**Input:**
- Normalized CSV from step 1 (Full data with all columns)

**Output:**
- PostgreSQL tables: `products`, `categories`, `product_categories`

**Features:**
- Dynamic schema creation from CSV headers
- Automatic category extraction and population
- Product-category relationship mapping
- Indexed for performance (product_id, sku, brand, product_type)

### 5. chromadb_ingestion.py
Creates vector embeddings for semantic search. It also creates the necessary documents (tables) and populates them with the data from the CSV file.

**Input:**
- Post normalized data from step 2 (Strictly schema-compliant data + `sku_base`)

**Output:**
- ChromaDB collection with embeddings

**Features:**
- Sentence transformer embeddings
- Configurable document fields
- Metadata preservation
- Incremental updates

### 6. csv_schema_generator.py
Generates attribute schema for frontend filter system.

**Input:**
- Post normalized data from step 2 (Strictly schema-compliant data + `sku_base`)

**Output:**
- `{SCHEMA_DIR}/{COLLECTION_NAME}_schema.json` - Attribute schema file

**Features:**
- Auto-detects attribute types (enum, number_range, date, string)
- Identifies low-cardinality fields as enums
- Generates filter operators for each attribute
- Skips document columns (title, description)

## Configuration

### Environment Variables (.env)
```bash
# PostgreSQL Database Configuration
DB_NAME=yourdatabasename
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Vector Database
CHROMA_DB_DIR=./chroma_db
COLLECTION_NAME=products
EMBEDDING_MODEL=all-MiniLM-L6-v2
DOCUMENT_COLUMNS=title,description
SCHEMA_DIR=./schemas
```

## Logging

The pipeline uses a dual-output logging system:

### Console Output (INFO level)
- Shows only important steps and progress
- Clean, minimal output on terminal for monitoring
- Example: "✅ Pipeline completed successfully!"

### Log Files (DEBUG level)
- Detailed execution information
- Full command outputs and debug info
- Location: `logs/pipeline_YYYYMMDD_HHMMSS.log`
- Auto-created with timestamp

**Log file example:**
```
2026-02-17 12:20:15 - __main__ - INFO - STARTING DATA PROCESSING PIPELINE
2026-02-17 12:20:15 - __main__ - DEBUG - Command: python3 normalize_csv.py input.csv
2026-02-17 12:20:18 - __main__ - INFO - ✅ Normalize raw CSV (3.40s)
```

**Note:** The pipeline automatically detects child processes and routes all logs to the same file.


### Output Files

The pipeline generates output files with names based on the input file:
- Input: `data/raw/magento_products.csv`
- Output: `data/processed_data/normalized_magento_products.csv`
- Output: `data/processed_data/post_normalized_magento_products.csv`
- Output: `data/processed_data/unique_magento_products.csv`
- Schema: `data/schema/catalog_ai_schema.json` (uses `COLLECTION_NAME` from .env)

CSV files are uniquely named per vendor to prevent overwrites. The schema filename remains consistent based on `COLLECTION_NAME`.

### Normalization Config (normalization_config.json)
Defines the schema and column mappings for your vendor's CSV format.

Eg: 
```
{
  "schema_version": "1.0",
  "import_mode": "config_only",
  "output_schema": [
    {
      "name": "product_id",
      "aliases": [
        "entity_id",
        "product_id",
        "id",
        "item_id"
      ],
      "transform": "safe_int"
    }
  ]
}

```

## Pipeline Results (Example)

Based on the Magento dataset:

**Step 1: Normalize CSV**
- Input: 67,769 rows × 26 columns
- Output: 67,769 rows × 26 columns (Standardized names)

**Step 2: Post-normalize**
- Input: 67,769 rows × 26 columns
- Output: 67,769 rows × 14 columns (Strict schema + `sku_base`)

**Step 3: Consolidate Product Variants**
- Input: 67,769 variants
- Output: 23,690 unique products

**Step 4: Import to PostgreSQL**
- Products: 67,769 (Imported from Step 1 output)
- Categories: 792
- Product-Category mappings: 104,268

**Step 5: Ingest to ChromaDB**
- Vector embeddings created for semantic search (from Step 2 output)

**Step 6: Generate Schema**
- Attribute schema generated for frontend filters (from Step 2 output)

## Important Notes

⚠️ **Always import `normalized_*.csv` to PostgreSQL**, not the post-normalized or unique products files!
- PostgreSQL needs the full original column set for data preservation.

✅ **Config validation before processing**
- Validates all critical field aliases (product_id, sku, title, price) exist in CSV
- Warns about optional fields that are missing
- Catches typos early with clear error messages
- Prevents silent failures and data loss

✅ **Pipeline validates environment variables** before running
- Checks for required `.env` variables based on flags
- Fails fast if configuration is missing
- Skips validation for vector DB vars if `--skip-ingestion` is used
- Skips validation for PostgreSQL vars if `--no-import-data` is used


## Troubleshooting

### "File not found" errors
- Make sure input CSV and config JSON paths are correct
- Use relative paths from project root: `data/raw/file.csv`

### Database connection errors
- Verify database configuration in `.env` (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
- Check PostgreSQL is running: `pg_isready -h localhost -p 5432`
- Test connection: `psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME`

### Vector Database errors
- Ensure CSV file path is passed correctly to the script
- Verify `CHROMA_DB_DIR` is writable
- Use `--skip-ingestion` flag to skip this step during testing

## Examples

### Process new vendor CSV
```bash
# 1. Add vendor config to scripts/config/
# 2. Run pipeline (deduplication always enabled)
python3 scripts/pipeline/pipeline.py data/raw/new_vendor.csv scripts/config/new_vendor_config.json
```

### Update Vector DB only
```bash
# Run ingestion on existing unique products file
python3 scripts/pipeline/chromadb_ingestion.py data/processed_data/post_normalized_magento_products.csv
```

### Generate schema only
```bash
python3 scripts/pipeline/csv_schema_generator.py data/processed_data/post_normalized_magento_products.csv
```

### Development workflow
```bash
# Skip PostgreSQL import (fast iteration)
python3 scripts/pipeline/pipeline.py data/raw/sample.csv scripts/config/normalization_config.json --no-import-data

# Import to PostgreSQL only (skip vector DB for faster testing)
python3 scripts/pipeline/pipeline.py data/raw/sample.csv scripts/config/normalization_config.json --skip-ingestion
```
