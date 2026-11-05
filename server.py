"""Web UI + API for the NL filter pipeline. Run with: python server.py"""
from pathlib import Path
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from examples import TEST_GROUPS
from pipeline import NLFilterPipeline

# Credentials stay on the server; the browser never sets them.
CREDS = dict(auth_token="jwt_token_valid_123", tenant_id="tenant_realsoft_prod")
INDEX_HTML = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="NL Product Filter")
pipeline = NLFilterPipeline()

MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8001"))

pipeline = NLFilterPipeline(model_name=MODEL_NAME)

class QueryIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)


@app.get("/")
def index():
    return FileResponse(INDEX_HTML)


@app.get("/api/examples")
def examples():
    return TEST_GROUPS


# Plain `def` so FastAPI runs the blocking Ollama calls in a worker thread.
@app.post("/api/translate")
def translate(body: QueryIn):
    return pipeline.translate(body.query.strip(), **CREDS)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
