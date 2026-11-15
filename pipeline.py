"""NLFilterPipeline: security -> LLM labelling -> deterministic parsing -> validation -> request body."""
import logging
import time
import unicodedata
from typing import Any, Callable, Dict

from builder import build_request_body
from errors import InvalidInputError, PipelineError
from llm import ask
from postprocess import reconcile
from prompts import LABEL_PROMPT
from schemas import Labels
from security import check_security
from validation import validate

log = logging.getLogger(__name__)
MAX_QUERY_LENGTH = 500


class NLFilterPipeline:
    def __init__(self, model_name: str = "llama3.2", max_limit: int = 100, fill_missing: bool = True,
                 strict_unsupported: bool = False, llm: Callable = ask):
        self.model_name = model_name
        self.max_limit = max_limit
        self.fill_missing = fill_missing
        self.strict_unsupported = strict_unsupported   # True: unsupported conditions -> 422 instead of a warning
        self._llm = llm

    @staticmethod
    def _check_input(prompt: Any) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise InvalidInputError("Query must be a non-empty string.")
        if len(prompt) > MAX_QUERY_LENGTH:
            raise InvalidInputError(f"Query is too long (max {MAX_QUERY_LENGTH} characters).")
        if any(unicodedata.category(ch) == "Cc" and ch not in "\t\n\r" for ch in prompt):
            raise InvalidInputError("Query contains control characters.")
        return prompt.strip()

    def translate(self, prompt: str) -> Dict[str, Any]:
        """Returns a response dict with an HTTP-style `code`. Never contains credentials."""
        start = time.perf_counter()
        result = self._translate(prompt)
        ms = round((time.perf_counter() - start) * 1000)
        err = result.get("error", {}).get("type")
        level = logging.ERROR if result["code"] >= 500 else logging.WARNING if result["code"] >= 400 else logging.INFO
        log.log(level, "translate %s code=%s%s unsupported=%d (%d ms)", result["status"], result["code"],
                f" error={err}" if err else "", len(result.get("unsupported", [])), ms,
                extra={"error_type": err} if err else {})
        return result

    def _translate(self, prompt: str) -> Dict[str, Any]:
        try:
            prompt = self._check_input(prompt)
            log.debug("query: %r", prompt)          # query text only at DEBUG
            check_security(prompt)

            labels = self._llm(self.model_name, LABEL_PROMPT, prompt, Labels)               # Step 1 (LLM)
            interp = reconcile(prompt, labels, max_limit=self.max_limit)                      # Step 2
            validate(interp, prompt, strict=self.strict_unsupported)
            body = build_request_body(interp.canonical, self.max_limit, self.fill_missing)   # Step 3

            return {
                "status": "PARTIAL_SUCCESS" if interp.unsupported else "SUCCESS",
                "code": 200,
                "request": {
                    # Auth/tenant headers are attached server-side when the request is sent; see config.py.
                    "headers": {"Content-Type": "application/json"},
                    "body": body.model_dump(mode="json"),
                },
                "unsupported": interp.unsupported,   # conditions we could NOT put in the request
                "warnings": interp.warnings,         # adjustments we made (clamped limit, swapped bounds, ...)
            }
        except PipelineError as err:
            return err.to_response()
        except Exception:
            log.exception("Unexpected failure while translating a query")
            return PipelineError("An unexpected error occurred.").to_response()
