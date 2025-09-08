import os, io, base64, re, hashlib
from typing import Optional, List, Tuple, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from anthropic import Anthropic, APIStatusError as AnthropicError
from openai import OpenAI, BadRequestError as OpenAIBadRequest, RateLimitError as OpenAIRateLimit, AuthenticationError as OpenAIAuthError

import chromadb
from chromadb.config import Settings
from pypdf import PdfReader

# ------------------ Env & App ------------------ #
load_dotenv()

ALLOWED = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app = FastAPI(title="PranayAI", version="5.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED if ALLOWED != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Claude (answers)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# OpenAI (embeddings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Vector store
VECTOR_DIR = os.getenv("VECTOR_DIR", "./chroma_store")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "pernai")
chroma_client = chromadb.Client(Settings(persist_directory=VECTOR_DIR))
collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

# Ingest / retrieval tuning (safe defaults)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))          # words-ish (regex tokens)
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "64"))
MAX_CHUNKS_PER_FILE = int(os.getenv("MAX_CHUNKS_PER_FILE", "400"))  # cap to avoid huge requests
MAX_CHARS_PER_CHUNK = int(os.getenv("MAX_CHARS_PER_CHUNK", "8000")) # guard against oversized inputs

# ------------------ Helpers ------------------ #
def ok_anthropic() -> Optional[str]:
    if anthropic_client is None:
        return "Anthropic not ready. Set ANTHROPIC_API_KEY."
    return None

def ok_openai() -> Optional[str]:
    if openai_client is None:
        return "OpenAI embeddings not ready. Set OPENAI_API_KEY."
    return None

def extract_text_blocks(msg) -> str:
    if not msg or not getattr(msg, "content", None):
        return ""
    return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text").strip()

def image_to_base64_jpeg(data: bytes) -> Tuple[str, str]:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((2000, 2000))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    tokens = re.findall(r"\S+\s*", text or "")
    if not tokens:
        return []
    chunks, i = [], 0
    step = max(1, chunk_size - overlap)
    while i < len(tokens) and len(chunks) < MAX_CHUNKS_PER_FILE:
        chunk = "".join(tokens[i:i+chunk_size]).strip()
        if chunk:
            # hard cap by characters to avoid 400 from embeddings API
            chunks.append(chunk[:MAX_CHARS_PER_CHUNK])
        i += step
    return chunks

def read_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    out = []
    for p in reader.pages:
        try:
            out.append(p.extract_text() or "")
        except Exception:
            out.append("")
    return "\n".join(out)

def read_any_file(file: UploadFile) -> str:
    raw = file.file.read()
    name = file.filename.lower()
    if name.endswith(".pdf"):
        return read_pdf_bytes(raw)
    elif name.endswith(".txt") or name.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")
    else:
        # treat unknown extensions as text
        return raw.decode("utf-8", errors="ignore")

def stable_doc_id(filename: str) -> str:
    return hashlib.md5(filename.strip().lower().encode("utf-8")).hexdigest()

# ---------- OpenAI embedding helpers ---------- #
def _embed_batch(texts: List[str]) -> List[List[float]]:
    res = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [row.embedding for row in res.data]

def embed_texts(texts: List[str], batch_size: int = EMBED_BATCH) -> List[List[float]]:
    if err := ok_openai():
        raise RuntimeError(err)
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        out.extend(_embed_batch(texts[i:i+batch_size]))
    return out

def embed_query(q: str) -> List[float]:
    return embed_texts([q])[0]

def retrieve(query: str, top_k: int = 5):
    q_vec = embed_query(query)
    res = collection.query(query_embeddings=[q_vec], n_results=top_k, include=["documents", "metadatas"])
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    return list(zip(docs, metas))

# ------------------ Schemas ------------------ #
class ChatRequest(BaseModel):
    message: str
    system: Optional[str] = None
    max_tokens: int = 800
    use_rag: bool = False
    top_k: int = 5

class ChatResponse(BaseModel):
    reply: str
    sources: Optional[List[dict]] = None

# ------------------ Frontend serving ------------------ #
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("web/index.html")

# ------------------ Health ------------------ #
@app.get("/health")
def health():
    return {
        "ok": True,
        "anthropic_ready": anthropic_client is not None,
        "openai_ready": openai_client is not None,
        "model": CLAUDE_MODEL,
        "embed_model": EMBED_MODEL,
    }

# ------------------ Chat ------------------ #
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if err := ok_anthropic():
        return ChatResponse(reply=err)

    user_content = [{"type": "text", "text": req.message}]
    sources: List[dict] = []

    if req.use_rag:
        if err := ok_openai():
            return ChatResponse(reply=err)
        try:
            results = retrieve(req.message, max(1, req.top_k))
            context_blocks = []
            for doc, meta in results:
                sources.append(meta if isinstance(meta, dict) else {"meta": meta})
                context_blocks.append(f"[{meta.get('source','unknown')}] {doc}")
            if context_blocks:
                user_content.insert(0, {"type": "text", "text": "Context:\n" + "\n".join(context_blocks)})
        except (OpenAIBadRequest, OpenAIRateLimit, OpenAIAuthError) as e:
            # Fall back to no-RAG, but DO NOT 500
            sources = [{"warning": f"RAG disabled due to embeddings error: {str(e)}"}]
        except Exception as e:
            sources = [{"warning": f"RAG disabled due to error: {str(e)}"}]

    try:
        msg = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max(1, min(4000, req.max_tokens)),
            messages=[{"role": "user", "content": user_content}],
        )
        return ChatResponse(reply=extract_text_blocks(msg) or "(no text)", sources=sources)
    except AnthropicError as e:
        return JSONResponse(
            status_code=400,
            content={"error": "claude_request_failed", "detail": str(e), "hint": "Check ANTHROPIC_API_KEY / model."},
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "chat_failed", "detail": str(e)})

# ------------------ Chat w/ Image ------------------ #
@app.post("/chat-image", response_model=ChatResponse)
async def chat_image(file: UploadFile = File(...), prompt: str = Form("Extract text and answer.")):
    if err := ok_anthropic():
        return ChatResponse(reply=err)

    try:
        raw = await file.read()
        b64, media_type = image_to_base64_jpeg(raw)
        content = [
            {"type": "text", "text": prompt},
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
        ]
        msg = anthropic_client.messages.create(
            model=CLAUDE_MODEL, max_tokens=1000, messages=[{"role": "user", "content": content}]
        )
        return ChatResponse(reply=extract_text_blocks(msg) or "(no text)")
    except AnthropicError as e:
        return JSONResponse(status_code=400, content={"error": "claude_image_failed", "detail": str(e)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "chat_image_failed", "detail": str(e)})

# ------------------ Ingest / List / Delete ------------------ #
@app.post("/ingest")
async def ingest(files: List[UploadFile] = File(...)):
    if err := ok_openai():
        return JSONResponse(status_code=400, content={"error": "embeddings_not_ready", "detail": err})

    report: List[Dict[str, Any]] = []

    for f in files:
        filename = f.filename
        # wipe prior chunks for this file
        try:
            collection.delete(where={"source": filename})
        except Exception:
            pass

        # read & chunk
        try:
            text = read_any_file(f)
        except Exception as e:
            report.append({"file": filename, "status": "failed_to_read", "detail": str(e)})
            continue

        chunks = [c for c in chunk_text(text) if c.strip()]
        if not chunks:
            report.append({"file": filename, "status": "no_text_extracted"})
            continue

        # embed
        try:
            vecs = embed_texts(chunks)
        except OpenAIBadRequest as e:
            report.append({"file": filename, "status": "embedding_failed", "detail": str(e)})
            continue
        except (OpenAIRateLimit, OpenAIAuthError) as e:
            report.append({"file": filename, "status": "embedding_failed", "detail": str(e)})
            continue
        except Exception as e:
            report.append({"file": filename, "status": "embedding_failed", "detail": str(e)})
            continue

        # upsert
        try:
            ns = stable_doc_id(filename)
            ids = [f"{ns}-{i}" for i in range(len(chunks))]
            metas = [{"source": filename, "chunk": i} for i in range(len(chunks))]
            collection.add(ids=ids, documents=chunks, embeddings=vecs, metadatas=metas)
            report.append({"file": filename, "status": "ingested", "chunks": len(chunks)})
        except Exception as e:
            report.append({"file": filename, "status": "vector_add_failed", "detail": str(e)})

    # Always 200 with a per-file report (no more 500 mystery)
    return {"ingested": report}

@app.get("/list")
def list_sources():
    try:
        results = collection.get(include=["metadatas"], limit=200_000)
        metas = results.get("metadatas") or []
        seen = set()
        sources: List[str] = []
        # metas may be list[dict] or list[list[dict]]
        for m in metas:
            if isinstance(m, dict):
                src = m.get("source")
                if src and src not in seen:
                    seen.add(src); sources.append(src)
            elif isinstance(m, list):
                for d in m:
                    if isinstance(d, dict):
                        src = d.get("source")
                        if src and src not in seen:
                            seen.add(src); sources.append(src)
        return {"sources": sources, "count": len(sources)}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "list_failed", "detail": str(e)})

@app.post("/delete")
def delete_source(source: str = Query(..., description="Exact filename as shown in /list")):
    try:
        collection.delete(where={"source": source})
        return {"deleted": source}
    except Exception as e:
        return JSONResponse(status_code=400, content={"deleted": False, "error": "delete_failed", "detail": str(e)})
