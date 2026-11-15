"""Deterministic parsers for the pieces of a query the API can express.

The LLM only segments the query (step 1). Everything with a precise meaning, comparison
operators, numbers, enum values, sort order, pagination, is parsed here so it is exact,
testable and cannot be hallucinated.
"""
import re
from typing import Dict, List, Optional, Tuple

from errors import ConflictingConditionsError, InvalidInputError
from schemas import PriceCondition, SortItem

I = re.IGNORECASE
Notice = Dict[str, str]


def notice(field: str, text: str, reason: str) -> Notice:
    return {"field": field, "text": text.strip(), "reason": reason}


# --------------------------------------------------------------------------------------
# Price: <  <=  >  >=  =  and BETWEEN
# --------------------------------------------------------------------------------------

def _num(tag: str) -> str:
    """A number: $1,000 / 2.5k / 500 -> groups <tag> (digits) and <tag>k (k suffix)."""
    return (rf"\$?\s*(?P<{tag}>\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<{tag}k>[kK])?(?![A-Za-z0-9_])")


def _val(m: "re.Match[str]", tag: str) -> float:
    v = float(m.group(tag).replace(",", ""))
    return v * 1000 if m.group(tag + "k") else v


def _alt(symbols: List[str], words: List[str]) -> str:
    parts = []
    if symbols:
        parts.append("|".join(symbols))
    if words:
        parts.append(r"\b(?:" + "|".join(words) + r")\b")
    return "|".join(parts)


_OPS = ["GTE", "LTE", "GT", "LT", "EQUALS"]
_PREFIX = {
    "GTE": _alt([r">=", r"≥", r"=>"], [
        r"(?:greater|more|higher)\s+than\s+or\s+equal\s+to", r"at\s+least",
        r"(?:no|not)\s+less\s+than", r"minimum(?:\s+of)?", r"min"]),
    "LTE": _alt([r"<=", r"≤", r"=<"], [
        r"(?:less|lower|fewer)\s+than\s+or\s+equal\s+to", r"at\s+most", r"up\s+to",
        r"(?:no|not)\s+more\s+than", r"maximum(?:\s+of)?", r"max"]),
    "GT": _alt([r">"], [
        r"more\s+than", r"greater\s+than", r"higher\s+than", r"more\s+expensive\s+than",
        r"costing\s+more\s+than", r"over", r"above", r"exceeding", r"exceeds", r"beyond"]),
    "LT": _alt([r"<"], [
        r"less\s+than", r"lower\s+than", r"fewer\s+than", r"cheaper\s+than",
        r"less\s+expensive\s+than", r"under", r"below", r"beneath"]),
    "EQUALS": _alt([r"(?<![!<>=])={1,2}"], [r"equals?", r"equal\s+to", r"exactly", r"priced\s+at"]),
}
_PREFIX_RE = re.compile(
    "(?:" + "|".join(f"(?P<{op}>{_PREFIX[op]})" for op in _OPS) + r")\s*(?:price\s*)?(?:of\s*)?(?:is\s*)?" + _num("a"),
    I)
_POSTFIX_RE = re.compile(
    _num("a") + r"\s+or\s+(?P<w>more|above|higher|over|greater|less|under|below|lower|cheaper|fewer)\b", I)
_POSTFIX_OP = {"more": "GTE", "above": "GTE", "higher": "GTE", "over": "GTE", "greater": "GTE",
               "less": "LTE", "under": "LTE", "below": "LTE", "lower": "LTE", "cheaper": "LTE", "fewer": "LTE"}
_BETWEEN_RE = re.compile(
    r"\b(?:between|from)\s+" + _num("a") + r"\s*(?:and|to|-|–|—)\s*" + _num("b"), I)
_DANGLING_RE = re.compile(
    r"\b(?:between|under|over|above|below|at\s+least|at\s+most|more\s+than|less\s+than|up\s+to|cheaper\s+than)\b[^,;]*", I)


def parse_price(text: str, label_mode: bool = False) -> Tuple[List[PriceCondition], List[Notice], List[str]]:
    """Returns (conditions, warnings, dangling). `dangling` holds price-like text we could not read."""
    conds: List[PriceCondition] = []
    warnings: List[Notice] = []

    def between(m):
        lo, hi = _val(m, "a"), _val(m, "b")
        if lo > hi:
            lo, hi = hi, lo
            warnings.append(notice("price", m.group(0), "Bounds were out of order and have been swapped."))
        conds.append(PriceCondition(operator="BETWEEN", value=[lo, hi]))
        return " "

    def postfix(m):
        conds.append(PriceCondition(operator=_POSTFIX_OP[m.group("w").lower()], value=_val(m, "a")))
        return " "

    def prefix(m):
        op = next(o for o in _OPS if m.group(o))
        conds.append(PriceCondition(operator=op, value=_val(m, "a")))
        return " "

    rest = _BETWEEN_RE.sub(between, text)
    rest = _POSTFIX_RE.sub(postfix, rest)
    rest = _PREFIX_RE.sub(prefix, rest)

    dangling = [m.group(0).strip() for m in _DANGLING_RE.finditer(rest)]
    if label_mode and not dangling and re.search(r"\d", rest):
        dangling = [rest.strip()]

    unique: List[PriceCondition] = []
    for c in conds:
        if c not in unique:
            unique.append(c)
    return unique, warnings, dangling


def check_price_conflicts(conds: List[PriceCondition]) -> None:
    """Raises if the price conditions can never all be true together."""
    by_op: Dict[str, set] = {}
    for c in conds:
        by_op.setdefault(c.operator, set()).add(tuple(c.value) if isinstance(c.value, list) else c.value)
    for op, values in by_op.items():
        if len(values) > 1:
            raise ConflictingConditionsError(f"Conflicting price conditions: several different {op} values given.")

    lowers, uppers = [], []                       # (value, inclusive)
    for c in conds:
        v = c.value
        if c.operator == "GT":
            lowers.append((v, False))
        elif c.operator == "GTE":
            lowers.append((v, True))
        elif c.operator == "LT":
            uppers.append((v, False))
        elif c.operator == "LTE":
            uppers.append((v, True))
        elif c.operator == "EQUALS":
            lowers.append((v, True)); uppers.append((v, True))
        elif c.operator == "BETWEEN":
            lowers.append((v[0], True)); uppers.append((v[1], True))
    if lowers and uppers:
        lo = max(lowers, key=lambda x: (x[0], not x[1]))   # tightest: highest, exclusive wins ties
        hi = min(uppers, key=lambda x: (x[0], x[1]))
        if lo[0] > hi[0] or (lo[0] == hi[0] and not (lo[1] and hi[1])):
            raise ConflictingConditionsError("Conflicting price conditions: no price can satisfy all of them.")


# --------------------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------------------

_OFFSET_RE = re.compile(r"\b(?:skip(?:ping)?|offset)\s+(?:the\s+)?(?:first\s+)?(?P<n>-?\d+)\b", I)
_PAGE_RE = re.compile(r"\bpage\s*(?:number\s*|no\.?\s*|#\s*)?(?P<n>-?\d+)\b", I)
_LIMIT_RES = [
    re.compile(r"\b(?:limit(?:ed)?(?:\s+(?:of|to))?|top|first|show(?:ing)?\s+only)\s+(?P<n>-?\d+)\b", I),
    re.compile(r"(?<![\w-])(?P<n>-?\d+)\s+(?:results?|items?|products?|records?|rows?)\b", I),
    re.compile(r"(?<![\w-])(?P<n>-?\d+)\s+per\s+page\b", I),
]


def _collect(regexes, text: str, name: str) -> Tuple[Optional[int], str]:
    values: List[int] = []
    for rx in regexes:
        for m in rx.finditer(text):
            values.append(int(m.group("n")))
        text = rx.sub(" ", text)
    for v in values:
        if v < 1 and name != "offset":
            raise InvalidInputError(f"'{name}' must be a positive whole number, got {v}.")
        if v < 0:
            raise InvalidInputError("'offset' cannot be negative.")
    if len(set(values)) > 1:
        raise ConflictingConditionsError(f"Conflicting '{name}' values: {sorted(set(values))}.")
    return (values[0] if values else None), text


def extract_pagination(text: str, default_limit: int = 20):
    """Returns (page, limit, remaining_text, unsupported, warnings)."""
    unsupported: List[Notice] = []
    warnings: List[Notice] = []
    offset, text = _collect([_OFFSET_RE], text, "offset")
    page, text = _collect([_PAGE_RE], text, "page")
    limit, text = _collect(_LIMIT_RES, text, "limit")

    if offset is not None:
        size = limit or default_limit
        if offset % size == 0:
            from_offset = offset // size + 1
            if page is not None and page != from_offset:
                raise ConflictingConditionsError("Conflicting pagination: 'page' and 'skip/offset' disagree.")
            page = from_offset
            warnings.append(notice("pagination", f"skip {offset}",
                                   f"Offset {offset} was converted to page {from_offset} (limit {size})."))
        else:
            unsupported.append(notice("pagination", f"skip {offset}",
                                      f"Offset {offset} is not a multiple of the limit ({size}); the API only supports whole pages."))
    return page, limit, text, unsupported, warnings


# --------------------------------------------------------------------------------------
# Conditions the API cannot express (dates, ratings, brand, ...)
# --------------------------------------------------------------------------------------

_FIELD_PATTERNS = [
    ("rating", r"ratings?|rated|stars?|reviews?|reviewers?"),
    ("brand", r"brands?|manufacturers?|vendors?|suppliers?|makers?"),
    ("color", r"colou?rs?"),
    ("size", r"sizes?"),
    ("weight", r"weights?|heavier|lighter"),
    ("discount", r"discount(?:s|ed)?|on\s+sale|coupons?"),
    ("quantity", r"quantit(?:y|ies)|inventory|units\s+in\s+stock"),
    ("publication/update date", r"publication[_\s]?dates?|release[_\s]?dates?|published|updated(?:_at)?|modified(?:_at)?"),
    ("sku", r"sku|barcode"),
    ("text search", r"named|called|containing|contains|keywords?|search(?:ing)?\s+for|descriptions?"),
]
_FIELD_RES = [(name, re.compile(r"\b(?:" + pat + r")\b", I)) for name, pat in _FIELD_PATTERNS]
_UNIT_WORDS = {"reviews", "review", "stars", "star", "ratings"}
_NUMERIC_TOKEN = re.compile(r"^[<>=≥≤]*\$?\d[\d.,]*k?\+?$", I)
_CMP_TOKENS = {"more", "less", "than", "at", "least", "most", "over", "under", "above", "below", "between",
               "to", "of", "no", "not", "or", "equal", "greater", "higher", "lower", "min", "max",
               "minimum", "maximum", "exactly", "a", "an", "highest", "lowest", "best", "worst"}

_DATE = (r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\b(?:today|yesterday|tomorrow)\b"
         r"|\b(?:last|this|past|previous)\s+(?:week|month|year|quarter|\d+\s+days?)\b)")
_DATE_RE = re.compile(
    r"(?:\b(?:created|updated|added|posted|published|modified|dated)\b\s*(?:at|on)?\s*)?"
    r"(?:\b(?:between|before|after|since|until|on|in|from|during)\b\s+)?"
    + _DATE + r"(?:\s+(?:and|to|-|–)\s+" + _DATE + r")?", I)
_BETWEEN_AND = re.compile(r"(\b(?:between|from)\s+\S+\s+)and\b", I)
_CLAUSE_SPLIT = re.compile(r"\s*(?:,(?!\d{3}\b)|;|\bwith\b|\bwhere\b|\bhaving\b|\bwhose\b|\bthat\s+have\b|\band\b)\s*", I)


def extract_unsupported(text: str) -> Tuple[str, List[Notice]]:
    """Removes conditions the API can't express and reports them. Returns (cleaned_text, notices)."""
    found: List[Notice] = []

    dates = [m.group(0) for m in _DATE_RE.finditer(text)]
    if dates:
        found.append(notice("date", ", ".join(d.strip() for d in dates),
                            "Date/time filters are not supported (only sorting by Name/Price is)."))
        text = _DATE_RE.sub(" ", text)

    kept: List[str] = []
    protected = _BETWEEN_AND.sub("\\1\x00", text)
    for clause in _CLAUSE_SPLIT.split(protected):
        clause = clause.replace("\x00", "and").strip()
        if not clause:
            continue
        hits = [(m.start(), name, m) for name, rx in _FIELD_RES for m in [rx.search(clause)] if m]
        if not hits:
            kept.append(clause)
            continue
        start, name, m = min(hits, key=lambda h: h[0])
        tokens = list(re.finditer(r"\S+", clause[:start]))
        idx = len(tokens)
        if m.group(0).lower() in _UNIT_WORDS and idx and _NUMERIC_TOKEN.match(tokens[idx - 1].group()):
            idx -= 1                                           # "more than 50 reviews"
            while idx and tokens[idx - 1].group().lower().strip(",") in _CMP_TOKENS:
                idx -= 1
        cut = tokens[idx].start() if idx < len(tokens) else start
        if clause[:cut].strip():
            kept.append(clause[:cut].strip())
        found.append(notice(name, clause[cut:], f"Filtering or sorting by {name} is not supported."))
    return ", ".join(kept), found


_UNSUPPORTED_CATEGORIES = re.compile(
    r"\b(books?|toys?|groceries|grocery|foods?|sports?|beauty|cosmetics|jewel(?:ry|lery)|tools?|garden|pets?|"
    r"automotive|cars?|vehicles?|software|music|movies?|games?|appliances?)\b", I)
SUPPORTED_CATEGORIES_MSG = "Supported categories: ELECTRONICS, APPAREL, HOME_GOODS."


def find_unsupported_categories(text: str) -> List[Notice]:
    seen, out = set(), []
    for m in _UNSUPPORTED_CATEGORIES.finditer(text):
        w = m.group(0).lower()
        if w not in seen:
            seen.add(w)
            out.append(notice("category", m.group(0), f"Category '{w}' is not supported. {SUPPORTED_CATEGORIES_MSG}"))
    return out


# --------------------------------------------------------------------------------------
# Status / category terms
# --------------------------------------------------------------------------------------

STATUS_SYNONYMS = {
    "ACTIVE": ["in stock", "available", "active", "currently available", "on hand"],
    "BACKORDERED": ["backordered", "back ordered", "on backorder", "sold out", "out of stock", "unavailable"],
    "DISCONTINUED": ["discontinued", "dead", "retired", "obsolete", "end of life"],
}
CATEGORY_SYNONYMS = {
    "ELECTRONICS": ["electronics", "electronic", "gadgets", "gadget", "tech", "phones", "phone", "laptops",
                    "laptop", "computers", "computer", "tvs", "tv", "tablets", "headphones"],
    "APPAREL": ["apparel", "clothes", "clothing", "shirts", "shoes", "jeans", "jackets", "fashion"],
    "HOME_GOODS": ["home goods", "furniture", "sofas", "chairs", "decor"],
}


def _compile_terms(synonyms: Dict[str, List[str]]) -> "re.Pattern[str]":
    groups = []
    for canon, phrases in synonyms.items():
        alts = sorted(phrases, key=len, reverse=True)
        body = "|".join(r"[\s_\-]+".join(re.escape(p) for p in re.split(r"[\s_\-]+", ph)) for ph in alts)
        groups.append(f"(?P<{canon}>{body})")
    return re.compile(r"(?<![\w])(?:" + "|".join(groups) + r")(?![\w])", I)


STATUS_TERMS = _compile_terms(STATUS_SYNONYMS)
CATEGORY_TERMS = _compile_terms(CATEGORY_SYNONYMS)

_NEGATION = re.compile(
    r"\b(?:(?:not|no|except|excluding|exclude|without|never)\s+(?:\w+\s+){0,2}|non[-\s]?)$", I)

_STOPWORDS = set("""and or the a an of in for all any some show me find list get display item items product products
goods stuff things only just that are is with under over above below between than at least most more less
cheap cheapest newest oldest first last page limit top sort sorted order ordered by price priced cost
""".split())


def find_terms(text: str, pattern: "re.Pattern[str]", canons: List[str]):
    """Returns ([(canon, negated, phrase)], leftover_text)."""
    matches = []
    for m in pattern.finditer(text):
        canon = next(c for c in canons if m.group(c))
        negated = bool(_NEGATION.search(text[max(0, m.start() - 30):m.start()]))
        matches.append((canon, negated, m.group(0)))
    return matches, pattern.sub(" ", text)


def leftover_words(text: str, *known: "re.Pattern[str]") -> List[str]:
    for p in known:
        text = p.sub(" ", text)
    words = re.findall(r"[a-z][a-z_'\-]*", text.lower())
    return [w for w in words if w not in _STOPWORDS]


# --------------------------------------------------------------------------------------
# Sorting
# --------------------------------------------------------------------------------------

_SORT_PHRASES = [
    (r"most\s+expensive|priciest|highest\s+price[d]?|(?:price\s+)?high(?:est)?\s+to\s+low(?:est)?(?:\s+price)?", "price", "DESC"),
    (r"cheapest|lowest\s+price[d]?|least\s+expensive|(?:price\s+)?low(?:est)?\s+to\s+high(?:est)?(?:\s+price)?", "price", "ASC"),
    (r"newest|latest|most\s+recent(?:ly)?(?:\s+added)?|recently\s+added", "created_at", "DESC"),
    (r"oldest|earliest", "created_at", "ASC"),
    (r"reverse\s+alphabetical(?:ly)?|z\s*-\s*a|z\s+to\s+a", "name", "DESC"),
    (r"alphabetical(?:ly)?|a\s*-\s*z|a\s+to\s+z", "name", "ASC"),
]
_SORT_PHRASE_RES = [(re.compile(r"\b(?:" + p + r")(?![\w])", I), f, d) for p, f, d in _SORT_PHRASES]
_FIELD_WORDS = [
    (re.compile(r"\b(?:created[_\s]?at|created|creation(?:\s+dates?)?|date\s+added|dates?)\b", I), "created_at"),
    (re.compile(r"\b(?:prices?|costs?)\b", I), "price"),
    (re.compile(r"\b(?:names?|titles?)\b", I), "name"),
]
_DEFAULT_DIR = {"price": "ASC", "name": "ASC", "created_at": "DESC"}
_ASC_RE = re.compile(r"\b(?:ascending|asc|increasing|lowest\s+first|oldest\s+first)\b", I)
_DESC_RE = re.compile(r"\b(?:descending|desc|decreasing|highest\s+first|newest\s+first)\b", I)
_SORT_VERB_RE = re.compile(r"\b(?:sort(?:ed)?|order(?:ed)?|rank(?:ed)?|arrange[d]?)\b[^,;]*?\bby\b", I)
_SORT_BY_RE = re.compile(
    r"\b(?:sort(?:ed)?|order(?:ed)?|rank(?:ed)?|arrange[d]?)\s+(?:\w+\s+){0,2}?by\s+(?P<f>[\w.]+)", I)
_THEN_RE = re.compile(r"\bthen\s+(?:by\s+)?(?P<f>[\w.]+)", I)
_SORT_CLAUSE_SPLIT = re.compile(r"\s*(?:,(?!\d{3}\b)|;|\bthen\b|\band\b)\s*", I)
_SORT_NOISE = {"sort", "sorted", "order", "ordered", "by", "then", "first", "the", "results", "items",
               "products", "list", "show", "me", "a", "an", "please", "from", "and"}
_KNOWN_SORT_WORDS = {"price", "prices", "cost", "costs", "created", "created_at", "name", "names", "title",
                     "titles", "ascending", "descending", "asc", "desc", "the", "a", "an", "date", "dates", "creation",
                     "added"}


def _direction_in(text: str) -> Optional[str]:
    asc, desc = bool(_ASC_RE.search(text)), bool(_DESC_RE.search(text))
    if asc and desc:
        raise ConflictingConditionsError(f"Conflicting sort directions in '{text.strip()}'.")
    return "ASC" if asc else "DESC" if desc else None


def parse_sort(text: str, label_mode: bool = False) -> Tuple[List[SortItem], List[Notice], List[Notice]]:
    """Phrases like 'cheapest first' anywhere; plain field names only after 'sort by' (or in a label)."""
    items: List[SortItem] = []
    unsupported: List[Notice] = []
    warnings: List[Notice] = []

    def add(field: str, direction: str):
        for it in items:
            if it.field.value == field:
                if it.direction != direction:
                    raise ConflictingConditionsError(f"Conflicting sort directions for '{field}'.")
                return
        items.append(SortItem(field=field, direction=direction))

    clauses = [c for c in _SORT_CLAUSE_SPLIT.split(text) if c.strip()]
    for clause in clauses:                                   # pass 1: unambiguous phrases
        for rx, field, direction in _SORT_PHRASE_RES:
            if rx.search(clause):
                explicit = _direction_in(rx.sub(" ", clause))
                if explicit and explicit != direction:
                    raise ConflictingConditionsError(f"Conflicting sort directions in '{clause.strip()}'.")
                add(field, direction)
                break

    verb = _SORT_VERB_RE.search(text)
    scope = text[verb.end():] if verb else (text if label_mode else "")
    for clause in _SORT_CLAUSE_SPLIT.split(scope):           # pass 2: "by price descending"
        if not clause.strip() or any(rx.search(clause) for rx, _, _ in _SORT_PHRASE_RES):
            continue
        for rx, field in _FIELD_WORDS:
            if rx.search(clause):
                rest = _DESC_RE.sub(" ", _ASC_RE.sub(" ", rx.sub(" ", clause)))
                if any(w not in _SORT_NOISE for w in re.findall(r"[a-z_]+", rest.lower())):
                    break                                    # e.g. "price under 100": not a sort clause
                if field == "created_at" and rx.search(clause).group(0).lower() in ("date", "dates"):
                    warnings.append(notice("sort", "date", "'date' was interpreted as created_at, the only date field available."))
                add(field, _direction_in(clause) or _DEFAULT_DIR[field])
                break

    for rx in (_SORT_BY_RE, _THEN_RE if verb else None):     # sort field we don't know
        for m in (rx.finditer(text) if rx else []):
            f = m.group("f")
            if f.lower() not in _KNOWN_SORT_WORDS and not any(p.search(f) for p, _, _ in _SORT_PHRASE_RES):
                unsupported.append(notice("sort", f, f"Sorting by '{f}' is not supported. Supported sort fields: price, created_at, name."))
    return items, unsupported, warnings


def looks_supported(phrase: str) -> bool:
    """True if the phrase contains something we can express (used to distrust the LLM's 'unsupported')."""
    cats = list(CATEGORY_SYNONYMS)
    return bool(
        find_terms(phrase, STATUS_TERMS, list(STATUS_SYNONYMS))[0]
        or find_terms(phrase, CATEGORY_TERMS, cats)[0]
        or parse_price(phrase)[0]
        or any(rx.search(phrase) for rx, _, _ in _SORT_PHRASE_RES)
    )
