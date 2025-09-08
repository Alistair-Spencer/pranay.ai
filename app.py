# app.py
import os, io, base64, re, hashlib
from typing import Optional, List, Tuple, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from anthropic import Anthropic
from dotenv import load_dotenv

# RAG stack
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader

# ------------------ Env & App ------------------ #
load_dotenv()
ALLOWED = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app = FastAPI(title="PranayAI", version="3.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED if ALLOWED != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")
VECTOR_DIR = os.getenv("VECTOR_DIR", "./chroma_store")
COLLECTION_NAME = "pernai"

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# Chroma client
chroma_client = chromadb.Client(Settings(persist_directory=VECTOR_DIR))
collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

# Embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ------------------ Helpers ------------------ #
def require_anthropic():
    if anthropic_client is None:
        return "Anthropic not ready. Set ANTHROPIC_API_KEY."
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

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    tokens = re.findall(r"\S+\s*", text)
    chunks = []
    i = 0
    while i < len(tokens):
        chunk = "".join(tokens[i:i+chunk_size])
        chunks.append(chunk.strip())
        i += (chunk_size - overlap)
    return [c for c in chunks if c]

def read_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join([(p.extract_text() or "") for p in reader.pages])

def read_any_file(file: UploadFile) -> str:
    raw = file.file.read()
    name = file.filename.lower()
    if name.endswith(".pdf"):
        return read_pdf_bytes(raw)
    elif name.endswith(".txt") or name.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")
    else:
        # Treat unknowns as text; change if you want to reject
        return raw.decode("utf-8", errors="ignore")

def stable_doc_id(filename: str) -> str:
    """
    Stable ID namespace per source file. Using lowercase filename hash is
    simple and works well for dedupe across re-ingests.
    """
    return hashlib.md5(filename.strip().lower().encode("utf-8")).hexdigest()

def embed_texts(chunks: List[str]) -> List[List[float]]:
    vecs = embedder.encode(chunks, convert_to_numpy=True)
    return [v.tolist() for v in vecs]

def retrieve(query: str, top_k: int = 5):
    q_vec = embedder.encode([query], convert_to_numpy=True)[0].tolist()
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

@app.get("/")
def root():
    return {
        "message": "Welcome to PranayAI 🚀",
        "routes": ["/health", "/chat", "/chat-image", "/ingest", "/list", "/delete"],
        "note": "This is the API backend. Use /chat or /chat-image for AI responses."
    }

@app.get("/health")
def health():
    return {"ok": True, "anthropic_ready": anthropic_client is not None, "model": CLAUDE_MODEL}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    err = require_anthropic()
    if err: return ChatResponse(reply=err)

    user_content = [{"type": "text", "text": req.message}]
    context_blocks = []
    sources = []

    if req.use_rag:
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

# ---------- Data management: ingest / list / delete ---------- #

@app.post("/ingest")
async def ingest(files: List[UploadFile] = File(...)):
    """
    Upload one or more files. Dedupe-by-filename:
    - Before inserting, delete any existing chunks where {"source": filename}.
    - Create stable chunk IDs based on filename-hash + chunk index.
    """
    report: List[Dict[str, Any]] = []

    for f in files:
        filename = f.filename
        # Delete any previous chunks for this source
        try:
            collection.delete(where={"source": filename})
        except Exception:
            # OK if nothing to delete
            pass

        # Read & chunk
        text = read_any_file(f)
        chunks = chunk_text(text)
        if not chunks:
            report.append({"file": filename, "chunks": 0, "status": "empty-or-unreadable"})
            continue

        # Embed & upsert with stable IDs
        vecs = embed_texts(chunks)
        doc_ns = stable_doc_id(filename)
        ids = [f"{doc_ns}-{i}" for i in range(len(chunks))]
        metas = [{"source": filename, "chunk": i} for i in range(len(chunks))]

        collection.add(ids=ids, documents=chunks, embeddings=vecs, metadatas=metas)
        report.append({"file": filename, "chunks": len(chunks), "status": "ingested"})

    return {"ingested": report}

@app.get("/list")
def list_sources():
    """
    Return a compact list of sources (filenames) currently in the collection.
    """
    # Chroma doesn't expose a native "distinct" list; fetch a sample and group
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
    """
    Delete all chunks for a given source (filename).
    """
    try:
        collection.delete(where={"source": source})
        return {"deleted": source}
    except Exception as e:
        return {"deleted": False, "error": str(e)}
