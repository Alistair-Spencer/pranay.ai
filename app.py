import os, io, base64, re, hashlib
from typing import Optional, List, Tuple, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
from anthropic import Anthropic
from openai import OpenAI

import chromadb
from chromadb.config import Settings
from pypdf import PdfReader

# ------------------ Env & App ------------------ #
load_dotenv()

ALLOWED = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app = FastAPI(title="PranayAI", version="5.0.0")
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

# Ingest tuning
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "64"))
MAX_CHUNKS_PER_FILE = int(os.getenv("MAX_CHUNKS_PER_FILE", "500"))  # safety cap

# ------------------ Helpers ------------------ #
def require_anthropic():
    if anthropic_client is None:
        return "Anthropic not ready. Set ANTHROPIC_API_KEY."
    return None

def require_openai():
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
            chunks.append(chunk)
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
        return raw.decode("utf-8", errors="ignore")

def stable_doc_id(filename: str) -> str:
    return hashlib.md5(filename.strip().lower().encode("utf-8")).hexdigest()

# ---------- OpenAI embedding helpers ---------- #
def _embed_batch(texts: List[str]) -> List[List[float]]:
    res = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [row.embedding for row in res.data]

def embed_texts(texts: List[str], batch_size: int = EMBED_BATCH) -> List[List[float]]:
    err = require_openai()
    if err:
        raise RuntimeError(err)
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        out.extend(_embed_batch(texts[i:i+batch_size]))
    return out

def embed_query(q: str) -> List[float]:
    return embed_texts([q])[0]

def retrieve(query: str, top_k: int = 5):
    q_vec = embed_query(query)
    res = collection.query(query_embeddings=[q_vec], n_results=top_k, include=["documents","metadatas"])
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

# ------------------ Routes ------------------ #
# Serve frontend
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("web/index.html")

@app.get("/health")
def health():
    return {
        "ok": True,
        "anthropic_ready": anthropic_client is not None,
        "openai_ready": openai_client is not None,
        "model": CLAUDE_MODEL,
        "embed_model": EMBED_MODEL,
    }

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    err = require_anthropic()
    if err: return ChatResponse(reply=err)

    user_content = [{"type": "text", "text": req.message}]
    context_blocks = []
    sources = []

    if req.use_rag:
        err2 = require_openai()
        if err2: return ChatResponse(reply=err2)
        results = retrieve(req.message, req.top_k)
        for doc, meta in results:
            context_blocks.append(f"[{meta.get('source','unknown')}] {doc}")
            sources.append(meta)
        if context_blocks:
            user_content.insert(0, {"type": "text", "text": "Context:\n" + "\n".join(context_blocks)})

    msg = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=req.max_tokens,
        messages=[{"role":"user","content":user_content}]
    )
    return ChatResponse(reply=extract_text_blocks(msg), sources=sources)

@app.post("/chat-image", response_model=ChatResponse)
async def chat_image(file: UploadFile = File(...), prompt: str = Form("Extract text and answer.")):
    err = require_anthropic()
    if err: return ChatResponse(reply=err)

    raw = await file.read()
    b64, media_type = image_to_base64_jpeg(raw)
    content = [
        {"type":"text","text":prompt},
        {"type":"image","source":{"type":"base64","media_type":media_type,"data":b64}}
    ]
    msg = anthropic_client.messages.create(
        model=CLAUDE_MODEL, max_tokens=1000,
        messages=[{"role":"user","content":content}]
    )
    return ChatResponse(reply=extract_text_blocks(msg))

@app.post("/ingest")
async def ingest(files: List[UploadFile] = File(...)):
    if openai_client is None:
        return {"error": "OpenAI embeddings not configured. Set OPENAI_API_KEY."}

    report: List[Dict[str, Any]] = []

    for f in files:
        filename = f.filename
        try:
            collection.delete(where={"source": filename})
        except Exception:
            pass

        try:
            text = read_any_file(f)
        except Exception as e:
            report.append({"file": filename, "status": f"failed to read: {str(e)}"})
            continue

        chunks = chunk_text(text)
        if not chunks:
            report.append({"file": filename, "status": "no text extracted"})
            continue

        try:
            vecs = embed_texts(chunks)
        except Exception as e:
            report.append({"file": filename, "status": f"embedding failed: {str(e)}"})
            continue

        ns = stable_doc_id(filename)
        ids = [f"{ns}-{i}" for i in range(len(chunks))]
        metas = [{"source": filename, "chunk": i} for i in range(len(chunks))]

        try:
            collection.add(ids=ids, documents=chunks, embeddings=vecs, metadatas=metas)
            report.append({"file": filename, "chunks": len(chunks), "status": "ingested"})
        except Exception as e:
            report.append({"file": filename, "status": f"vector add failed: {str(e)}"})

    return {"ingested": report}

@app.get("/list")
def list_sources():
    results = collection.get(include=["metadatas"], limit=100000)
    metas = results.get("metadatas") or []
    sources = []
    for m in metas:
        if isinstance(m, dict):
            src = m.get("source")
        elif isinstance(m, list) and m and isinstance(m[0], dict):
            src = m[0].get("source")
        else:
            src = None
        if src and src not in sources:
            sources.append(src)
    return {"sources": sources, "count": len(sources)}

@app.post("/delete")
def delete_source(source: str = Query(..., description="Exact filename as shown in /list")):
    try:
        collection.delete(where={"source": source})
        return {"deleted": source}
    except Exception as e:
        return {"deleted": False, "error": str(e)}
