"""LLM prompts for step 1 (labeling) and step 2 (canonicalizing)."""

LABEL_PROMPT = """You are a strict text segmenter. Copy exact natural language phrases from the query into their corresponding slots.

RULES:
- "status": Words describing stock state (e.g., "dead", "discontinued", "backordered", "in stock", "available", "sold out").
- "category": Words describing item types (e.g., "clothes", "clothing", "furniture", "gadgets", "tech", "phones").
- "price": Phrases describing cost or monetary bounds (e.g., "above $500", "under 200", "between 1000 and 2500", "over $250").
- "sort": Phrases describing ordering or rank (e.g., "cheapest first", "newest first", "lowest price", "most expensive").
- "pagination": Phrases describing page numbers or result limits (e.g., "limit 10", "page 2", "limit 500").

STRICT CONSTRAINTS:
1. Do NOT put price or sorting phrases into category or status.
2. If a slot is not mentioned, set it to null.
3. Copy words verbatim from the query. Do NOT interpret or convert values.

Query: "clothes and furniture between $1,000 and $2.5k, cheapest first, page 2, limit 10"
Output: {"status": null, "category": "clothes and furniture", "price": "between $1,000 and $2.5k", "sort": "cheapest first", "pagination": "page 2, limit 10"}

Query: "Find dead gadgets under $500, newest first, limit 500"
Output: {"status": "dead", "category": "gadgets", "price": "under $500", "sort": "newest first", "pagination": "limit 500"}
"""

CANONICAL_PROMPT = """Convert these labeled phrases into the schema. Output JSON only.

status values:   ACTIVE (in stock, available) | BACKORDERED (sold out, unavailable) | DISCONTINUED (dead, retired)
category values: ELECTRONICS (gadgets, tech, phones) | APPAREL (clothes, clothing) | HOME_GOODS (furniture)
price: price_operator GTE (above, over, at least) | LTE (under, below, up to) | EQUALS | BETWEEN (between X and Y)
       price_value is a plain number, except BETWEEN where it is an array [min, max]
sort: field price | created_at | name; direction ASC | DESC  (newest = created_at DESC, cheapest = price ASC)
pagination: limit and page as integers, exactly as written

Example input:  {"status":"backordered and dead","category":"gadgets","price":"above 500","sort":"newest first","pagination":"limit 500"}
Example output: {"status":["BACKORDERED","DISCONTINUED"],"category":["ELECTRONICS"],"price_operator":"GTE","price_value":500,"sort_field":"created_at","sort_direction":"DESC","limit":500,"page":null}

Example input:  {"category":"clothes","price":"between 150 and 20"}
Example output: {"status":[],"category":["APPAREL"],"price_operator":"BETWEEN","price_value":[20,150],"sort_field":null,"sort_direction":null,"limit":null,"page":null}"""
