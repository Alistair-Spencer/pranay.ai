# api.py
import os
import io
import base64
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from anthropic import Anthropic
from dotenv import load_dotenv

# --- Load environment variables locally (Render will inject env directly) ---
load_dotenv()

# --- FastAPI app + CORS (allow all; tighten for production) ---
app = FastAPI(title="Pernai API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # set to your domain later (e.g., https://pernai.ai)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Anthropic client and model ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_API_KEY:
    # Don't crash; return clear error later if missing
    pass

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


# ----------------------------- Utilities ----------------------------- #

def _require_anthropic():
    if anthropic_client is None:
        return {
            "error": "Anthropic SDK not available or API key missing. "
                     "Set ANTHROPIC_API_KEY in your environment."
        }
    return None


def _extract_text_blocks(msg) -> str:
    """
    Claude returns a list of content blocks. We concatenate any text blocks.
    """
    if not msg or not getattr(msg, "content", None):
        return ""
    parts = []
    for block in msg.content:
        # Text blocks have .type == "text" and .text attribute
        txt = getattr(block, "text", "")
        if isinstance(txt, str):
            parts.append(txt)
    return "".join(parts).strip()


def _image_to_base64_jpeg(data: bytes) -> tuple[str, str]:
    """
    Normalize uploads to a compressed JPEG to keep requests fast and within limits.
    Returns (base64_str, media_type).
    """
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((2000, 2000))  # keeps aspect ratio
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


# ------------------------------- Models ------------------------------ #

class ChatRequest(BaseModel):
    message: str
    system: Optional[str] = None
    max_tokens: int = 800
    # If you later add retrieval, you can include top_k, filters, etc.


class ChatResponse(BaseModel):
    reply: str


# ------------------------------- Routes ------------------------------ #

@app.get("/health")
def health():
    ok = anthropic_client is not None
    return {"ok": True, "anthropic_ready": ok, "model": CLAUDE_MODEL}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Text-only chat endpoint. Frontend should POST JSON: { "message": "..." }
    """
    err = _require_anthropic()
    if err:
        return ChatResponse(reply=err["error"])

    # Build the messages for Claude
    user_content = [{"type": "text", "text": req.message}]
    system_prompt = req.system or "You are a helpful AI assistant. Be concise and accurate."

    msg = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=req.max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    reply_text = _extract_text_blocks(msg) or "(no response)"
    return ChatResponse(reply=reply_text)


@app.post("/chat-image", response_model=ChatResponse)
async def chat_image(
    file: UploadFile = File(...),
    prompt: str = Form("Extract the text from this image and solve/answer any questions shown. Be concise."),
    max_tokens: int = Form(1000)
):
    """
    Image chat endpoint. Send multipart/form-data with:
      - file: the image
      - prompt (optional): extra instruction for the model
      - max_tokens (optional)
    """
    err = _require_anthropic()
    if err:
        return ChatResponse(reply=err["error"])

    raw = await file.read()
    b64, media_type = _image_to_base64_jpeg(raw)

    content = [
        {"type": "text", "text": prompt},
        {"type": "image",
         "source": {
             "type": "base64",
             "media_type": media_type,
             "data": b64,
         }},
    ]

    msg = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    reply_text = _extract_text_blocks(msg) or "(no response)"
    return ChatResponse(reply=reply_text)
