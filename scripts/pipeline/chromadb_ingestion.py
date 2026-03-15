import os
import sys
import pandas as pd
import json
import chromadb
from chromadb.utils import embedding_functions
import re
import ssl
import numpy as np
from dotenv import load_dotenv
from logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Module-level config (loaded at import time)
load_dotenv()

DOCUMENT_COLUMNS = [
    col.strip()
    for col in os.getenv("DOCUMENT_COLUMNS", "").split(",")
    if col.strip()
]

def print_usage():
    print("""
Usage: python chromadb_ingestion.py <csv_file_path>

Arguments:
  csv_file_path   Path to the normalized CSV file to ingest into ChromaDB

Environment Variables (set in .env):
  CHROMA_DB_DIR      Directory to store ChromaDB data
  COLLECTION_NAME    Name of the ChromaDB collection
  EMBEDDING_MODEL    SentenceTransformer model name (e.g. all-MiniLM-L6-v2)
  DOCUMENT_COLUMNS   Comma-separated list of columns to use as document text
  CSV_FILE_PATH      (Optional) Fallback CSV path if not passed as argument

Examples:
  python chromadb_ingestion.py data/processed_data/normalized_products.csv
  python chromadb_ingestion.py data/processed_data/normalized_products.csv --help
""")


# =========================================================
# NORMALIZATION
# =========================================================

def extract_age_bounds(age_val):
    """
    Converts age like:
    - '2-3Y' → (2, 3)
    - '6-7' → (6, 7)
    - '4Y' → (4, 4)
    - 4 → (4, 4)
    """
    if age_val is None:
        return None, None

    if isinstance(age_val, (int, float)):
        age = int(age_val)
        return age, age

    if isinstance(age_val, str):
        age_val = age_val.lower().strip()

        # Range: 2-3y, 6 - 7
        match = re.match(r"(\d+)\s*-\s*(\d+)", age_val)
        if match:
            return int(match.group(1)), int(match.group(2))

        # Single age: 4y, 5
        match = re.match(r"(\d+)", age_val)
        if match:
            age = int(match.group(1))
            return age, age

    return None, None

def normalize_value(val):
    if pd.isna(val):
        return None

    if isinstance(val, np.generic):
        val = val.item()

    if isinstance(val, str):
        return val.strip().lower()

    if isinstance(val, (int, float, bool)):
        return val

    return str(val).strip().lower()

# =========================================================
# BUILD DOCUMENT (ENV COLUMNS ONLY)
# =========================================================
def build_document(row):
    row_dict = row.to_dict()
    doc = {}

    for col in DOCUMENT_COLUMNS:
        val = row_dict.get(col)

        if pd.isna(val):
            continue

        if isinstance(val, np.generic):
            val = val.item()

        doc[col] = val

    return json.dumps(doc, ensure_ascii=False)

# =========================================================
# BUILD METADATA (ALL OTHER COLUMNS)
# =========================================================
def build_metadata_before_age(row):
    row_dict = row.to_dict()
    metadata = {}

    for col, val in row_dict.items():
        if col in DOCUMENT_COLUMNS:
            continue

        normalized = normalize_value(val)
        if normalized is not None:
            metadata[col] = normalized

    return metadata

def build_metadata(row):
    row_dict = row.to_dict()
    metadata = {}

    age_min = age_max = None

    for col, val in row_dict.items():
        # Skip document columns EXCEPT title and description (we want those in metadata too for display)
        if col in DOCUMENT_COLUMNS:
            continue

        # TAGS HANDLING — split comma-separated string into a native list
        # Enables ChromaDB $in filter: { "tags": { "$in": ["birthday"] } }
        if col == "tags":
            if val is not None and str(val).strip() not in ("", "nan"):
                tag_list = [t.strip() for t in str(val).split(",") if t.strip()]
                if tag_list:
                    metadata["tags"] = tag_list  # e.g. ["birthday", "festival"]
            continue

        normalized = normalize_value(val)
        if normalized is None:
            continue

        # AGE HANDLING
        if col.lower() == "age_group":
            age_min, age_max = extract_age_bounds(val)
            metadata["age_group"] = normalized
            continue

        metadata[col] = normalized

    # ✅ Add numeric age bounds (ONLY if present)
    if age_min is not None and age_max is not None:
        metadata["age_min"] = age_min
        metadata["age_max"] = age_max

    return metadata


# =========================================================
# MAIN
# =========================================================
def main():
    # =========================================================
    # LOAD ENV & COMMAND-LINE ARGS
    # =========================================================
    load_dotenv()

    if '--help' in sys.argv or '-h' in sys.argv:
        print_usage()
        sys.exit(0)

    # Accept CSV file path as command-line argument (fallback to .env)
    csv_file_path = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CSV_FILE_PATH")
    db_dir = os.path.abspath(os.getenv("CHROMA_DB_DIR"))
    collection_name = os.getenv("COLLECTION_NAME")
    embedding_model = os.getenv("EMBEDDING_MODEL")

    document_columns = [
        col.strip()
        for col in os.getenv("DOCUMENT_COLUMNS", "").split(",")
        if col.strip()
    ]

    if not csv_file_path:
        print("❌ Error: CSV file path not provided")
        print_usage()
        sys.exit(1)

    logger.debug(f"Document columns: {document_columns}")
    logger.debug(f"CSV path: {csv_file_path}")
    logger.debug(f"Embedding model: {embedding_model}")
    logger.debug(f"Collection: {collection_name}")
    logger.debug(f"DB dir: {db_dir}")

    # ---- SSL FIX (Windows / Corp Network) ----
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ["REQUESTS_CA_BUNDLE"] = ""

    os.makedirs(db_dir, exist_ok=True)

    # =========================================================
    # LOAD CSV
    # =========================================================
    # df = pd.read_csv(csv_file_path).fillna("")
    df = pd.read_csv(csv_file_path, encoding='utf-8-sig', low_memory=False, skip_blank_lines=True)
    df.columns = df.columns.str.strip().str.lower()
    logger.debug(f"Detected columns: {df.columns.tolist()}")

    # =========================================================
    # EMBEDDING FUNCTION
    # =========================================================
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model
    )

    # =========================================================
    # CHROMA CLIENT
    # =========================================================
    client = chromadb.PersistentClient(path=db_dir)

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function
    )

    # =========================================================
    # INGEST (WITH BATCHING)
    # =========================================================
    documents, metadatas, ids = [], [], []

    # 1. Build the lists
    for _, row in df.iterrows():
        product_id = str(row["product_id"]).strip()
        documents.append(build_document(row))
        metadatas.append(build_metadata(row))
        ids.append(product_id)

    # 2. Upload in batches
    BATCH_SIZE = 5000  # Staying safely under the 5461 limit
    total_records = len(ids)

    logger.debug(f"Starting ingestion of {total_records} records...")

    for i in range(0, total_records, BATCH_SIZE):
        batch_ids = ids[i : i + BATCH_SIZE]
        batch_docs = documents[i : i + BATCH_SIZE]
        batch_metas = metadatas[i : i + BATCH_SIZE]

        collection.add(
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids
        )
        logger.debug(f"Progress: {min(i + BATCH_SIZE, total_records)} / {total_records} records stored.")

    logger.debug(f"Finished! Stored total {collection.count()} vectors in ChromaDB.")


if __name__ == '__main__':
    main()