"""Pre-LLM security checks: blocks restricted fields and SQL-style keywords."""
import re

RESTRICTED_FIELDS = {"ssn", "password_hash", "credit_card", "is_admin", "salary", "tenant_id"}
RESTRICTED_KEYWORDS = {"DROP TABLE", "DELETE FROM", "TRUNCATE", "UNION SELECT"}


class SecurityViolationError(Exception):
    pass


def check_security(prompt: str) -> None:
    lower, upper = prompt.lower(), prompt.upper()
    for field in RESTRICTED_FIELDS:
        if re.search(r"\b" + re.escape(field) + r"\b", lower):
            raise SecurityViolationError(f"Access Denied: restricted field '{field}' detected.")
    for kw in RESTRICTED_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", upper):
            raise SecurityViolationError(f"Security Alert: restricted keyword '{kw}' detected.")
