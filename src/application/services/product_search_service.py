"""Product search service using ChromaDB semantic search."""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from src.infrastructure.llm.groq_client import get_groq_client
from src.infrastructure.llm.prompts import EXTRACT_ATTRIBUTES_PROMPT
from src.config.settings import settings
from src.config.logging_config import get_logger

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
        """
        try:
            return self.groq_client.extract_json(
                system_prompt=EXTRACT_ATTRIBUTES_PROMPT,
                user_query=user_query
            )
        except Exception as e:
            logger.error(f"Error extracting attributes: {str(e)}")
            return {}
    
    def build_chroma_filter(self, raw_filters: dict) -> dict:
        """
        Convert extracted filters to Chroma-compatible where clause.
        Handles age ranges and other filter types.
        Validates that numeric values are not None before creating filters.
        """
        filters = []
        
        for key, value in raw_filters.items():
            if value is None:
                continue
            
            # Age handling
            if key == "age":
                if "$gte" in value and "$lte" in value:
                    min_age = value["$gte"]
                    max_age = value["$lte"]
                    # Validate that values are not None and are numeric
                    if min_age is not None and max_age is not None and isinstance(min_age, (int, float)) and isinstance(max_age, (int, float)):
                        filters.append({"age_max": {"$lte": max_age}})
                        filters.append({"age_min": {"$gte": min_age}})
                elif "$eq" in value:
                    age = value["$eq"]
                    # Validate age is not None and is numeric
                    if age is not None and isinstance(age, (int, float)):
                        filters.append({"age_min": {"$lte": age}})
                        filters.append({"age_max": {"$gte": age}})
                elif "$lt" in value:
                    age_lt = value["$lt"]
                    # Validate age_lt is not None and is numeric
                    if age_lt is not None and isinstance(age_lt, (int, float)):
                        filters.append({"age_min": {"$lt": age_lt}})
                elif "$gt" in value:
                    age_gt = value["$gt"]
                    # Validate age_gt is not None and is numeric
                    if age_gt is not None and isinstance(age_gt, (int, float)):
                        filters.append({"age_max": {"$gt": age_gt}})
                continue
            
            # Range filters (e.g., price: {"$lte": 5000})
            if isinstance(value, dict):
                for op, num in value.items():
                    # Validate that num is not None and is numeric
                    if num is not None and isinstance(num, (int, float)):
                        filters.append({key: {op: num}})
            else:
                filters.append({key: self.normalize_filter_value(value)})
        
        # Build final Chroma where clause
        if not filters:
            return {}
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}
    
    def search_products(
        self, 
        query: str, 
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search products using semantic search with attribute filtering.
        
        Args:
            query: User search query
            n_results: Number of results to return
            
        Returns:
            List of product dictionaries with document and metadata
        """
        try:
            # Step 1: Rewrite query for semantic search
            rewritten_query = self.rewrite_query(query)
            
            # Step 2: Extract attributes using LLM
            raw_filters = self.extract_attributes(query)
            logger.info(f"Extracted filters: {raw_filters}")
            
            # Step 3: Build Chroma filter
            where_filter = self.build_chroma_filter(raw_filters)
            logger.info(f"Chroma filter: {json.dumps(where_filter, indent=2)}")
            
            # Step 4: Perform vector search
            results = self.collection.query(
                query_texts=[rewritten_query],
                n_results=n_results,
                where=where_filter if where_filter else None
            )
            
            # Step 5: Format results
            products = []
            if results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    product = {
                        "document": doc,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {},
                        "id": results["ids"][0][i] if results.get("ids") and results["ids"][0] else None,
                        "distance": results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                    }
                    products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            raise
