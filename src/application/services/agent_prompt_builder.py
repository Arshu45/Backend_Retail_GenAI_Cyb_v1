import os
from src.config.csv_schema_loader import get_attribute_schema

def derive_output_fields(attribute_schema: dict, document_columns: set[str]) -> list[str]:
    """
    Derive the final ordered list of output fields for the product response schema.

    This function constructs the list of fields that should appear in the final
    product output by combining:
      - `product_id` (if present in the attribute schema)
      - document-level fields (e.g., title, keyword_tags, embedding_text)
      - attribute fields defined in the attribute schema
      - an explicit `key_features` list field

    Fields specified in the `EXCLUDED_FINAL_ANS_FIELDS` environment variable
    are excluded from the final output.

    Ordering rules:
      1. `product_id` (if present)
      2. Sorted document columns
      3. Attribute schema fields (excluding duplicates and excluded fields)
      4. `key_features` (always added at the end)

    Args:
        attribute_schema (dict): Attribute schema loaded from CSV, where keys are
            attribute names and values define attribute configuration.
        document_columns (set[str]): Set of document-level field names extracted
            from stored product documents.

    Returns:
        list[str]: Ordered list of field names to be used in the final answer schema.
    """
    fields = []
    EXCLUDED_FINAL_ANS_FIELDS = {
        f.strip()
        for f in os.getenv("EXCLUDED_FINAL_ANS_FIELDS", "").split(",")
        if f.strip()
    }

    if "sku" in attribute_schema:
        fields.append("sku")

    fields.extend(sorted(document_columns))
    
    for attr, cfg in attribute_schema.items():
        if attr in fields or attr in EXCLUDED_FINAL_ANS_FIELDS:
            continue

        attr_type = cfg.get("type")
        fields.append(attr)

    # 🔥 Explicitly add key_features (LIST field)
    fields.append("key_features")

    return fields


def build_final_answer_schema(output_fields: list[str]) -> str:
    """
    Build a structured response schema string for the final LLM output.

    This function converts a list of output fields into a JSON-like schema
    representation used to guide the LLM's final response formatting.

    The schema includes:
      - `response_text`: natural language response from the assistant
      - `products`: list of product objects with derived fields

    Args:
        output_fields (list[str]): Ordered list of product field names to include
            in the response schema.

    Returns:
        str: A formatted schema template string for the final answer.
    """
    lines = []

    for field in output_fields:
        if field in ("key_features", "tags"):
            lines.append(f'      "{field}": ["<string>"]')
        elif field in ("price", "product_id"):
            lines.append(f'      "{field}": <number>')
        else:
            lines.append(f'      "{field}": "<any>"')

    body = ",\n".join(lines)

    return f"""
response_text: <natural language response to the user>
products: [
  {{
{body}
  }}
]
"""
