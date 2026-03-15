"""Utility functions for formatting and display."""

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


def trim_response_text(response_text: str, formatted_products: list) -> str:
    """
    Trim product titles and listed details from the response text to avoid duplication
    in the UI containing product cards.
    """
    if not response_text or not formatted_products:
        return response_text
        
    earliest_idx = len(response_text)
    for p in formatted_products:
        title = getattr(p, "title", None)
        if title and title in response_text:
            idx = response_text.find(title)
            if idx != -1 and idx < earliest_idx:
                earliest_idx = idx
                
    if earliest_idx < len(response_text):
        # We found a product title. Truncate before it to leave a clean intro sentence.
        colon_idx = response_text.rfind(':', 0, earliest_idx)
        period_idx = response_text.rfind('.', 0, earliest_idx)
        
        if colon_idx != -1 and (period_idx == -1 or colon_idx > period_idx):
            # Cut precisely at the colon (e.g., "Here are a few options:")
            return response_text[:colon_idx + 1].strip()
        elif period_idx != -1:
            # Cut at the end of the previous sentence
            return response_text[:period_idx + 1].strip()
        else:
            # Just cut explicitly where the title starts
            return response_text[:earliest_idx].strip()
            
    return response_text