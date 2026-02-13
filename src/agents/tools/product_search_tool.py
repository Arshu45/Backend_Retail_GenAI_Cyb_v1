"""Product search tool for LangChain agents."""

import os
import json
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
            products = product_service.search_products(query, n_results=5)
            
            if not products:
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
                    # ðŸ”¹ Document fields
                    for field in DOCUMENT_COLUMNS:
                        formatted_product[field] = doc.get(field, "")

                    # ðŸ”¹ Metadata fields
                    for attr_name, attr_schema in ATTRIBUTE_SCHEMA.items():
                        formatted_product[attr_name] = metadata.get(attr_name, "")

                    formatted_products.append(formatted_product)

                except Exception as e:
                    logger.warning(f"Error formatting product: {e}")
                    continue
            
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