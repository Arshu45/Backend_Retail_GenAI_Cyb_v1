import os
import json
import time
from typing import Dict
from src.config.logger import get_logger
from src.config.settings import settings

_SCHEMA_CACHE: Dict[str, dict] = {}
logger = get_logger(__name__)

CATALOG_NAME = os.getenv("COLLECTION_NAME")
SCHEMA_FILE = f"{CATALOG_NAME}_schema.json"
SCHEMA_PATH = os.path.join(settings.schema_dir, SCHEMA_FILE)

def build_schema_path(catalog_name: str) -> str:
    """
    Build schema JSON file path for a given catalog.

    Args:
        catalog_name (str)

    Returns:
        str: schema file path
    """
    schema_file = f"{catalog_name}_schema.json"
    return os.path.join(settings.schema_dir, schema_file)

def load_attribute_schema_from_file(schema_path: str) -> dict:
    """
    Load attribute schema JSON from a given file path.

    Args:
        schema_path (str): Absolute or relative path to schema JSON file

    Returns:
        dict: Attribute schema

    Raises:
        FileNotFoundError
        json.JSONDecodeError
    """
    if not os.path.exists(schema_path):
        raise FileNotFoundError(
            f"Schema file not found: {schema_path}. "
            f"Run csv_schema_generator.py first."
        )

    logger.info("Loading schema from path: %s", schema_path)
    start_time = time.time()

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    logger.info(
        "Schema loaded in %.4f seconds. Total attributes: %d",
        time.time() - start_time,
        len(schema)
    )

    return schema


def get_attribute_schema(catalog_name: str) -> dict:
    """
    Get the cached attribute schema.

    The schema is loaded from disk only once and then cached in memory
    for subsequent calls to improve performance.

    Returns:
        dict: Cached attribute schema.
    """
    # 1️⃣ Return from cache if available
    if catalog_name in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[catalog_name]

    logger.info("Schema cache miss for catalog: %s", catalog_name)
    try:
        # 2️⃣ Build path dynamically
        schema_path = build_schema_path(catalog_name)
        # 3️⃣ Load schema from disk
        schema = load_attribute_schema_from_file(schema_path)
        # 3️⃣ Load schema from disk
        _SCHEMA_CACHE[catalog_name] = schema
        return schema
    except FileNotFoundError as e:
        logger.error(
            "Schema file not found for catalog '%s': %s",
            catalog_name,
            e
        )
        raise RuntimeError(
            f"Schema not configured for catalog '{catalog_name}'"
        ) from e

    except json.JSONDecodeError as e:
        logger.error(
            "Invalid schema JSON for catalog '%s': %s",
            catalog_name,
            e
        )
        raise RuntimeError(
            f"Invalid schema file for catalog '{catalog_name}'"
        ) from e

    except Exception as e:
        logger.exception(
            "Unexpected error while loading schema for catalog '%s'",
            catalog_name
        )
        raise RuntimeError(
            f"Failed to load schema for catalog '{catalog_name}'"
        ) from e