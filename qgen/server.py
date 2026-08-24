"""
Server for MrSOLIS 2-AL. Run locally with:

    python -m qgen.server

Also doubles as the deployable web app: it serves the frontend HTML at "/"
and the API at "/generate", so hosting this one process is enough - no
separate static-site deployment needed. No file parsing, no LLM calls -
pure deterministic symbolic computation via sympy.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .pipeline import generate_from_question

app = FastAPI(title="MrSOLIS 2-AL Question Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single-origin app (frontend served by this same process);
    allow_methods=["*"],  # left permissive in case you split hosting later
    allow_headers=["*"],
)

_HTML_PATH = Path(__file__).resolve().parent.parent / "mrsolis-2-al.html"


class GenerateRequest(BaseModel):
    question: str
    n: int = 10
    deck_id: Optional[str] = None
    reset: bool = False


@app.get("/")
def index():
    if _HTML_PATH.exists():
        return FileResponse(_HTML_PATH)
    raise HTTPException(404, "mrsolis-2-al.html not found next to the qgen/ package.")


@app.get("/health")
def health():
    return {"status": "ok", "engine": "qgen", "llm_calls": 0}


@app.post("/generate")
def generate(req: GenerateRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(400, "Question text is empty.")

    deck_id = req.deck_id or hashlib.sha1(question.encode()).hexdigest()[:16]
    n = max(1, min(req.n, 50))

    result = generate_from_question(deck_id=deck_id, question_text=question, n=n, reset=req.reset)
    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn
    # PORT is what Render/Railway/most PaaS platforms inject; QGEN_PORT/8420
    # is the local-dev fallback. Binding 0.0.0.0 (not 127.0.0.1) is required
    # for the platform's proxy to reach this process at all.
    port = int(os.environ.get("PORT", os.environ.get("QGEN_PORT", 8420)))
    host = os.environ.get("QGEN_HOST", "0.0.0.0")
    print(f"MrSOLIS 2-AL question engine starting on {host}:{port}")
    print("No LLM calls in this process - pure deterministic symbolic computation.")
    uvicorn.run(app, host=host, port=port)
