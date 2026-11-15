"""Pre-LLM security checks: restricted fields, SQL-style input and prompt injection."""
import re
import unicodedata
from typing import List, Pattern, Tuple

from errors import MaliciousInputError, SecurityViolationError

__all__ = ["check_security", "SecurityViolationError", "MaliciousInputError"]

# Fields callers may never filter, sort or read. Matching is token-based and also catches
# suffixed names ("credit_card_number"), spaced/hyphenated forms ("credit card") and any
# "tenant*" name, so other tenants can't be addressed.
RESTRICTED_FIELDS = [
    "ssn", "social_security", "password", "passwd", "password_hash", "pin", "secret",
    "api_key", "token", "credit_card", "card_number", "cvv", "is_admin", "salary",
    "tenant", "tenant_id", "internal_cost", "cost_price",
]

_ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")


def _field_pattern(field: str) -> Pattern[str]:
    body = r"[_\s\-]?".join(re.escape(p) for p in field.split("_"))
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


_FIELD_PATTERNS: List[Tuple[str, Pattern[str]]] = [(f, _field_pattern(f)) for f in RESTRICTED_FIELDS]

_INJECTION_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    ("DROP TABLE", re.compile(r"\bdrop\s+(?:table|database|schema)\b")),
    ("DELETE FROM", re.compile(r"\bdelete\s+from\b")),
    ("TRUNCATE", re.compile(r"\btruncate\b")),
    ("UNION SELECT", re.compile(r"\bunion\s+(?:all\s+)?select\b")),
    ("INSERT INTO", re.compile(r"\binsert\s+into\b")),
    ("UPDATE ... SET", re.compile(r"\bupdate\s+\w+\s+set\b")),
    ("ALTER TABLE", re.compile(r"\balter\s+table\b")),
    ("SELECT *", re.compile(r"\bselect\s+(?:\*|count\s*\()")),
    ("stacked query", re.compile(r";\s*(?:select|drop|delete|insert|update|alter|exec)\b")),
    ("tautology", re.compile(r"['\"]\s*or\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+")),
    ("SQL comment", re.compile(r"--|/\*|\*/")),
    ("system catalog", re.compile(r"\b(?:information_schema|pg_catalog|sqlite_master)\b")),
    ("prompt injection", re.compile(
        r"\b(?:ignore|disregard|forget|override)\b.{0,40}\b(?:previous|prior|above|earlier|all|your)\b"
        r".{0,25}\b(?:rules?|instructions?|prompts?|constraints?)\b")),
    ("prompt injection", re.compile(r"\b(?:system\s+prompt|developer\s+mode|jailbreak)\b")),
]


def normalize(prompt: str) -> str:
    text = unicodedata.normalize("NFKC", prompt)
    return _ZERO_WIDTH.sub("", text)


def check_security(prompt: str) -> None:
    lower = normalize(prompt).lower()
    for field, pattern in _FIELD_PATTERNS:
        if pattern.search(lower):
            raise SecurityViolationError(f"Access Denied: restricted field '{field}' detected.")
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(lower):
            raise MaliciousInputError(f"Security Alert: disallowed input pattern '{name}' detected.")
