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

# load env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_INPUT_MODEL = os.getenv("OPENAI_INPUT_MODEL", "gpt-3.5-turbo")
OPENAI_OUTPUT_MODEL = os.getenv("OPENAI_OUTPUT_MODEL", "gpt-4o")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-this")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in environment")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="PranayAI")

# CORS so browser JS can call /chat on same origin or from your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock to your domain later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the /web folder at root-level predictable paths
# /static/style.css, /static/script.js, /static/logo.png, etc.
app.mount("/static", StaticFiles(directory="web"), name="static")

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = "default"
    consent_ok: bool | None = True

class ChatResponse(BaseModel):
    response: str
    easter_egg: bool = False

class LoginRequest(BaseModel):
    token: str

def create_jwt(email: str):
    payload = {"email": email, "exp": time.time() + 60 * 60 * 24}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

@app.get("/")
async def serve_index():
    # send the HTML for the app shell
    return FileResponse("web/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/google-login")
async def google_login(body: LoginRequest):
    # in production you'd verify body.token against Google
    if not body.token:
        raise HTTPException(status_code=400, detail="Missing token")
    return {"jwt": create_jwt("user@example.com"), "status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest):
    """
    Main chat route.
    1. special JD easter egg
    2. run gpt-3.5-turbo to clean/interpret the user ask
    3. run gpt-4o to generate final nice answer
    """
    user_msg = (body.message or "").strip()
    lowered = user_msg.lower()

    # easter egg
    if "hi im jd" in lowered or "hi i'm jd" in lowered or "i’m jd" in lowered:
        return ChatResponse(
            response="hey jd, I heard you’re trash at ap bio.",
            easter_egg=True
        )

    # step 1: preprocess with cheaper model
    try:
        preprocess = client.chat.completions.create(
            model=OPENAI_INPUT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Rewrite the user's message so it's as clear and direct as possible. Keep intent the same."
                },
                {"role": "user", "content": user_msg},
            ],
        )
        processed = preprocess.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Input model failed: {e}")

    # step 2: final answer with nicer model
    try:
        completion = client.chat.completions.create(
            model=OPENAI_OUTPUT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PranayAI. You answer like a smart friend, direct and useful. "
                        "No corporate buzzwords. Be honest, clear, and helpful."
                    )
                },
                {"role": "user", "content": processed},
            ],
        )
        answer = completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Output model failed: {e}")

    return ChatResponse(response=answer, easter_egg=False)

@app.post("/generate-image")
async def generate_image(request: Request):
    """
    Future feature: image generation.
    Right now just placeholder to prove endpoint exists.
    """
    data = await request.json()
    prompt = data.get("prompt", "A futuristic tech wallpaper in dark purple light")
    try:
        image = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return {"url": image.data[0].url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")
