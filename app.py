import os, base64
from typing import List, Optional, Any
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from anthropic import Anthropic

load_dotenv()

APP_TITLE = "PranayAI"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-haiku-20240307")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

app = FastAPI(title=APP_TITLE)

# Static + templates
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/status")
def status():
    ok = bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant-"))
    return {"ok": ok, "model": MODEL, "brand": APP_TITLE}

# ---------- Chat API ----------
class ImagePayload(BaseModel):
    data: str                                      # base64 (no prefix)
    media_type: str = Field(default="image/jpeg")  # e.g., image/png
    name: Optional[str] = None

class ChatIn(BaseModel):
    message: str
    images: Optional[List[ImagePayload]] = None
    max_tokens: int = 800

@app.post("/chat")
async def chat(payload: ChatIn):
    if not ANTHROPIC_API_KEY:
        return JSONResponse({"error": "Missing ANTHROPIC_API_KEY"}, status_code=500)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Build Anthropic content blocks (text + optional images)
    content: List[Any] = []
    if payload.message:
        content.append({"type": "text", "text": payload.message})

    if payload.images:
        for img in payload.images:
            # Validate base64
            try:
                base64.b64decode(img.data, validate=True)
            except Exception:
                return JSONResponse({"error": f"Invalid base64 for {img.name or 'image'}"}, status_code=400)

            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.media_type,
                    "data": img.data
                }
            })

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=payload.max_tokens,
            messages=[{"role": "user", "content": content}],
        )

        text = ""
        for block in resp.content:
            if getattr(block, "type", "") == "text":
                text += block.text
        return {"reply": text.strip() or "[empty response]"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
