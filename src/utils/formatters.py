"""Utility functions for formatting and display."""

from typing import Dict, List


def format_price(metadata: dict) -> str:
    """
    Format price with discount information.
    
    Args:
        metadata: Product metadata dictionary
        
    Returns:
        Formatted price string
    """
    price = metadata.get("price")
    mrp = metadata.get("mrp")

    if price is None:
        return "Price not available"

    price_str = f"₹{int(price):,}"

    if mrp and mrp > price:
        discount = int(((mrp - price) / mrp) * 100)
        return f"{price_str} ({discount}% off)"

    return price_str


def extract_key_features(metadata: dict) -> list:
    """
    Extract safe, dynamic key features from metadata.
    Does NOT assume fixed attributes.
    
    Args:
        metadata: Product metadata dictionary
        
    Returns:
        List of key feature strings
    """
    features = []

    if brand := metadata.get("brand"):
        features.append(f"Brand: {str(brand).title()}")

    if stock := metadata.get("stock_status"):
        features.append(f"Stock: {str(stock).replace('_', ' ').title()}")

    # Optional dynamic attributes (only if present)
    for attr in ["size", "age_group", "color", "occasion", "fit_type"]:
        if val := metadata.get(attr):
            features.append(f"{attr.replace('_',' ').title()}: {str(val).title()}")

    return features[:4]  # keep UI compact


def generate_follow_up_questions(products: list) -> list:
    """
    Generate follow-up questions based on product results.
    
    Args:
        products: List of product dictionaries
        
    Returns:
        List of follow-up question strings
    """
    questions = []

    brands = {p.get("metadata", {}).get("brand") for p in products if p.get("metadata")}
    if len(brands) > 1:
        questions.append("Would you like to explore other brands?")

    questions.append("Would you like to apply filters like price or color?")
    questions.append("Do you want help choosing the best option?")

    return questions[:2]