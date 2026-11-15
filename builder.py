"""Step 3: turns the canonical values into an API request body. Plain Python, no LLM."""
from typing import Any, List

from schemas import (
    AllowedCategory, AllowedStatus, APIRequestBody, Canonical, CategoryFilter,
    Pagination, PriceFilter, StatusFilter,
)


def build_request_body(c: Canonical, max_limit: int = 100, fill_missing: bool = True) -> APIRequestBody:
    filters: List[Any] = []

    status = c.status
    category = c.category
    if fill_missing:
        status = status or list(AllowedStatus)        # not mentioned -> all statuses
        category = category or list(AllowedCategory)  # not mentioned -> all categories

    for values, filter_cls in ((status, StatusFilter), (category, CategoryFilter)):
        values = list(dict.fromkeys(values))
        if len(values) == 1:
            filters.append(filter_cls(operator="EQUALS", value=values[0]))
        elif values:
            filters.append(filter_cls(operator="IN", value=values))

    for p in c.prices:                                # every price condition, e.g. > 100 AND < 500
        filters.append(PriceFilter(operator=p.operator, value=p.value))

    limit = min(max(c.limit or 20, 1), max_limit)     # never above the ceiling
    page = max(c.page or 1, 1)

    return APIRequestBody(filters=filters, sort=c.sort or None, pagination=Pagination(page=page, limit=limit))
