"""Fixes applied to the LLM's step 2 output before building the request."""
import re
from typing import Dict, Optional

from schemas import Canonical

PRICE_OPERATOR_WORDS = [
    ("BETWEEN", ["between"]),
    ("GTE", ["above", "over", "at least", "more than", "greater", "minimum", "min"]),
    ("LTE", ["under", "below", "up to", "less than", "at most", "cheaper than", "maximum", "max"]),
]


def price_operator_from_text(text: str) -> Optional[str]:
    t = text.lower()
    for op, words in PRICE_OPERATOR_WORDS:
        if any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in words):
            return op
    return None


def sanitize(c: Canonical, labels: Dict[str, str]) -> Canonical:
    """Drop anything the LLM invented for a slot that Step 1 left empty."""
    if "status" not in labels:
        c.status = []
    if "category" not in labels:
        c.category = []
    if "price" not in labels:
        c.price_operator = None
        c.price_value = None
    else:
        c.price_operator = price_operator_from_text(labels["price"]) or c.price_operator
    if "sort" not in labels:
        c.sort_field = None
        c.sort_direction = None
    if "pagination" not in labels:
        c.limit = None
        c.page = None
    return c
