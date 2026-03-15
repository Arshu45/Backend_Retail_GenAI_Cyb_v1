"""
Complete Data Processing Pipeline

This script runs the entire data processing workflow in series:
1. Normalize raw CSV
2. Extracts only SKU Base and keep only the necessary columns specified in the config file.
3. Extracts unique products
4. Import to PostgreSQL (optional)
5. Ingest to vector database (optional)
6. Generate attribute schema

Usage:
    python pipeline.py <raw_csv> <config_json> [options]
    python pipeline.py --help

Options:
    --no-import-data     Skip PostgreSQL import only
    --skip-ingestion     Skip vector database ingestion only
    --help, -h           Show this help message

Examples:
    # Full pipeline (normalize + consolidate + import to PostgreSQL + Vector DB ingestion + CSV Schema Generation)
    python pipeline.py data/raw_vendor.csv config.json

    # Skip PostgreSQL import only
    python pipeline.py data/raw_vendor.csv config.json --no-import-data

    # Import to PostgreSQL only (skips vector db ingestion)
    python pipeline.py data/raw_vendor.csv config.json --skip-ingestion
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()

# Import validation module
from validate_config import validate_normalization_config, validate_config_structure

def validate_env_variables(no_import_data=False, skip_ingestion=False):

    """Validate that all required environment variables are set"""
    logger.debug("="*80)
    logger.debug("VALIDATING ENVIRONMENT VARIABLES")
    logger.debug("="*80)
    
    required_vars = []
    optional_vars = []
    
    # Database variables (required if importing data)
    if not no_import_data:
        required_vars.extend([
            ('DB_NAME', 'PostgreSQL database name'),
            ('DB_USER', 'PostgreSQL user'),
            ('DB_PASSWORD', 'PostgreSQL password'),
            ('DB_HOST', 'PostgreSQL host'),
            ('DB_PORT', 'PostgreSQL port')
        ])
    
    # Vector DB variables (required if not skipping vector DB and not skipping PostgreSQL)
    # Note: Vector DB can run independently, but typically needs data in PostgreSQL first
    if not skip_ingestion:
        required_vars.extend([
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
        for var_name, description in present_vars:
            # Mask sensitive values
            value = os.getenv(var_name)
            if 'PASSWORD' in var_name.upper() or 'KEY' in var_name.upper() or 'URL' in var_name.upper():
                display_value = value[:20] + '...' if len(value) > 20 else value
            else:
                display_value = value[:50] + '...' if len(value) > 50 else value
            logger.debug(f"  • {var_name:20} = {display_value}")
    
    if missing_vars:
        print("\n❌ Missing required variables:")
        for var_name, description in missing_vars:
            logger.debug(f"  • {var_name:20} - {description}")
        print("\n⚠️  Please add these variables to your .env file")
        return False
    
    logger.debug("✅ All required environment variables are set!")
    return True


def validate_inputs(raw_csv, config_json, no_import_data=False, skip_ingestion=False):
    """
    Validate all inputs before running the pipeline.
    
    Args:
        raw_csv: Path to raw CSV file
        config_json: Path to configuration JSON file
        no_import_data: Whether PostgreSQL import is skipped
        skip_ingestion: Whether vector DB ingestion is skipped
    
    Returns:
        bool: True if all validations pass, False otherwise
    """
    # 1. Validate file existence
    if not os.path.exists(raw_csv):
        print(f"❌ Error: Input file not found: {raw_csv}")
        return False
    
    if not os.path.exists(config_json):
        print(f"❌ Error: Config file not found: {config_json}")
        return False
    
    # 2. Validate environment variables
    if not validate_env_variables(no_import_data=no_import_data, skip_ingestion=skip_ingestion):
        print("\n❌ Pipeline aborted due to missing environment variables")
        return False
    
    # 3. Validate configuration structure
    logger.debug("="*80)
    logger.debug("VALIDATING CONFIGURATION")
    logger.debug("="*80)
    
    is_valid_structure, structure_errors = validate_config_structure(config_json)
    if not is_valid_structure:
        print("\n❌ Config structure validation failed:")
        for error in structure_errors:
            logger.debug(f"  • {error}")
        print("\n💡 Please fix the configuration file and try again.")
        return False
    
    logger.debug("✅ Config structure is valid")
    
    # 4. Validate aliases against CSV columns
    logger.debug("")
    logger.debug("Validating aliases against CSV columns...")
    is_valid, errors = validate_normalization_config(raw_csv, config_json)
    
    if not is_valid:
        print("\n❌ Configuration validation failed:")
        for error in errors:
            logger.debug(f"  • {error}")
        print("\n💡 Please fix the configuration file and try again.")
        return False
    
    logger.debug("")
    logger.debug("✅ All aliases are valid")
    
    return True



def run_command(cmd, description):
    """Run a command and handle errors, returning (success, duration)"""
    logger.debug(f"\n{'='*80}")
    logger.info(description)
    logger.debug(f"{'='*80}")
    logger.debug(f"Command: {' '.join(cmd)}\n")
    
    start_time = time.time()
    try:
        subprocess.run(cmd, check=True, capture_output=False, text=True)
        duration = time.time() - start_time
        print(f"{description} completed successfully! ({duration:.2f}s)")
        print("\n")
        return True, duration
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        print(f"\n❌ {description} failed after {duration:.2f}s with exit code {e.returncode}")
        return False, duration


def main():
    # Check for help flag first
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)  # Print the module docstring
        sys.exit(0)
    
    if len(sys.argv) < 3:
        print("❌ Error: Missing required arguments")
        print()
        print(__doc__)  # Print the module docstring
        sys.exit(1)
    
    raw_csv = sys.argv[1]
    config_json = sys.argv[2]
    
    # Parse flags (deduplication is always enabled now)
    should_consolidate = True  # Always consolidate
    no_import_data = '--no-import-data' in sys.argv
    skip_ingestion = '--skip-ingestion' in sys.argv
    
    # Validate all inputs (files, env vars, config)
    if not validate_inputs(raw_csv, config_json, no_import_data=no_import_data, skip_ingestion=skip_ingestion):
        sys.exit(1)
    
    # Define output paths - store in data/processed_data
    # Use input filename to create unique output files
    output_dir = Path("data/processed_data")
    output_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    
    # Extract base filename without extension
    input_basename = Path(raw_csv).stem  # e.g., "magento_products"
    normalized_csv = output_dir / f"normalized_{input_basename}.csv"
    post_normalized_csv = output_dir / f"post_normalized_{input_basename}.csv"
    tagged_csv = output_dir / f"tagged_{input_basename}.csv"
    products_csv = output_dir / f"unique_{input_basename}.csv"

    # Occasion config — always lives next to script dir
    occasion_config_json = SCRIPT_DIR / ".." / "config" / "occasion_config.json"

    # PostgreSQL import uses the full normalized CSV
    import_csv = normalized_csv
    
    logger.debug("="*80)
    logger.debug("STARTING DATA PROCESSING PIPELINE")
    logger.debug("="*80)
    logger.debug(f"Input:        {raw_csv}")
    logger.debug(f"Config:       {config_json}")
    logger.debug(f"Normalized:   {normalized_csv} (for PostgreSQL)")
    if should_consolidate:
        logger.debug(f"Products:     {products_csv} (for analytics)")
    logger.debug("Consolidate:  Always enabled")
    logger.debug(f"Import to DB: {'No (skipped)' if no_import_data else 'Yes'}")
    logger.debug("="*80)
    
    logger.info("\n📋 Executing Pipeline Steps...")
    
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

    # Step 2: Post-normalize (add sku_base, strip pass-through columns)
    post_normalize_cmd = [
        'python3',
        str(SCRIPT_DIR / 'post_normalize.py'),
        str(normalized_csv),
        str(post_normalized_csv),  # Write to separate file
        config_json
    ]

    success, duration = run_command(post_normalize_cmd, "Step 2: Post-normalize (add sku_base, enforce schema columns)")
    if not success:
        print("\n❌ Pipeline failed at post-normalization step")
        sys.exit(1)
    durations['post_normalize'] = duration

    # Step 3: Tag products with occasion keywords
    tag_cmd = [
        'python3',
        str(SCRIPT_DIR / 'tag_products.py'),
        str(post_normalized_csv),
        str(tagged_csv),
        str(occasion_config_json)
    ]

    success, duration = run_command(tag_cmd, "Step 3: Tag products with occasion keywords")
    if not success:
        print("\n❌ Pipeline failed at tag products step")
        sys.exit(1)
    durations['tag_products'] = duration

    # Step 4: Consolidate product variants
    if should_consolidate:
        consolidate_cmd = [
            'python3',
            str(SCRIPT_DIR / 'consolidate_product_variants.py'),
            str(tagged_csv),
            str(products_csv),
            config_json
        ]

        success, duration = run_command(consolidate_cmd, "Step 3: Consolidate product variants")
        if not success:
            print("\n❌ Pipeline failed at deduplication step")
            sys.exit(1)
        durations['consolidate'] = duration

    
    # Step 5: Database Import (if not skipped)
    # Note: import_normalized_data.py now handles category population automatically
    if not no_import_data:
        import_cmd = [
            'python3',
            str(SCRIPT_DIR / 'import_normalized_data.py'),
            str(import_csv)
        ]

        step_num = 5 if should_consolidate else 4
        success, duration = run_command(import_cmd, f"Step {step_num}: Import to PostgreSQL (Categories + Products)")
        if not success:
            print("\n❌ Pipeline failed at database import step")
            sys.exit(1)
        durations['import_db'] = duration
    
    # Step 6: Vector DB Ingestion — uses tagged CSV so tags land in ChromaDB metadata
    if not skip_ingestion:
        chroma_cmd = [
            'python3',
            str(SCRIPT_DIR / 'chromadb_ingestion.py'),
            str(tagged_csv)  # Pass tagged CSV so occasion tags are ingested
        ]

        # Calculate step number
        if no_import_data:
            chroma_step_num = 4
        else:
            chroma_step_num = 6

        success, duration = run_command(chroma_cmd, f"Step {chroma_step_num}: Ingest to Vector Database (with tags)")
        if not success:
            print("\n❌ Pipeline failed at vector database ingestion step")
            sys.exit(1)
        durations['chroma'] = duration
    else:
        print("\n Skipping vector database ingestion (--skip-vector-db flag)")
    
    # Schema Generation: Runs independently (only needs CSV, not DB)
    # Calculate step number based on what was skipped
    step_count = 3  # Base: normalize + consolidate + schema
    if not no_import_data:
        step_count += 1  # Add PostgreSQL import
    if not skip_ingestion:
        step_count += 1  # Add vector DB
    
    schema_step_num = step_count
    
    schema_cmd = [
        'python3',
        str(SCRIPT_DIR / 'csv_schema_generator.py'),
        str(tagged_csv)  # Pass tagged CSV so tags column is included in schema
    ]
    success, duration = run_command(schema_cmd, f"Step {schema_step_num}: Generate Attribute Schema")
    if not success:
        print("\n❌ Pipeline failed at schema generation step")
        sys.exit(1)
    durations['schema'] = duration
    
    # Summary
    logger.debug("-"*80)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY!")
    logger.debug("-"*80)
    logger.debug("-"*80)
    logger.debug("\n📁 Output Files:")
    logger.debug(f"  ✓ Normalized CSV: {normalized_csv}")
    logger.debug(f"  ✓ Tagged CSV:     {tagged_csv}")
    logger.debug(f"  ✓ Products CSV:   {products_csv}")
    logger.debug(f"  ✓ Schema JSON:    {SCRIPT_DIR / '..'/ '..'/ 'data' / 'schema' / 'catalog_ai_schema.json'}")
    
    logger.debug("\n📁 Output Files:")
    logger.debug("\n📋 Pipeline Steps Completed:")
    logger.debug(f"  1. ✅ Normalize raw CSV ({durations.get('normalize', 0):.2f}s)")
    logger.debug(f"  2. ✅ Post-normalize ({durations.get('post_normalize', 0):.2f}s)")
    logger.debug(f"  3. ✅ Tag products with occasion keywords ({durations.get('tag_products', 0):.2f}s)")
    logger.debug(f"  4. ✅ Consolidate product variants ({durations.get('consolidate', 0):.2f}s)")
    
    current_step = 3
    if not no_import_data:
        logger.debug(f"  {current_step}. ✅ Import to PostgreSQL ({durations.get('import_db', 0):.2f}s)")
        current_step += 1
        if not skip_ingestion:
            logger.debug(f"  {current_step}. ✅ Ingest to Vector Database ({durations.get('chroma', 0):.2f}s)")
            current_step += 1
    
    logger.debug(f"  {current_step}. ✅ Generate attribute schema ({durations.get('schema', 0):.2f}s)")
    
    total_time = sum(durations.values())
    logger.info(f"\n⏱️  Total execution time: {total_time:.2f}s")
    logger.debug("="*80)


if __name__ == '__main__':
    main()

