# src/utils/post_retriever.py
from typing import List, Dict, Any


def group_by_sku_base(
    docs: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Deduplicate Chroma results by sku_base.
    Keeps the best (closest) variant per product.

    Args:
        docs: Retrieved documents
        metadatas: Metadata corresponding to each document
        distances: Vector distances (lower is better)
        top_n: Number of unique products to return

    Returns:
        List of unique products with best matching variant
    """
    seen: Dict[str, Dict[str, Any]] = {}

    for doc, meta, dist in zip(docs, metadatas, distances):
        sku_base = meta.get("sku_base")
        if not sku_base:
            continue

        # If product not seen, store it
        if sku_base not in seen:
            seen[sku_base] = {
                #"id": id,
                "document": doc,
                "metadata": meta,
                "distance": dist,
            }
            if len(seen) >= top_n:
                break

    return list(seen.values())

def convert_to_chroma_result_shape(grouped_results):
    return {
        "documents": [[item["document"] for item in grouped_results]],
        "metadatas": [[item["metadata"] for item in grouped_results]],
        "ids": [[
            item["metadata"].get("sku")
            or item["metadata"].get("sku_base")
            for item in grouped_results
        ]],
        "distances": [[item["distance"] for item in grouped_results]],
    }

