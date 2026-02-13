#!/usr/bin/env python3
"""
Configuration Validation Module

Validates normalization config against input CSV to catch errors early.
"""

import json
import pandas as pd
from typing import Tuple, List


def validate_normalization_config(csv_path: str, config_path: str) -> Tuple[bool, List[str]]:
    """
    Validate that aliases in normalization config match columns in CSV.
    
    Args:
        csv_path: Path to input CSV file
        config_path: Path to normalization config JSON file
    
    Returns:
        tuple: (is_valid, error_messages)
            - is_valid: True if all validations pass
            - error_messages: List of error messages (empty if valid)
    
    Example:
        is_valid, errors = validate_normalization_config('data.csv', 'config.json')
        if not is_valid:
            for error in errors:
                print(error)
    """
    
    errors = []
    
    # Load config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        errors.append(f"Failed to load config file: {e}")
        return False, errors
    
    # Read CSV headers only (first row)
    try:
        df_headers = pd.read_csv(csv_path, nrows=0)
        csv_columns = set(col.lower().strip() for col in df_headers.columns)
    except Exception as e:
        errors.append(f"Failed to read CSV file: {e}")
        return False, errors
    
    # Validate each field in the schema
    schema = config.get('output_schema', [])
    
    warnings = []
    critical_fields = ['product_id', 'sku', 'title', 'price']  # Fields that MUST exist
    
    for field in schema:
        field_name = field.get('name')
        aliases = field.get('aliases', [])
        
        if not aliases:
            # Skip fields with no aliases (derived fields, etc.)
            continue
        
        # Check if at least one alias exists in CSV columns (case-insensitive)
        aliases_lower = [alias.lower().strip() for alias in aliases]
        matching_aliases = [alias for alias in aliases_lower if alias in csv_columns]
        
        if not matching_aliases:
            # None of the aliases exist in CSV
            if field_name in critical_fields:
                # Critical field - this is an error
                errors.append(
                    f"CRITICAL: Field '{field_name}' is required but none of the aliases {aliases} exist in CSV.\n"
                    f"    Available columns: {', '.join(sorted(csv_columns)[:15])}..."
                )
            else:
                # Optional field - just a warning
                warnings.append(
                    f"Field '{field_name}': None of the aliases {aliases} found in CSV (will be empty)"
                )
    
    # Print warnings if any
    if warnings:
        print("\n⚠️  Optional fields not found in CSV (will be empty):")
        for warning in warnings:
            print(f"  • {warning}")
    
    # Return validation result
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_config_structure(config_path: str) -> Tuple[bool, List[str]]:
    """
    Validate the structure of the config file itself.
    
    Args:
        config_path: Path to normalization config JSON file
    
    Returns:
        tuple: (is_valid, error_messages)
    """
    
    errors = []
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON format: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"Failed to load config file: {e}")
        return False, errors
    
    # Check required top-level keys
    if 'output_schema' not in config:
        errors.append("Missing required key: 'output_schema'")
    
    # Validate schema structure
    schema = config.get('output_schema', [])
    
    if not isinstance(schema, list):
        errors.append("'output_schema' must be a list")
        return False, errors
    
    for i, field in enumerate(schema):
        if not isinstance(field, dict):
            errors.append(f"Schema item {i} must be a dictionary")
            continue
        
        if 'name' not in field:
            errors.append(f"Schema item {i} missing required key: 'name'")
        
        if 'aliases' not in field:
            errors.append(f"Schema item {i} ('{field.get('name', 'unknown')}') missing required key: 'aliases'")
        
        if 'aliases' in field and not isinstance(field['aliases'], list):
            errors.append(f"Field '{field.get('name')}': 'aliases' must be a list")
    
    is_valid = len(errors) == 0
    return is_valid, errors


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python validate_config.py <csv_file> <config_file>")
        print("\nExample:")
        print("  python validate_config.py data/input.csv scripts/config/normalization_config.json")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    config_file = sys.argv[2]
    
    print("="*80)
    print("CONFIGURATION VALIDATION")
    print("="*80)
    print(f"CSV File:    {csv_file}")
    print(f"Config File: {config_file}")
    print("="*80)
    
    # Validate config structure
    print("\n🔍 Validating config structure...")
    is_valid_structure, structure_errors = validate_config_structure(config_file)
    
    if not is_valid_structure:
        print("\n❌ Config structure validation failed:")
        for error in structure_errors:
            print(f"  • {error}")
        sys.exit(1)
    
    print("✅ Config structure is valid")
    
    # Validate against CSV
    print("\n🔍 Validating aliases against CSV columns...")
    is_valid, errors = validate_normalization_config(csv_file, config_file)
    
    if not is_valid:
        print("\n❌ Configuration validation failed:")
        for error in errors:
            print(f"  • {error}")
        print("\n💡 Please fix the configuration file and try again.")
        sys.exit(1)
    
    print("✅ All aliases are valid")
    print("\n" + "="*80)
    print("✅ VALIDATION PASSED")
    print("="*80)
