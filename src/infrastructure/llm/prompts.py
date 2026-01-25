"""LLM system prompts and templates."""


# Attribute extraction prompt
EXTRACT_ATTRIBUTES_PROMPT="""Extract structured attributes from a user query for a ChromaDB where filter.

You MUST follow these rules STRICTLY:

1. Output MUST be a single, complete, valid JSON object.
2. Output ONLY JSON. No markdown, explanations, or comments.
3. All string values MUST be lowercase.
4. Extract ONLY attributes that are EXPLICITLY stated in the user query.
5. Do NOT infer, guess, expand, normalize, or assume any attribute.
6. If an attribute is not explicitly mentioned, OMIT that key.
7. Do NOT include keys with null values.
8. The JSON must be valid and complete (no truncation).

Allowed keys (include ONLY if explicitly present in query):
- color (string)
- occasion (string)
- gender (string)
- age (object with ONLY ONE operator OR range)
- price (object with ONLY ONE operator)

Strict attribute rules:

Color:
- Extract ONLY if a real color name is present (e.g., red, blue, yellow).
- Do NOT treat occasions, events, or adjectives as colors.

Occasion:
- Extract ONLY if explicitly stated (e.g., birthday, party, wedding, festive, casual).

Gender:
- Extract ONLY if explicitly stated.
- Normalize:
  - girl, girls, female, women, woman → "girls"
  - boy, boys, male, men, man → "boys"
- Words like "kids", "children", "child", "toddler", "infant" are NOT genders.
- **NEVER output gender as "kids" or "children".**
- If the word "kids" or "children" appears, DO NOT output gender.

Age:
- Extract ONLY if an age is explicitly mentioned.
- Age MUST be numeric.
- Do NOT output age_group strings.
- Use ONLY ONE operator:
  - “X year old”, “age X”, “for X yr”, “X y/o” → { "$eq": X }
  - “under X years”, “below X years”, “less than X years” → { "$lt": X }
  - “above X years”, “over X years”, “greater than X years” → { "$gt": X }
  - “X-Y year old”, “between X and Y years” → { "$gte": X, "$lte": Y }
- If age is ambiguous or inferred, OMIT age.

Price:
- Extract ONLY if explicitly mentioned.
- Use ONLY ONE operator:
  - under, below, less than, upto, up to → { "$lte": number }
  - above, over, greater than, more than → { "$gte": number }
  - equal, exactly, exact, for → { "$eq": number }

"""
