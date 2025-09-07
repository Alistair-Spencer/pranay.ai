# app.py  — full, drop-in version
import os
from typing import List, Optional, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# --- Load environment (.env on local; on Render use Env Vars) ---
load_dotenv()

# ---------------- FastAPI app & CORS ----------------
app = FastAPI(title="Pranay AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-friendly; lock down later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve your web UI (web/index.html) at /web
# (If the folder doesn't exist on first run, this won't crash.)
if os.path.isdir("web"):
    app.mount("/web", StaticFiles(directory="web", html=True), name="web")

# Root → redirect to UI
@app.get("/")
def _root():
    if os.path.isdir("web"):
        return RedirectResponse(url="/web/index.html")
    return JSONResponse({"msg": "UI not found. Put your files in ./web/index.html"}, status_code=200)

# Health check for Render/browsers
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# ---------------- System prompt & modes ----------------
SYSTEM_PROMPT_PATH = os.path.join("system_prompts", "system_pranay.md")
DEFAULT_SYSTEM = (
    "You are Pranay AI. Be concise, helpful, and explain clearly. "
    "When using context from the user's documents, cite the source in square brackets like [filename.pdf]."
)

def load_system_prompt() -> str:
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return DEFAULT_SYSTEM

SYSTEM_PROMPT = load_system_prompt()

MODES: Dict[str, str] = {
    "default": "General helper.",
    "study": "Mode: STUDY COACH — explain simply, quiz me, cite sources you used.",
    "fitness": "Mode: FITNESS BUDDY — safe advice, form cues, progressive overload.",
    "biz": "Mode: BUSINESS HELPER — pricing, scripts, short checklists.",
    "texting": "Mode: SOCIAL COACH — respectful, confident, non-cringe.",
}

# ---------------- Optional Retriever (local embeddings) ----------------
RetrieverT = None
retriever = None
try:
    from retriever import Retriever as RetrieverT, DocChunk  # your local module
except Exception:
    DocChunk = None  # type: ignore

if RetrieverT:
    try:
        retriever = RetrieverT(
            persist_dir=os.getenv("CHROMA_DIR", "chroma_db"),
            embeddings_backend=os.getenv("EMBEDDINGS", "local"),
        )
    except Exception:
        retriever = None  # keep the app running even if DB missing

# ---------------- Anthropic (Claude) client ----------------
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # MUST be set in Render env

anthropic_client = None
anthropic_err: Optional[str] = None
try:
    from anthropic import Anthropic
    if ANTHROPIC_API_KEY:
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    else:
        anthropic_err = (
            "Missing ANTHROPIC_API_KEY. Set it in your environment variables."
        )
except Exception as e:
    anthropic_err = f"Anthropic SDK not available: {e}"

# ---------------- Request/Response models ----------------
class ChatRequest(BaseModel):
    message: str
    mode: Optional[str] = None
    use_docs: bool = True
    k: int = 5  # number of retrieved chunks

class ChatResponse(BaseModel):
    reply: str
    sources: List[Dict[str, Any]] = []

# ---------------- Helper: build messages for Claude ----------------
def build_context_chunks(chunks: List[DocChunk]) -> str:  # type: ignore
    if not chunks:
        return ""
    joined = "\n\n".join([f"[{c.metadata.get('source','unknown')}] {c.text}" for c in chunks])
    return f"Relevant context from the user's docs:\n{joined}\n\n"

def system_for_mode(mode_key: str, chunks: List[DocChunk]) -> str:  # type: ignore
    mode_text = MODES.get(mode_key, MODES["default"])
    ctx = build_context_chunks(chunks)
    return f"{SYSTEM_PROMPT}\n\n{mode_text}\n\n{ctx}If you use the context, cite the source in brackets."

# ---------------- Core chat endpoint ----------------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Quick guardrails: API ready?
    if anthropic_err:
        return JSONResponse({"detail": anthropic_err}, status_code=500)
    if anthropic_client is None:
        return JSONResponse({"detail": "Anthropic client not initialized."}, status_code=500)

    # Parse mode (explicit or slash-prefixed in message)
    user_msg = req.message or ""
    mode_key = (req.mode or "").lstrip("/").lower() if req.mode else ""
    if not mode_key and user_msg.strip().startswith("/"):
        # e.g., "/study What is mitosis?"
        parts = user_msg.strip().split(" ", 1)
        mode_key = parts[0].lstrip("/").lower()
        user_msg = parts[1] if len(parts) > 1 else ""

    # Optional retrieval
    chunks: List[DocChunk] = []  # type: ignore
    if req.use_docs and retriever is not None:
        try:
            if retriever.is_ready():
                chunks = retriever.search(user_msg, k=max(1, req.k))
        except Exception:
            chunks = []

    # Compose Claude request
    system_text = system_for_mode(mode_key or "default", chunks)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_msg or " "},
            ],
        }
    ]

    try:
        resp = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=800,
            temperature=0.4,
            system=system_text,
            messages=messages,
        )
        # Claude returns a content list; grab text parts
        reply_text_parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                reply_text_parts.append(block.text)
        reply_text = "\n".join(reply_text_parts).strip() or "(no response)"

        sources = [
            {"source": c.metadata.get("source", "unknown"), "score": c.metadata.get("score")}
            for c in (chunks or [])
        ]
        return ChatResponse(reply=reply_text, sources=sources)

    except Exception as e:
        return JSONResponse({"detail": f"LLM error: {e}"}, status_code=500)
