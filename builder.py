"""Step 3: turns the canonical values into an API request body. Plain Python, no LLM."""
from typing import Any, List

from schemas import (
    AllowedCategory, AllowedStatus, APIRequestBody, Canonical, CategoryFilter,
    Pagination, PriceFilter, SortItem, StatusFilter,
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

    if c.price_operator and c.price_value is not None:
        value = c.price_value
        if c.price_operator == "BETWEEN" and isinstance(value, list):
            value = sorted(value)                     # "between 150 and 20" -> [20, 150]
        filters.append(PriceFilter(operator=c.price_operator, value=value))

    sort = None
    if c.sort_field:
        sort = [SortItem(field=c.sort_field, direction=c.sort_direction or "DESC")]

    limit = min(max(c.limit or 20, 1), max_limit)     # never above the ceiling
    page = max(c.page or 1, 1)

    return APIRequestBody(filters=filters, sort=sort, pagination=Pagination(page=page, limit=limit))
