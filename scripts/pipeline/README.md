# Data Processing Pipeline

## Overview

The pipeline processes raw vendor CSV files through multiple stages:
1. **Normalize** - Standardize column names and data formats
2. **Deduplicate** - Group product variants into unique products
3. **Import to PostgreSQL** - Populate database with categories and products
4. **Ingest to ChromaDB** - Create vector embeddings for semantic search
5. **Generate Schema** - Create attribute schema for frontend filters

## Quick Start

### Full Pipeline
```bash
python3 scripts/pipeline/pipeline.py data/raw/magento_products_20K_v2.csv scripts/config/normalization_config.json --deduplicate
```


### Skip ChromaDB Ingestion
```bash
python3 scripts/pipeline/pipeline.py data/raw/magento_products_20K_v2.csv scripts/config/normalization_config.json --deduplicate --skip-chroma
```

### Normalize Only (No DB Import)
```bash
python3 scripts/pipeline/pipeline.py data/raw/magento_products_20K_v2.csv scripts/config/normalization_config.json --deduplicate --skip-db
```

## Pipeline Components

### 1. normalize_csv.py
Standardizes raw vendor CSV files using a configuration schema.

**Input:**
- Raw CSV file (e.g., `data/raw/magento_products_20K_v2.csv`)
- Configuration JSON (e.g., `scripts/config/normalization_config.json`)

**Output:**
- `data/processed_data/normalized_output.csv` - Standardized data ready for PostgreSQL

**Features:**
- Dynamic column mapping based on config
- Type conversion and validation
- Handles missing fields gracefully
- Preserves original data integrity

### 2. deduplicate_variants.py
Groups product variants (same SKU base, different sizes/colors) into unique products.

**Input:**
- Normalized CSV from step 1

**Output:**
- `data/processed_data/unique_products.csv` - Aggregated products for analytics

**Features:**
- SKU-based grouping (removes size/color suffixes)
- Aggregates variants into arrays
- Calculates price ranges
- Preserves all variant information

### 3. import_normalized_data.py
Imports normalized data into PostgreSQL with dynamic schema generation.

**Input:**
- Normalized CSV from step 1 (NOT unique products)

**Output:**
- PostgreSQL tables: `products`, `categories`, `product_categories`

**Features:**
- Dynamic schema creation from CSV headers
- Automatic category extraction and population
- Product-category relationship mapping
- Indexed for performance (product_id, sku, brand, product_type)

### 4. chromadb_ingestion.py
Creates vector embeddings for semantic search.

**Input:**
- Reads from CSV path specified in `.env` (`CSV_FILE_PATH`)

**Output:**
- ChromaDB collection with embeddings

**Features:**
- Sentence transformer embeddings
- Configurable document fields
- Metadata preservation
- Incremental updates

### 5. csv_schema_generator.py
Generates attribute schema for frontend filter system.

**Input:**
- Reads from CSV path specified in `.env` (`CSV_FILE_PATH`)

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
# PostgreSQL
DATABASE_URL=postgresql://user:password@host:port/database

# ChromaDB (only required if not using --skip-chroma)
CSV_FILE_PATH=data/processed_data/normalized_output.csv
CHROMA_DB_DIR=./chroma_db
COLLECTION_NAME=products
EMBEDDING_MODEL=all-MiniLM-L6-v2
DOCUMENT_COLUMNS=title,description
SCHEMA_DIR=./schemas
```

### Normalization Config (normalization_config.json)
Defines the schema and column mappings for your vendor's CSV format.

## Output Files

All processed files are stored in `data/processed_data/`:
- `normalized_output.csv` - For PostgreSQL import (all variants, 67,769 rows)
- `unique_products.csv` - For ChromaDB ingestion (unique products, 23,690 rows)

## Pipeline Results (Example)

Based on the Magento 20K dataset:

**Step 1: Normalize CSV**
- Input: 67,769 rows × 26 columns
- Output: 67,769 rows × 28 columns
- Standardized fields: product_id, sku, title, price, stock_status, etc.

**Step 2: Deduplicate Variants**
- Input: 67,769 variants
- Output: 23,690 unique products
- Average variants per product: 2.9

**Step 3: Import to PostgreSQL**
- Products: 67,769
- Categories: 792
- Product-Category mappings: 104,268

**Step 4: Ingest to ChromaDB**
- Vector embeddings created for semantic search

**Step 5: Generate Schema**
- Attribute schema generated for frontend filters
- Auto-detected enums, number ranges, and date fields

## Important Notes

⚠️ **Always import `normalized_output.csv` to PostgreSQL**, not the unique products file!
- PostgreSQL needs all variants as separate rows
- Unique products file is for analytics/reporting only

✅ **Config validation before processing**
- Validates all critical field aliases (product_id, sku, title, price) exist in CSV
- Warns about optional fields that are missing
- Catches typos early with clear error messages
- Prevents silent failures and data loss

✅ **Pipeline validates environment variables** before running
- Checks for required `.env` variables based on flags
- Fails fast if configuration is missing
- Skips validation for ChromaDB vars if `--skip-chroma` is used


## Troubleshooting

### "File not found" errors
- Make sure input CSV and config JSON paths are correct
- Use relative paths from project root: `data/raw/file.csv`

### Database connection errors
- Verify `DATABASE_URL` in `.env`
- Check PostgreSQL is running and accessible
- Test connection: `psql $DATABASE_URL`

### ChromaDB errors
- Ensure `CSV_FILE_PATH` points to normalized output
- Verify `CHROMA_DB_DIR` is writable
- Use `--skip-chroma` flag to skip this step during testing

## Examples

### Process new vendor CSV
```bash
# 1. Add vendor config to scripts/config/
# 2. Run pipeline
python3 scripts/pipeline/pipeline.py data/raw/new_vendor.csv scripts/config/new_vendor_config.json --deduplicate
```

### Re-import existing data
```bash
# Skip normalization, just re-import to PostgreSQL
python3 scripts/pipeline/import_normalized_data.py data/processed_data/normalized_output.csv
```

### Update ChromaDB only
```bash
# Make sure CSV_FILE_PATH is set in .env
python3 scripts/pipeline/chromadb_ingestion.py
```

### Development workflow
```bash
# Test normalization only (fast iteration)
python3 scripts/pipeline/pipeline.py data/raw/sample.csv scripts/config/normalization_config.json --skip-db

# Test with DB but skip ChromaDB (faster)
python3 scripts/pipeline/pipeline.py data/raw/sample.csv scripts/config/normalization_config.json --deduplicate --skip-chroma
```
