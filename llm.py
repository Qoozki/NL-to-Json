"""Thin wrapper around Ollama that returns validated, schema-constrained JSON."""
import logging
import os

import httpx
import ollama

from errors import LLMOutputError, LLMTimeoutError, LLMUnavailableError

log = logging.getLogger(__name__)
_client = None


def _get_client():
    global _client
    if _client is None:   # host comes from OLLAMA_HOST
        _client = ollama.Client(timeout=float(os.getenv("LLM_TIMEOUT", "60")))
    return _client


def ask(model_name: str, system: str, user: str, model_cls):
    """One Ollama call that must return JSON matching `model_cls`. Raises typed pipeline errors."""
    try:
        response = _get_client().chat(
            model=model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format=model_cls.model_json_schema(),
            options={"temperature": 0.0, "num_ctx": 2048, "num_predict": 256},
        )
    except httpx.TimeoutException as err:
        log.error("LLM timeout: %s", err)
        raise LLMTimeoutError("The language model took too long to respond.") from err
    except ollama.ResponseError as err:
        hint = f" Is the model pulled? Run: ollama pull {model_name}" if err.status_code == 404 else ""
        log.error("Ollama returned an error (HTTP %s): %s.%s", err.status_code, err, hint)
        raise LLMUnavailableError("The language model is currently unavailable.") from err
    except (ConnectionError, httpx.HTTPError) as err:
        log.error("Cannot reach Ollama (check OLLAMA_HOST): %s", err)
        raise LLMUnavailableError("The language model is currently unavailable.") from err

    try:
        return model_cls.model_validate_json(response["message"]["content"].strip())
    except (ValueError, KeyError, TypeError) as err:      # pydantic's ValidationError is a ValueError
        log.error("LLM returned invalid output: %s", err)
        raise LLMOutputError("The language model returned an invalid response.") from err
