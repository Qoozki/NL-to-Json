"""Thin wrapper around Ollama that returns validated, schema-constrained JSON."""
import ollama


def ask(model_name: str, system: str, user: str, model_cls):
    """One Ollama call that must return JSON matching `model_cls`."""
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format=model_cls.model_json_schema(),
        options={
            "temperature": 0.0,
            "num_ctx": 2048,
            "num_predict": 256,
        },
    )
    return model_cls.model_validate_json(response["message"]["content"].strip())
