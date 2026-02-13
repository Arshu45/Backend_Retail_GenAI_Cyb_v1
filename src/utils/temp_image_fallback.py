# # """
# TEMPORARY IMAGE FALLBACK UTILITY
# =================================
# This module provides fallback image URLs for products when the product_images table is empty.

# ⚠️ TEMPORARY SOLUTION - Remove once product_images table is populated
# """

import os
import hashlib
from typing import List, Optional

# Available fallback images in /static/images
FALLBACK_IMAGES = [
    "blue.jpg",
    "cream.jpg",
    "cream_blue.jpg",
    "light_pink.jpg",
    "orange.png",
    "pink.jpg",
    "red.jpg",
    "white.jpg",
    "yellow.jpg",
    "yellow_dress.jpg",
]


def get_fallback_image_url(product_id: str, index: int = 0) -> str:
    """
    Get a consistent fallback image URL for a product.
    
    Uses product_id hash to ensure the same product always gets the same image(s).
    
    Args:
        product_id: The product ID
        index: Image index (0 for primary, 1+ for additional images)
        
    Returns:
        URL path to the fallback image
        
    Example:
        >>> get_fallback_image_url("PRD123", 0)
        '/static/images/pink.jpg'
    """
    # Hash product_id + index to get consistent but pseudo-random selection
    hash_input = f"{product_id}_{index}".encode('utf-8')
    hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
    
    # Select image based on hash
    image_index = hash_value % len(FALLBACK_IMAGES)
    image_filename = FALLBACK_IMAGES[image_index]
    
    return f"/static/images/{image_filename}"


def get_fallback_images(product_id: str, count: int = 3) -> List[dict]:
    """
    Get multiple fallback images for a product detail page.
    
    Args:
        product_id: The product ID
        count: Number of images to return (default: 3)
        
    Returns:
        List of image dictionaries compatible with ProductImageResponse schema
        
    Example:
        >>> get_fallback_images("PRD123", 2)
        [
            {"id": 0, "image_url": "/static/images/pink.jpg", "is_primary": True, "display_order": 0},
            {"id": 1, "image_url": "/static/images/blue.jpg", "is_primary": False, "display_order": 1}
        ]
    """
    images = []
    for i in range(min(count, len(FALLBACK_IMAGES))):
        images.append({
            "id": i,
            "image_url": get_fallback_image_url(product_id, i),
            "is_primary": i == 0,
            "display_order": i
        })
    return images


def get_primary_fallback_image(product_id: str) -> Optional[str]:
    """
    Get the primary fallback image URL for a product.
    
    This is a convenience function for product listing pages.
    
    Args:
        product_id: The product ID
        
    Returns:
        URL path to the primary fallback image
    """
    return get_fallback_image_url(product_id, 0)