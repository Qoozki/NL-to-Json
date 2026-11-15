"""Step 2b: reject requests that are empty, contradictory, or (in strict mode) partly unsupported."""
import re

from errors import NoSupportedConditionsError, UnsupportedConditionError
from parsing import check_price_conflicts
from postprocess import Interpretation

_ASKS_FOR_EVERYTHING = re.compile(
    r"^\W*(?:show|list|get|find|display|give|fetch)\b.*\b(?:all|every|everything)\b.*\b(?:products?|items?)\b|"
    r"^\W*(?:all|every)\s+(?:the\s+)?(?:products?|items?)\W*$", re.I)


def validate(interp: Interpretation, prompt: str, strict: bool = False) -> None:
    c = interp.canonical
    check_price_conflicts(c.prices)

    understood = bool(c.status or c.category or c.prices or c.sort or c.limit or c.page)
    if not understood and not (_ASKS_FOR_EVERYTHING.search(prompt) and not interp.unsupported):
        raise NoSupportedConditionsError(
            "No supported filter conditions were found in the query. "
            "Supported: status, category, price, sort (price/created_at/name), page and limit.",
            details={"unsupported": interp.unsupported} if interp.unsupported else None,
        )
    if strict and interp.unsupported:
        raise UnsupportedConditionError(
            "The query contains conditions that are not supported.", details={"unsupported": interp.unsupported})
