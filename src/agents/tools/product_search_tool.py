"""Product search tool for LangChain agents."""

import os
import json
import time
from langchain_core.tools import tool
from src.config.logger import get_logger
from src.config.csv_schema_loader import get_attribute_schema

logger = get_logger(__name__)


def create_product_search_tool(product_service):
    """
    Create product search tool for the agent.
    
    Args:
        product_service: ProductSearchService instance
        
    Returns:
        LangChain tool for product search
    """
    
    @tool
    def search_products(query: str) -> str:
        """
        Search for products in the e-commerce catalog using semantic search.
        Use this tool when the user is asking about products, items, clothing, dresses, or wants to buy something.
        
        Args:
            query: Product search query (e.g., "maroon dress for birthday", "dresses under 5000")
            
        Returns:
            JSON string with product search results including titles, prices, and metadata
        """
        try:
            tool_start_time = time.perf_counter()
            result = product_service.search_products(query, n_results=15)
            time_after_search = time.perf_counter()

            # ── NEED MORE INFO GATE ────────────────────────────────
            # product_search_service returns a dict with need_more_info=True
            # when fewer than MIN_ATTRIBUTES_TO_SEARCH were extracted.
            # The agent sees this and asks the user for more details
            # instead of returning irrelevant products.
            if isinstance(result, dict) and result.get("need_more_info"):
                attr_count = result.get("attr_count", 0)
                extracted = result.get("extracted_so_far", {})
                logger.info(
                    f"[TOOL] need_more_info=True | "
                    f"attr_count={attr_count} | extracted={extracted}"
                )
                return json.dumps({
                    "found": False,
                    "need_more_info": True,
                    "attr_count": attr_count,
                    "extracted_so_far": extracted,
                    "message": (
                        "Search was NOT performed. "
                        "Do NOT say 'no products found' or 'could not find'. "
                        "Instead ask the user for more details naturally. "
                        "First ask what type of product they are looking for "
                        "(e.g., dresses, accessories, bags), then about color, size, or budget."
                    )
                })
            # ── END NEED MORE INFO GATE ────────────────────────────

            # From here, result is a list of products (normal flow)
            products = result

            if not products:
                total_tool = time.perf_counter() - tool_start_time
                logger.info(f"[TOOL] Total Tool Time: {total_tool:.4f}s")
                return json.dumps({
                    "found": False,
                    "message": f"No products found matching '{query}'",
                    "products": []
                })
            
            # Format products for agent
            CATALOG_NAME = os.getenv("COLLECTION_NAME")
            ATTRIBUTE_SCHEMA = get_attribute_schema(CATALOG_NAME)
            formatted_products = []
            DOCUMENT_COLUMNS = {
                col.strip().lower()
                for col in os.getenv("DOCUMENT_COLUMNS", "").split(",")
                if col.strip()
            }
            for product in products:
                try:
                    doc = json.loads(product.get("document", "{}"))
                    metadata = product.get("metadata", {})
                    
                    formatted_product = {}
                    # 🔹 Document fields
                    for field in DOCUMENT_COLUMNS:
                        formatted_product[field] = doc.get(field, "")

                    # 🔹 Metadata fields
                    for attr_name, attr_schema in ATTRIBUTE_SCHEMA.items():
                        formatted_product[attr_name] = metadata.get(attr_name, "")

                    # 🔹 Key features (per product)
                    formatted_product["key_features"] = product.get("key_features", [])

                    formatted_products.append(formatted_product)

                except Exception as e:
                    logger.warning(f"Error formatting product: {e}")
                    continue
            time_after_format = time.perf_counter()

            logger.info(f"""
    [TOOL Timing]
    Search Call Time : {(time_after_search - tool_start_time):.4f}s
    Formatting Time  : {(time_after_format - time_after_search):.4f}s
    -----------------------------------------------------------
    Total Tool Time  : {(time_after_format - tool_start_time):.4f}s
    """)
            return json.dumps({
                "found": True,
                "count": len(formatted_products),
                "products": formatted_products
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Error in search_products tool: {str(e)}")
            return json.dumps({
                "found": False,
                "error": str(e),
                "products": []
            })
    
    return search_products
