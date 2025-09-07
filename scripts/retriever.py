import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # allow 'from retriever import Retriever'
import os, re, glob
from dataclasses import dataclass
from typing import List, Dict, Any, Iterable

import chromadb
from pypdf import PdfReader

from sentence_transformers import SentenceTransformer

@dataclass
class DocChunk:
    text: str
    metadata: Dict[str, Any]

def _read_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join([(p.extract_text() or "") for p in reader.pages])

def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
    words, chunks, current, length = text.split(), [], [], 0
    for w in words:
        if length + len(w) + 1 > max_chars:
            chunks.append(" ".join(current))
            back = " ".join(current)[-overlap:].split()
            current, length = back[:], sum(len(x)+1 for x in back)
        current.append(w); length += len(w)+1
    if current: chunks.append(" ".join(current))
    return [re.sub(r"\s+", " ", c).strip() for c in chunks if c.strip()]

class Retriever:
    def __init__(self, persist_dir: str = "chroma_db", embeddings_backend: str = "local"):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="pranay_chunks", metadata={"hnsw:space": "cosine"}
        )
        # Local, free embedder (CPU ok)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")  # ~384-dim, fast

    def is_ready(self) -> bool:
        return self.collection.count() > 0

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def ingest(self, paths: Iterable[str]):
        docs, metas, ids = [], [], []
        for path in paths:
            ext = path.lower()
            if ext.endswith(".pdf"):
                content = _read_pdf(path)
            elif ext.endswith((".txt", ".md", ".markdown")):
                content = _read_text_file(path)
            else:
                continue

            for i, ch in enumerate(_chunk_text(content)):
                docs.append(ch)
                metas.append({"source": os.path.basename(path)})
                ids.append(f"{os.path.basename(path)}-{i}")

                if len(docs) >= 256:
                    self._add_batch(ids, docs, metas)
                    docs, metas, ids = [], [], []
        if docs:
            self._add_batch(ids, docs, metas)

    def _add_batch(self, ids, docs, metas):
        embeddings = self._embed(docs)
        self.collection.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)

    def search(self, query: str, k: int = 5) -> List[DocChunk]:
        if not query.strip():
            return []
        q_emb = self._embed([query])
        res = self.collection.query(query_embeddings=q_emb, n_results=k)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out: List[DocChunk] = []
        for text, meta, dist in zip(docs, metas, dists):
            out.append(
                DocChunk(
                    text=text,
                    metadata={
                        "source": meta.get("source", "unknown"),
                        "score": (1.0 - dist) if dist is not None else None,
                    },
                )
            )
        return out
