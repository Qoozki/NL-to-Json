"""Step 2: reconcile the LLM's phrase labels with the query and produce canonical values.

The labels tell us which words belong to which slot (and let us spot words nobody understood).
All values are produced by the deterministic parsers, never copied from the LLM.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List

from parsing import (
    CATEGORY_SYNONYMS, CATEGORY_TERMS, STATUS_SYNONYMS, STATUS_TERMS, Notice, extract_pagination,
    extract_unsupported, find_terms, find_unsupported_categories, leftover_words, looks_supported,
    notice, parse_price, parse_sort, SUPPORTED_CATEGORIES_MSG,
)
from schemas import AllowedCategory, AllowedStatus, Canonical, Labels
from security import normalize


@dataclass
class Interpretation:
    canonical: Canonical
    unsupported: List[Notice] = field(default_factory=list)
    warnings: List[Notice] = field(default_factory=list)


def _dedupe(items: List[Notice]) -> List[Notice]:
    """Drop empty items, and items already covered by (or covering) another item's text."""
    out: List[Notice] = []
    for it in items:
        key = it["text"].lower()
        if not key:
            continue
        for i, o in enumerate(out):
            existing = o["text"].lower()
            if key in existing:
                break                      # already reported
            if existing in key:
                out[i] = it                # the new one is more specific
                break
        else:
            out.append(it)
    return out


def _terms(prompt_text: str, label: str, pattern, canons, field_name: str, other_pattern, unsupported: List[Notice]):
    matches, _ = find_terms(prompt_text, pattern, canons)
    values: List[str] = []
    for canon, negated, phrase in matches:
        if negated:
            unsupported.append(notice(field_name, phrase, f"Excluding a {field_name} ('not {phrase}') is not supported; only matching values is."))
        elif canon not in values:
            values.append(canon)
    if label:
        for word in leftover_words(label, pattern, other_pattern):
            reason = f"Unrecognised {field_name} '{word}'."
            if field_name == "category":
                reason += " " + SUPPORTED_CATEGORIES_MSG
            unsupported.append(notice(field_name, word, reason))
    return values


def reconcile(prompt: str, labels: Labels, default_limit: int = 20, max_limit: int = 100) -> Interpretation:
    lab: Dict[str, str] = {k: v.strip() for k, v in labels.model_dump().items() if isinstance(v, str) and v.strip()}
    unsupported: List[Notice] = []
    warnings: List[Notice] = []

    text = normalize(prompt)
    page, limit, text, p_unsup, p_warn = extract_pagination(text, default_limit)
    unsupported += p_unsup
    warnings += p_warn
    text, found = extract_unsupported(text)
    unsupported += found

    for key in ("status", "category", "price", "sort"):          # same clean-up for the LLM's phrases
        if key in lab:
            lab[key] = extract_unsupported(lab[key])[0]

    status = _terms(text, lab.get("status", ""), STATUS_TERMS, list(STATUS_SYNONYMS), "status", CATEGORY_TERMS, unsupported)
    category = _terms(text, lab.get("category", ""), CATEGORY_TERMS, list(CATEGORY_SYNONYMS), "category", STATUS_TERMS, unsupported)
    unsupported += find_unsupported_categories(text)

    # price: the labelled phrase first, the whole query as a fallback
    prices, dangling = [], []
    if lab.get("price"):
        prices, w, dangling = parse_price(lab["price"], label_mode=True)
        warnings += w
    if not prices:
        prices, w, d = parse_price(text)
        warnings += w
        dangling = dangling or d
    for d in dangling:
        unsupported.append(notice("price", d, "Could not interpret this price condition. Use e.g. 'under 50', 'at least 10', 'between 10 and 20'."))

    # sort: same idea
    sort, s_unsup, s_warn = [], [], []
    if lab.get("sort"):
        sort, s_unsup, s_warn = parse_sort(lab["sort"], label_mode=True)
    if not sort:
        sort, u2, w2 = parse_sort(text)
        s_unsup += u2
        s_warn += w2
    unsupported += s_unsup
    warnings += s_warn

    # anything the LLM flagged that we did not already understand
    for phrase in re.split(r"[;,]", lab.get("unsupported", "")):
        if phrase.strip() and not looks_supported(phrase):
            unsupported.append(notice("other", phrase, "This condition is not supported."))

    if limit is not None and limit > max_limit:
        warnings.append(notice("pagination", f"limit {limit}", f"Limit {limit} exceeds the maximum; using {max_limit}."))
        limit = max_limit

    canonical = Canonical(
        status=[AllowedStatus(s) for s in status],
        category=[AllowedCategory(c) for c in category],
        prices=prices, sort=sort, limit=limit, page=page,
    )
    return Interpretation(canonical, _dedupe(unsupported), warnings)
