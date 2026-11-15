"""LLM prompt for step 1 (labeling). Values are parsed deterministically afterwards."""

LABEL_PROMPT = """You are a strict text segmenter. Copy exact phrases from the query into their slots. Output JSON only.

SLOTS:
- "status": stock state words ("dead", "discontinued", "backordered", "in stock", "available", "sold out").
- "category": item types ("clothes", "furniture", "gadgets", "tech", "phones", "books").
- "price": the full price condition INCLUDING its comparison words or symbols ("above $500", "at least 10", "under 200", "<= 100", "between 1000 and 2500").
- "sort": ordering phrases ("cheapest first", "newest first", "price descending, then name").
- "pagination": page numbers or result limits ("limit 10", "page 2").
- "unsupported": any other condition, e.g. rating, reviews, brand, color, dates, text search.

RULES:
1. Copy words verbatim. Do NOT interpret, convert or fix values.
2. Keep comparison words exactly as written ("at least" is not "over"; "<=" is not "<").
3. If a slot is not mentioned, set it to null.
4. Never put price or sort phrases into category or status.

Query: "clothes and furniture between $1,000 and $2.5k, cheapest first, page 2, limit 10"
Output: {"status": null, "category": "clothes and furniture", "price": "between $1,000 and $2.5k", "sort": "cheapest first", "pagination": "page 2, limit 10", "unsupported": null}

Query: "Find dead gadgets over $500 with rating at least 4.5, newest first"
Output: {"status": "dead", "category": "gadgets", "price": "over $500", "sort": "newest first", "pagination": null, "unsupported": "rating at least 4.5"}

Query: "who is the president of France"
Output: {"status": null, "category": null, "price": null, "sort": null, "pagination": null, "unsupported": null}
"""
