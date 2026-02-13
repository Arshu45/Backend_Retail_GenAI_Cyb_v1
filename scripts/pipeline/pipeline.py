"""
Complete Data Processing Pipeline

This script runs the entire data processing workflow in series:
1. Normalize raw CSV
2. Deduplicate variants for chromadb ingestion
3. Populate categories in PostgreSQL
4. Import products to PostgreSQL

Usage:
    python pipeline.py <raw_csv> <config_json> [--deduplicate] [--skip-db]

Examples:
    # Full pipeline with deduplication and DB import
    python pipeline.py data/raw_vendor.csv normalization_config.json --deduplicate

    # Normalize + deduplicate only (skip DB)
    python pipeline.py data/raw_vendor.csv normalization_config.json --deduplicate --skip-db

    # Normalize + DB import (no deduplication)
    python pipeline.py data/raw_vendor.csv normalization_config.json
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()

# Import validation module
from validate_config import validate_normalization_config, validate_config_structure


def validate_env_variables(skip_db=False, skip_chroma=False):
    """Validate that all required environment variables are set"""
    print("\n" + "="*80)
    print("VALIDATING ENVIRONMENT VARIABLES")
    print("="*80)
    
    required_vars = []
    optional_vars = []
    
    # Database variables (required if not skipping DB)
    if not skip_db:
        required_vars.append(('DATABASE_URL', 'PostgreSQL connection string'))
    
    # ChromaDB variables (required if not skipping ChromaDB)
    if not skip_db and not skip_chroma:
        required_vars.extend([
            ('CSV_FILE_PATH', 'Path to CSV for ChromaDB ingestion'),
            ('CHROMA_DB_DIR', 'ChromaDB storage directory'),
            ('COLLECTION_NAME', 'ChromaDB collection name'),
            ('EMBEDDING_MODEL', 'Sentence transformer model'),
            ('DOCUMENT_COLUMNS', 'Columns to use for embeddings'),
            ('SCHEMA_DIR', 'Directory for generated schema files')
        ])
    
    missing_vars = []
    present_vars = []
    
    # Check required variables
    for var_name, description in required_vars:
        value = os.getenv(var_name)
        if not value or value.strip() == '':
            missing_vars.append((var_name, description))
        else:
            present_vars.append((var_name, description))
    
    # Print status
    if present_vars:
        print("\n✅ Found required variables:")
        for var_name, description in present_vars:
            # Mask sensitive values
            value = os.getenv(var_name)
            if 'PASSWORD' in var_name.upper() or 'KEY' in var_name.upper() or 'URL' in var_name.upper():
                display_value = value[:20] + '...' if len(value) > 20 else value
            else:
                display_value = value[:50] + '...' if len(value) > 50 else value
            print(f"  • {var_name:20} = {display_value}")
    
    if missing_vars:
        print("\n❌ Missing required variables:")
        for var_name, description in missing_vars:
            print(f"  • {var_name:20} - {description}")
        print("\n⚠️  Please add these variables to your .env file")
        return False
    
    print("\n✅ All required environment variables are set!")
    return True


def run_command(cmd, description):
    """Run a command and handle errors, returning (success, duration)"""
    print(f"\n{'='*80}")
    print(f"{description}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(cmd)}\n")
    
    start_time = time.time()
    try:
        subprocess.run(cmd, check=True, capture_output=False, text=True)
        duration = time.time() - start_time
        print(f"\n✅ {description} completed successfully! ({duration:.2f}s)")
        return True, duration
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        print(f"\n❌ {description} failed after {duration:.2f}s with exit code {e.returncode}")
        return False, duration


def main():
    if len(sys.argv) < 3:
        print("Usage: python pipeline.py <raw_csv> <config_json> [--deduplicate] [--skip-db] [--skip-chroma]")
        print("\nExamples:")
        print("  # Full pipeline with deduplication")
        print("  python pipeline.py data/raw_vendor.csv normalization_config.json --deduplicate")
        print()
        print("  # Normalize + DB import (no deduplication)")
        print("  python pipeline.py data/raw_vendor.csv normalization_config.json")
        print()
        print("  # Normalize + deduplicate only (skip DB and ChromaDB)")
        print("  python pipeline.py data/raw_vendor.csv normalization_config.json --deduplicate --skip-db")
        print()
        print("  # Skip ChromaDB ingestion only")
        print("  python pipeline.py data/raw_vendor.csv normalization_config.json --deduplicate --skip-chroma")
        sys.exit(1)
    
    raw_csv = sys.argv[1]
    config_json = sys.argv[2]
    should_deduplicate = '--deduplicate' in sys.argv
    skip_db = '--skip-db' in sys.argv
    skip_chroma = '--skip-chroma' in sys.argv
    
    # Validate inputs
    if not os.path.exists(raw_csv):
        print(f"❌ Error: Input file not found: {raw_csv}")
        sys.exit(1)
    
    if not os.path.exists(config_json):
        print(f"❌ Error: Config file not found: {config_json}")
        sys.exit(1)
    
    # Define output paths - store in data/processed_data
    output_dir = Path("data/processed_data")
    output_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    normalized_csv = output_dir / "normalized_output.csv"
    products_csv = output_dir / "unique_products.csv"
    
    # Validate environment variables before proceeding
    if not validate_env_variables(skip_db=skip_db, skip_chroma=skip_chroma):
        print("\n❌ Pipeline aborted due to missing environment variables")
        sys.exit(1)
    
    # Validate configuration against CSV
    print("\n" + "="*80)
    print("VALIDATING CONFIGURATION")
    print("="*80)
    
    # First validate config structure
    is_valid_structure, structure_errors = validate_config_structure(config_json)
    if not is_valid_structure:
        print("\n❌ Config structure validation failed:")
        for error in structure_errors:
            print(f"  • {error}")
        print("\n💡 Please fix the configuration file and try again.")
        sys.exit(1)
    
    print("✅ Config structure is valid")
    
    # Then validate aliases against CSV
    print("\n")
    print("Validating aliases against CSV columns...")
    is_valid, errors = validate_normalization_config(raw_csv, config_json)
    
    if not is_valid:
        print("\n❌ Configuration validation failed:")
        for error in errors:
            print(f"  • {error}")
        print("\n💡 Please fix the configuration file and try again.")
        sys.exit(1)
    
    print("\n")
    print("✅ All aliases are valid")
    
    
    # IMPORTANT: Always import normalized_output.csv to PostgreSQL
    # products.csv is for chromadb ingestion
    import_csv = normalized_csv
    
    print("="*80)
    print("STARTING DATA PROCESSING PIPELINE")
    print("="*80)
    print(f"Input:        {raw_csv}")
    print(f"Config:       {config_json}")
    print(f"Normalized:   {normalized_csv} (for PostgreSQL)")
    if should_deduplicate:
        print(f"Products:     {products_csv} (for analytics)")
    print(f"Deduplicate:  {'Yes' if should_deduplicate else 'No'}")
    print(f"Import to DB: {'No (skipped)' if skip_db else 'Yes'}")
    print("="*80)
    
    print("\n📋 Executing Pipeline Steps...")
    
    # Store durations for summary
    durations = {}
    
    # Step 1: Normalize CSV
    normalize_cmd = [
        'python3',
        str(SCRIPT_DIR / 'normalize_csv.py'),
        raw_csv,
        str(normalized_csv),
        config_json
    ]
    
    success, duration = run_command(normalize_cmd, "Step 1: Normalize CSV")
    if not success:
        print("\n❌ Pipeline failed at normalization step")
        sys.exit(1)
    durations['normalize'] = duration
    
    # Step 2: Deduplicate (if requested)
    if should_deduplicate:
        deduplicate_cmd = [
            'python3',
            str(SCRIPT_DIR / 'deduplicate_variants.py'),
            str(normalized_csv),
            str(products_csv),
            config_json
        ]
        
        success, duration = run_command(deduplicate_cmd, "Step 2: Extracting unique products")
        if not success:
            print("\n❌ Pipeline failed at deduplication step")
            sys.exit(1)
        durations['deduplicate'] = duration
    
    # Step 3: Database Import (if not skipped)
    # Note: import_normalized_data.py now handles category population automatically
    if not skip_db:
        import_cmd = [
            'python3',
            str(SCRIPT_DIR / 'import_normalized_data.py'),
            str(import_csv)
        ]
        
        step_num = 3 if should_deduplicate else 2
        success, duration = run_command(import_cmd, f"Step {step_num}: Import to PostgreSQL (Categories + Products)")
        if not success:
            print("\n❌ Pipeline failed at database import step")
            sys.exit(1)
        durations['import_db'] = duration
        
        # Step 4: ChromaDB Ingestion (if not skipped)
        if not skip_chroma:
            chroma_cmd = ['python3', str(SCRIPT_DIR / 'chromadb_ingestion.py')]
            chroma_step_num = 4 if should_deduplicate else 3
            success, duration = run_command(chroma_cmd, f"Step {chroma_step_num}: Ingest to ChromaDB (Vector Search)")
            if not success:
                print("\n❌ Pipeline failed at ChromaDB ingestion step")
                sys.exit(1)
            durations['chroma'] = duration
        else:
            print("\n⏭️  Skipping ChromaDB ingestion (--skip-chroma flag)")
    
    # Schema Generation: Runs independently (only needs CSV, not DB)
    # Calculate step number based on what was skipped
    if should_deduplicate:
        if skip_db:
            schema_step_num = 3
        elif skip_chroma:
            schema_step_num = 4
        else:
            schema_step_num = 5
    else:
        if skip_db:
            schema_step_num = 2
        elif skip_chroma:
            schema_step_num = 3
        else:
            schema_step_num = 4
    
    schema_cmd = ['python3', str(SCRIPT_DIR / 'csv_schema_generator.py')]
    success, duration = run_command(schema_cmd, f"Step {schema_step_num}: Generate Attribute Schema")
    if not success:
        print("\n❌ Pipeline failed at schema generation step")
        sys.exit(1)
    durations['schema'] = duration
    
    # Summary
    print("\n" + "-"*80)
    print("✅ PIPELINE COMPLETED SUCCESSFULLY!")
    print("-"*80)
    print("\n📁 Output Files:")
    print(f"  ✓ Normalized CSV: {normalized_csv}")
    if should_deduplicate:
        print(f"  ✓ Products CSV:   {products_csv}")
    print(f"  ✓ Schema JSON:    {SCRIPT_DIR / '..'/ '..'/ 'data' / 'schema' / 'catalog_ai_schema.json'}")
    
    print("\n📋 Pipeline Steps Completed:")
    print(f"  1. ✅ Normalize raw CSV ({durations.get('normalize', 0):.2f}s)")
    
    current_step = 2
    if should_deduplicate:
        print(f"  {current_step}. ✅ Extracting unique products ({durations.get('deduplicate', 0):.2f}s)")
        current_step += 1
    
    if not skip_db:
        print(f"  {current_step}. ✅ Import to PostgreSQL ({durations.get('import_db', 0):.2f}s)")
        current_step += 1
        if not skip_chroma:
            print(f"  {current_step}. ✅ Ingest to ChromaDB ({durations.get('chroma', 0):.2f}s)")
            current_step += 1
    
    print(f"  {current_step}. ✅ Generate attribute schema ({durations.get('schema', 0):.2f}s)")
    
    total_time = sum(durations.values())
    print(f"\n⏱️  Total execution time: {total_time:.2f}s")
    print("="*80)


if __name__ == '__main__':
    main()

