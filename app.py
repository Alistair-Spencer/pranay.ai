import os
import time
import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# ===========================================
# Load environment variables
# ===========================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_INPUT_MODEL = os.getenv("OPENAI_INPUT_MODEL", "gpt-3.5-turbo")
OPENAI_OUTPUT_MODEL = os.getenv("OPENAI_OUTPUT_MODEL", "gpt-4o")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-this")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in .env or Render environment variables")

# ===========================================
# Initialize client & app
# ===========================================
client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="PranayAI")

# CORS (Frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your site later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend (index.html, etc.)
app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/")
async def root():
    """Serve main page."""
    return FileResponse("web/index.html")


# ===========================================
# Models
# ===========================================
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    consent_ok: bool = True


class ChatResponse(BaseModel):
    response: str
    easter_egg: bool = False


class LoginRequest(BaseModel):
    token: str


# ===========================================
# Helper: JWT creation for Google login
# ===========================================
def create_jwt(email: str):
    payload = {"email": email, "exp": time.time() + 60 * 60 * 24}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ===========================================
# Routes
# ===========================================
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest):
    """Main chat route: uses 3.5-turbo for input, GPT-4 for output."""
    user_msg = body.message.strip()
    lowered = user_msg.lower()

    # Easter egg for JD
    if "hi im jd" in lowered or "hi i'm jd" in lowered or "i’m jd" in lowered:
        return ChatResponse(response="hey jd, I heard you’re trash at ap bio.", easter_egg=True)

    # Step 1: pre-process input using GPT-3.5-Turbo
    try:
        preprocess = client.chat.completions.create(
            model=OPENAI_INPUT_MODEL,
            messages=[
                {"role": "system", "content": "Summarize or clean the user message for clarity."},
                {"role": "user", "content": user_msg},
            ],
        )
        processed = preprocess.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Input model failed: {e}")

    # Step 2: generate final response using GPT-4
    try:
        completion = client.chat.completions.create(
            model=OPENAI_OUTPUT_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are PranayAI — a helpful, direct, and honest assistant. "
                    "Speak naturally and clearly, like a real person explaining over coffee. "
                    "Avoid buzzwords or formal filler."
                )},
                {"role": "user", "content": processed},
            ],
        )
        answer = completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Output model failed: {e}")

    return ChatResponse(response=answer, easter_egg=False)


@app.post("/google-login")
async def google_login(body: LoginRequest):
    """Simulate Google sign-in with a fake token exchange (you’ll hook real Google later)."""
    token = body.token
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    # In a real setup, verify token with Google API.
    return {"jwt": create_jwt("user@example.com"), "status": "ok"}


@app.get("/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}


# ===========================================
# Future feature placeholders (image, moderation, etc.)
# ===========================================

@app.post("/generate-image")
async def generate_image(request: Request):
    """(Placeholder) Generate image with DALL-E or similar."""
    data = await request.json()
    prompt = data.get("prompt", "A beautiful AI-generated landscape")
    try:
        image = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
        return {"url": image.data[0].url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")
