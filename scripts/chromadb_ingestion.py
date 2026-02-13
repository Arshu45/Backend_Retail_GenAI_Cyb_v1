import os
import json
import re
import ssl

import pandas as pd
import numpy as np
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv


# =========================================================
# LOAD ENV
# =========================================================
load_dotenv()

CSV_FILE_PATH = os.getenv("CSV_FILE_PATH")
DB_DIR = os.path.abspath(os.getenv("CHROMA_DB_DIR"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

DOCUMENT_COLUMNS = [
    col.strip()
    for col in os.getenv("DOCUMENT_COLUMNS", "").split(",")
    if col.strip()
]

print("📄 Document columns:", DOCUMENT_COLUMNS)
print("📂 CSV path:", CSV_FILE_PATH)
print("🧠 Embedding model:", EMBEDDING_MODEL)
print("📦 Collection:", COLLECTION_NAME)
print("🗄️ DB dir:", DB_DIR)


# ---- SSL FIX (Windows / Corp Network) ----
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["REQUESTS_CA_BUNDLE"] = ""

os.makedirs(DB_DIR, exist_ok=True)


# =========================================================
# LOAD CSV
# =========================================================
df = pd.read_csv(CSV_FILE_PATH).fillna("")


# =========================================================
# EMBEDDING FUNCTION
# =========================================================
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)


# =========================================================
# CHROMA CLIENT
# =========================================================
client = chromadb.PersistentClient(path=DB_DIR)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_function
)


# =========================================================
# NORMALIZATION
# =========================================================
def extract_age_bounds(age_val):
    """
    Converts age like:
    - '2-3Y' → (2, 3)
    - '6-7'  → (6, 7)
    - '4Y'   → (4, 4)
    - 4      → (4, 4)
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
        if col in DOCUMENT_COLUMNS:
            continue

        normalized = normalize_value(val)
        if normalized is None:
            continue

        # 🎯 AGE HANDLING
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
# INGEST
# =========================================================
documents = []
metadatas = []
ids = []

for _, row in df.iterrows():
    product_id = str(row["product_id"]).strip()

    documents.append(build_document(row))
    metadatas.append(build_metadata(row))
    ids.append(product_id)

collection.add(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

print(f"\n✅ Stored {collection.count()} vectors in ChromaDB")
