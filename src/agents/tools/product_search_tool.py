"""Product search tool for LangChain agents."""

import json
from langchain_core.tools import tool
from src.config.logger import get_logger

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
            formatted_products = []
            for product in products:
                try:
                    doc = json.loads(product["document"])
                    metadata = product["metadata"]
                    
                    formatted_product = {
                        "title": doc.get("title", "Unknown Product"),
                        "product_id": product.get("id", ""),
                        "price": metadata.get("price", 0),
                        "mrp": metadata.get("mrp", 0),
                        "color": metadata.get("color", ""),
                        "size": metadata.get("size", ""),
                        "gender": metadata.get("gender", ""),
                        "occasion": metadata.get("occasion", ""),
                        "brand": metadata.get("brand", ""),
                        "stock_status": metadata.get("stock_status", ""),
                        "description": doc.get("embedding_text", "")
                    }
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
