## Run with Docker | (Recommended)

```powershell
# Windows PowerShell (use `cp` on macOS/Linux)
Copy-Item .env.example .env
notepad .env            # fill in API_AUTH_TOKEN and TENANT_ID, save as .env (not .env.txt)
docker compose up --build
```

The first start downloads the model (about 2 GB), so wait for `model-pull` to finish. Then open
<http://127.0.0.1:8001>. The port is bound to localhost only.

What starts: `ollama` (LLM server, models persisted in the `ollama_data` volume), then `model-pull` (one-shot
download), then `app` (web UI + API). `app` starts only after the model is available.

- **GPU (NVIDIA):** uncomment the `deploy:` block under `ollama` in `docker-compose.yml`.
- **Different model:** set `MODEL_NAME=...` in `.env`.
- **Stop / reset:** `docker compose down` (add `-v` to also delete downloaded models).

## Run locally (Without Docker)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ollama pull llama3.2

export API_AUTH_TOKEN=... TENANT_ID=...                 # PowerShell: $env:API_AUTH_TOKEN="..."
python server.py                                        # http://127.0.0.1:8001
python main.py                                          # CLI: run all built-in examples (needs no credentials)
```
