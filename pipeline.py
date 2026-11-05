"""NLFilterPipeline: ties security, the two LLM steps, sanitizing and building together."""
import json
from typing import Any, Dict

from pydantic import ValidationError

from builder import build_request_body
from llm import ask
from postprocess import sanitize
from prompts import CANONICAL_PROMPT, LABEL_PROMPT
from schemas import Canonical, Labels
from security import SecurityViolationError, check_security


class NLFilterPipeline:
    def __init__(self, model_name: str = "llama3.2", max_limit: int = 100, fill_missing: bool = True):
        self.model_name = model_name
        self.max_limit = max_limit
        self.fill_missing = fill_missing

    def translate(self, prompt: str, auth_token: str, tenant_id: str) -> Dict[str, Any]:
        try:
            check_security(prompt)

            labels = ask(self.model_name, LABEL_PROMPT, prompt, Labels)                        # Step 1
            payload = {k: v for k, v in labels.model_dump().items() if v}
            canonical = ask(self.model_name, CANONICAL_PROMPT, json.dumps(payload), Canonical)  # Step 2
            canonical = sanitize(canonical, payload)                                           # fix hallucinations
            body = build_request_body(canonical, self.max_limit, self.fill_missing)            # Step 3

            return {
                "status": "SUCCESS",
                "code": 200,
                "request": {
                    "headers": {
                        "Authorization": f"{auth_token}",
                        "X-Tenant-ID": tenant_id,
                        "Content-Type": "application/json",
                    },
                    "body": body.model_dump(mode="json"),
                },
                # "debug": {"labels": payload, "canonical": canonical.model_dump(mode="json")},
            }

        except SecurityViolationError as err:
            return {"status": "HALTED_SECURITY_VIOLATION", "code": 400,
                    "error": {"type": "SECURITY_RESTRICTION", "message": str(err)}}
        except ValidationError as err:
            return {"status": "HALTED_VALIDATION_ERROR", "code": 422,
                    "error": {"type": "SCHEMA_VALIDATION_FAILED", "message": str(err)}}
        except Exception:
            return {"status": "HALTED_INTERNAL_ERROR", "code": 500,
                    "error": {"type": "INTERNAL_FAILURE", "message": "An unexpected error occurred."}}
