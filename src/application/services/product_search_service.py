"""Product search service using ChromaDB semantic search."""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from src.infrastructure.llm.groq_client import get_groq_client
from src.infrastructure.prompts.prompts_loader import get_prompt
from src.config.settings import settings
from src.config.logger import get_logger
from src.config.csv_schema_loader import get_attribute_schema
from src.utils.post_process_vector_results import (
    group_by_sku_base,
    convert_to_chroma_result_shape
)


logger = get_logger(__name__)


class ProductSearchService:
    """Service for product retrieval using ChromaDB semantic search."""
    
    def __init__(self):
        """Initialize ChromaDB client and embedding function."""
        try:
            # Initialize embedding function
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model
            )
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path=settings.chroma_db_dir)
            self.collection = self.client.get_or_create_collection(
                name=settings.collection_name,
                embedding_function=self.embedding_function
            )
            
            # Initialize Groq client for attribute extraction
            self.groq_client = get_groq_client()

            CATALOG_NAME = os.getenv("COLLECTION_NAME")
            self.attribute_schema = get_attribute_schema(CATALOG_NAME)

            # ✅ Load from env with safe defaults
            self.default_key_features = [
                f.strip()
                for f in os.getenv("DEFAULT_KEY_FEATURES", "brand,color,size").split(",")
                if f.strip()
            ]

            self.max_key_features = int(os.getenv("MAX_KEY_FEATURES", 3))

            logger.info(
                f"Key feature config → defaults={self.default_key_features}, "
                f"max={self.max_key_features}"
            )
            
            logger.info(f"ProductSearchService initialized: {self.collection.count()} vectors in collection")
            
        except Exception as e:
            logger.error(f"Failed to initialize ProductSearchService: {str(e)}")
            raise
    
    def normalize_filter_value(self, val):
        """Normalize filter value (must match ingest logic)."""
        if isinstance(val, str):
            return val.strip().lower()
        return val
    
    def rewrite_query(self, user_query: str) -> str:
        """
        Rewrite query for semantic search optimization.
        Currently returns query as-is, can be enhanced with LLM.
        """
        return user_query.strip()
    
    def extract_attributes(self, user_query: str) -> dict:
        """
        Extract attributes from user query for filtering.
        Uses Groq LLM to extract structured filters.

        Enum attributes with more values than MAX_ENUM_VALUES_IN_PROMPT are
        trimmed before being sent to the LLM to avoid token bloat.
        The full value list is still kept in self.attribute_schema for
        validation in build_chroma_filter — trimming only affects the prompt.
        """
        try:
            CATALOG_NAME = os.getenv("COLLECTION_NAME")
            ATTRIBUTE_SCHEMA = get_attribute_schema(CATALOG_NAME)
            # logger.info(f"ATTRIBUTE_SCHEMA: {ATTRIBUTE_SCHEMA} ")

            # Get EXCLUDED_ATTR_EXTRACTION_FIELDS from config (comma-separated)
            excluded_config = os.getenv(
                "EXCLUDED_ATTR_EXTRACTION_FIELDS",
                "product_id,sku_base"   # fallback default
            )

            excluded_fields = {
                field.strip()
                for field in excluded_config.split(",")
                if field.strip()
            }


            # Filter schema before sending to LLM
            filtered_schema = {
                k: v for k, v in ATTRIBUTE_SCHEMA.items()
                if k not in excluded_fields
            }

            # logger.info(f"Filtered ATTRIBUTE_SCHEMA: {filtered_schema}")

            # -------------------------------------------------------
            # TRIM LARGE ENUM VALUES FOR PROMPT
            # -------------------------------------------------------
            # For enum attributes with many values (e.g. color with 80+ entries),
            # sending the full list to the LLM inflates token usage significantly.
            # We trim to MAX_ENUM_VALUES_IN_PROMPT entries for the prompt only.
            # The full list remains in self.attribute_schema for hard validation
            # in build_chroma_filter — so the guard still catches invalid values
            # even if they weren't in the trimmed sample shown to the LLM.
            MAX_ENUM_VALUES_IN_PROMPT = int(os.getenv("MAX_ENUM_VALUES_IN_PROMPT", 30))

            filtered_schema_for_prompt = {}
            for k, v in filtered_schema.items():
                if v.get("type") == "enum":
                    values = v["rules"].get("values", [])
                    if len(values) > MAX_ENUM_VALUES_IN_PROMPT:
                        trimmed = dict(v)
                        trimmed["rules"] = {
                            "values": values[:MAX_ENUM_VALUES_IN_PROMPT]
                        }
                        filtered_schema_for_prompt[k] = trimmed
                        logger.debug(
                            f"Trimmed enum '{k}' from {len(values)} "
                            f"to {MAX_ENUM_VALUES_IN_PROMPT} values for prompt"
                        )
                    else:
                        filtered_schema_for_prompt[k] = v
                else:
                    filtered_schema_for_prompt[k] = v

            # Load occasion names dynamically from occasion_config.json
            # so adding a new occasion only requires editing the config file.
            occasion_names = self._load_occasion_names()

            return self.groq_client.extract_json(
                system_prompt=get_prompt("EXTRACT_ATTRIBUTES_PROMPT").format(
                    attribute_schema=json.dumps(filtered_schema_for_prompt, indent=2),
                    occasion_names=occasion_names,
                ),
                user_query=user_query
            )
        except Exception as e:
            logger.error(f"Error extracting attributes: {str(e)})")
            return {}

    def _load_occasion_names(self) -> str:
        """
        Read occasion names from occasion_config.json and return them
        as a comma-separated string for prompt injection.

        Returns:
            str: e.g. "birthday, wedding, anniversary, baby_shower, festival"
                 or "birthday" if only one occasion is configured.
                 Falls back to empty string on error.
        """
        config_path = os.path.join(
            os.path.dirname(__file__),           # src/application/services/
            "..", "..", "..",                    # project root
            "scripts", "config", "occasion_config.json"
        )
        config_path = os.path.normpath(config_path)
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            names = list(config.get("occasions", {}).keys())
            result = ", ".join(names)
            logger.debug(f"Loaded occasion names from config: {result}")
            return result
        except Exception as e:
            logger.warning(f"Could not load occasion_config.json: {e}. Occasion tags disabled.")
            return ""

    
    def build_chroma_filter(self, raw_filters: dict) -> dict:
        """
        Convert extracted filters to Chroma-compatible where clause.
        Handles age ranges, tags ($contains), enum validation, and numeric ranges.
        Validates enum values dynamically from schema — no hardcoding.
        Validates that numeric values are not None before creating filters.
        """
        filters = []

        # Build enum validator dynamically from loaded schema.
        # Only attributes with type "enum" and a "values" list are included.
        # Example: {"color": {"black", "red", ...}, "size": {"s", "m", "l", ...}}
        enum_validators = {
            k: set(v["rules"]["values"])
            for k, v in self.attribute_schema.items()
            if v.get("type") == "enum" and "values" in v.get("rules", {})
        }

        for key, value in raw_filters.items():
            if value is None:
                continue

            # -------------------------------------------------------
            # AGE HANDLING
            # -------------------------------------------------------
            if key == "age":
                if "$gte" in value and "$lte" in value:
                    min_age = value["$gte"]
                    max_age = value["$lte"]
                    if min_age is not None and max_age is not None and isinstance(min_age, (int, float)) and isinstance(max_age, (int, float)):
                        filters.append({"age_max": {"$lte": max_age}})
                        filters.append({"age_min": {"$gte": min_age}})
                elif "$eq" in value:
                    age = value["$eq"]
                    if age is not None and isinstance(age, (int, float)):
                        filters.append({"age_min": {"$lte": age}})
                        filters.append({"age_max": {"$gte": age}})
                elif "$lt" in value:
                    age_lt = value["$lt"]
                    if age_lt is not None and isinstance(age_lt, (int, float)):
                        filters.append({"age_min": {"$lt": age_lt}})
                elif "$gt" in value:
                    age_gt = value["$gt"]
                    if age_gt is not None and isinstance(age_gt, (int, float)):
                        filters.append({"age_max": {"$gt": age_gt}})
                continue

            # -------------------------------------------------------
            # TAGS HANDLING — occasion-based search
            # Validates tag value against known occasions from config.
            # Prevents non-occasion values (e.g. "sandals") from being
            # used as a tags filter.
            # -------------------------------------------------------
            if key == "tags":
                tag_value = str(value).strip().lower()
                known_occasions = self._load_occasion_names()  # e.g. "birthday, wedding, festival"
                valid_occasions = {o.strip() for o in known_occasions.split(",") if o.strip()}
                if tag_value and tag_value in valid_occasions:
                    filters.append({"tags": {"$contains": tag_value}})
                else:
                    logger.warning(f"Dropping invalid tag filter: tags='{tag_value}' not in known occasions {valid_occasions}")
                continue

            # -------------------------------------------------------
            # ENUM VALIDATION
            # Dynamically checks extracted value against schema-defined
            # allowed values. Drops the filter if the value is invalid
            # (e.g. LLM maps "sandals" → color) rather than crashing
            # or returning zero results.
            # -------------------------------------------------------
            if key in enum_validators:
                if isinstance(value, str) and value.strip().lower() not in enum_validators[key]:
                    logger.warning(f"Dropping invalid enum filter: {key}='{value}' not in schema values {enum_validators[key]}")
                    continue  # drop — let semantic search handle it freely

            # -------------------------------------------------------
            # RANGE FILTERS (e.g. price: {"$lte": 5000, "$gte": 100})
            # -------------------------------------------------------
            if isinstance(value, dict):
                for op, num in value.items():
                    if num is not None and isinstance(num, (int, float)):
                        filters.append({key: {op: num}})
            else:
                # Scalar filter (e.g. color: "red", size: "m")
                filters.append({key: self.normalize_filter_value(value)})

            # -------------------------------------------------------
            # Build final Chroma where clause
            # -------------------------------------------------------
        if not filters:
            return {}
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}

    def build_key_features(
        self,
        metadata: dict,
        metadata_filters: dict
    ) -> list[str]:
        """
        Build UI key features based on metadata filters.
        Priority:
        1. Latest user-applied filters
        2. Fallback defaults from env
        """

        key_features = []
        EXCLUDED_KEY_FEATURES = {
                col.strip().lower()
                for col in os.getenv("EXCLUDED_KEY_FEATURES", "").split(",")
                if col.strip()
            }

        # 1️⃣ Dynamic: latest metadata filters first
        for attr in reversed(metadata_filters.keys()):
            if attr not in self.attribute_schema:
                continue

            if attr in EXCLUDED_KEY_FEATURES:
                continue

            value = metadata.get(attr)
            if value:
                key_features.append(str(value))

            if len(key_features) == self.max_key_features:
                return key_features

        # 2️⃣ Fallback: defaults from env
        for attr in self.default_key_features:
            if attr in metadata_filters:
                continue

            value = metadata.get(attr)
            if value:
                key_features.append(str(value))

            if len(key_features) == self.max_key_features:
                break

        return key_features

    def search_products(
        self, 
        query: str, 
        n_results: int = 5
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        """
        Search products using semantic search with attribute filtering.
        
        Args:
            query: User search query
            n_results: Number of results to return
            
        Returns:
            List of product dictionaries with document and metadata
        """
        start_total = time.perf_counter()   # 🔥 TOTAL TIMER
        try:
            # -----------------------------
            # Step 1: Rewrite Query (currently we are not doing query rewriting, but in future if need, we can do it)
            # -----------------------------
            # Normalize or enhance the user's search query before semantic search.
            start_time_query_rewrite = time.perf_counter()
            rewritten_query = self.rewrite_query(query)
            end_time_query_rewrite = time.perf_counter()

            # -----------------------------
            # Step 2: Extract Attributes (LLM Call)
            # -----------------------------
            # Use LLM to extract structured filters from the natural language query.
            # Example:
            # "red t-shirt under 500 for 5 year old"
            # →
            # {
            #   "color": "red",
            #   "price": {"$lte": 500}
            # }
            # These filters will later be converted into ChromaDB metadata filters.
            raw_filters = self.extract_attributes(query)
            end_time_attr_extract = time.perf_counter()
            logger.info(f"Extracted filters: {raw_filters}")

            # ── ATTRIBUTE COUNT GATE ───────────────────────────────
            # Only proceed to vector search if enough attributes were
            # extracted. Otherwise return need_more_info so the agent
            # asks the user for more details.
            MIN_ATTRIBUTES = int(os.getenv("MIN_ATTRIBUTES_TO_SEARCH", "2"))
            attr_count = len([v for v in raw_filters.values() if v is not None])

            if attr_count < MIN_ATTRIBUTES:
                logger.info(
                    f"[Attribute Gate] {attr_count} attribute(s) extracted "
                    f"— need at least {MIN_ATTRIBUTES}. Returning need_more_info."
                )
                return {
                    "need_more_info": True,
                    "attr_count": attr_count,
                    "extracted_so_far": raw_filters,
                }
            
            # -----------------------------
            # Step 3: Build Chroma Filter
            # -----------------------------
            # Convert extracted structured attributes into a ChromaDB-compatible
            # `where` filter clause.
            # Handles:
            # - Numeric ranges (price)
            # - Equality filters (color, brand, size)
            # Output format example:
            # {
            #   "$and": [
            #       {"color": "red"},
            #       {"price": {"$lte": 500}}
            #   ]
            # }
            where_filter = self.build_chroma_filter(raw_filters)
            end_time_build_filter = time.perf_counter()
            logger.info(f"Chroma filter: {json.dumps(where_filter, indent=2)}")

            logger.info("🔍 Chroma query text: %s", rewritten_query)
            
            # -----------------------------
            # Step 4: Vector Search (DB Call)
            # -----------------------------
            # Perform semantic similarity search using embeddings.
            # Combines:
            #   1. Vector similarity search (semantic meaning)
            #   2. Metadata filtering (structured constraints)
            # Returns:
            #   - documents
            #   - metadata
            #   - distances (similarity scores)
            results = self.collection.query(
                query_texts=[rewritten_query],
                n_results=n_results,
                where=where_filter if where_filter else None
            )
            end_time_chroma_query = time.perf_counter()

            # -----------------------------
            # Step 5: SKU Grouping
            # -----------------------------
            # Group product variants by `sku_base` to avoid returning multiple sizes/colors of the same product separately.
            # Keeps only the best matching variant per product group.
            # Improves UI clarity by reducing duplicate product listings.
            final_products = group_by_sku_base(
                docs=results["documents"][0],
                metadatas=results["metadatas"][0],
                distances=results["distances"][0],
                top_n=5
            )
            end_time_sku_grouping = time.perf_counter()
            #print(json.dumps(final_products, indent=2, ensure_ascii=False))
            
            # -----------------------------
            # Step 6: Convert Result Shape
            # -----------------------------
            # Convert grouped results back into ChromaDB-like structure.
            # This ensures consistent downstream formatting logic, even after custom SKU grouping.
            results = convert_to_chroma_result_shape(final_products)
            end_time_chroma_conversion = time.perf_counter()

            # -----------------------------
            # Step 7: Format Final Response
            # -----------------------------
            # Build final API-ready response format.
            # Each product includes:
            # - document 
            # - metadata (all structured attributes)
            # - id (vector id)
            # - distance (similarity score)
            # - key_features (UI-highlight attributes)
            #
            # key_features are dynamically built based on:
            #   1. User-applied filters (highest priority)
            #   2. Default fallback attributes (from env config)
            products = []
            
            if results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    product = {
                        "document": doc,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {},
                        "id": results["ids"][0][i] if results.get("ids") and results["ids"][0] else None,
                        "distance": results["distances"][0][i] if results.get("distances") and results["distances"][0] else None,
                        
                        # ✅ ADD THIS
                        "key_features": self.build_key_features(
                            metadata=metadata,
                            metadata_filters=raw_filters
                        )
                    }
                    products.append(product)
            end_time_response_formating = time.perf_counter()

            # -----------------------------
            # 🔥 Timing Breakdown Log
            # -----------------------------
            logger.info(
                f"""
    Search Timing Breakdown:
    Rewrite Query        : {(end_time_query_rewrite - start_time_query_rewrite):.4f}s
    LLM Attribute Extraction : {(end_time_attr_extract - end_time_query_rewrite):.4f}s
    Build Metadata Filter     : {(end_time_build_filter - end_time_attr_extract):.4f}s
    Vector Search         : {(end_time_chroma_query - end_time_build_filter):.4f}s
    SKU Grouping         : {(end_time_sku_grouping - end_time_chroma_query):.4f}s
    Chroma Conversion     : {(end_time_chroma_conversion - end_time_sku_grouping):.4f}s
    Response Formatting  : {(end_time_response_formating - end_time_chroma_conversion):.4f}s
    -------------------------------------
    TOTAL SEARCH TIME    : {(end_time_response_formating - start_total):.4f}s
    """
            )
            #print(json.dumps(products, indent=2, ensure_ascii=False))
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            raise