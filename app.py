import os
import re
import uuid
from typing import Dict, Any, List, Optional

import requests
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI

# env
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="PranayAI")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve static frontend files from ./web
app.mount("/static", StaticFiles(directory="web"), name="static")

# ---------- DEBUG ROUTE so we can confirm deploy ----------
@app.get("/test-alive")
async def test_alive():
    # if you can hit /test-alive in browser, you're definitely running THIS code
    return {"status": "running-new-code", "note": "if you see this, deploy is correct"}


# ---------- FRONTEND ROUTE (home page) ----------
@app.get("/")
async def root_page():
    # serve index.html from /web
    return FileResponse("web/index.html")


# ---------- MODELS / SCHEMAS ----------
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    easter_egg: bool

class GoogleLoginRequest(BaseModel):
    id_token: str

class LoginResponse(BaseModel):
    token: str
    username: str

class HistoryPayload(BaseModel):
    conversations: List[Dict[str, Any]]


# ---------- MEMORY ----------
sessions: Dict[str, str] = {}
stored_conversations: Dict[str, Any] = {}


# ---------- EASTER EGGS ----------
def check_easter_eggs(user_text: str) -> Optional[str]:
    lowered = user_text.lower().strip()

    jd_pattern = r"\b(hi|hey|hello|yo)\s+i[' ]?m\s+jd\b"
    if re.search(jd_pattern, lowered):
        return "hey jd I heard you’re trash at ap bio."

    pranay_pattern = r"\b(my name is|i am|i'm|im|this is)\s+pranay\b"
    if re.search(pranay_pattern, lowered):
        return "I can't help you because you are too bad at Clash Royale."

    if "mason richards" in lowered:
        return "it's slim time"

    return None


def normal_ai_response(user_text: str) -> str:
    completion = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You are PranayAI. You respond like ChatGPT but cleaner. "
                    "Explain like you're talking to a smart friend. "
                    "Be direct, clear, not cringe, no fake business talk."
                ),
            },
            {
                "role": "user",
                "content": user_text,
            },
        ],
    )

    for item in completion.output:
        if item.type == "message":
            parts = []
            for c in item.content:
                if getattr(c, "type", None) == "output_text":
                    parts.append(c.text)
            if parts:
                return "".join(parts)

    return "Sorry, something went wrong generating a response."


def get_username_from_auth(authorization_header: Optional[str]) -> str:
    if (
        authorization_header is None
        or not authorization_header.lower().startswith("bearer ")
    ):
        raise HTTPException(status_code=401, detail="not signed in")

    token = authorization_header.split(" ", 1)[1].strip()
    if token not in sessions:
        raise HTTPException(status_code=401, detail="invalid token")

    return sessions[token]


def verify_google_id_token(id_token: str) -> str:
    jwks = requests.get("https://www.googleapis.com/oauth2/v3/certs").json()
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header["kid"]

    public_key = None
    for key in jwks["keys"]:
        if key["kid"] == kid:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            break

    if public_key is None:
        raise HTTPException(status_code=401, detail="no matching google public key")

    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"google token invalid: {e}")

    username = (
        payload.get("name")
        or payload.get("email")
        or payload.get("sub")
        or "user"
    )

    return username


# ---------- API ROUTES ----------
@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    user_msg = body.message

    egg_reply = check_easter_eggs(user_msg)
    if egg_reply is not None:
        return JSONResponse(
            content={
                "response": egg_reply,
                "easter_egg": True,
            }
        )

    ai_reply = normal_ai_response(user_msg)
    return JSONResponse(
        content={
            "response": ai_reply,
            "easter_egg": False,
        }
    )


@app.post("/google-login", response_model=LoginResponse)
async def google_login(body: GoogleLoginRequest):
    username = verify_google_id_token(body.id_token)

    token = str(uuid.uuid4())
    sessions[token] = username

    if username not in stored_conversations:
        stored_conversations[username] = []

    return {
        "token": token,
        "username": username,
    }


@app.get("/history")
async def get_history(authorization: str = Header(None)):
    username = get_username_from_auth(authorization)
    convo_list = stored_conversations.get(username, [])
    return {"conversations": convo_list}


@app.post("/history")
async def save_history(payload: HistoryPayload, authorization: str = Header(None)):
    username = get_username_from_auth(authorization)

    if not isinstance(payload.conversations, list):
        raise HTTPException(status_code=400, detail="invalid conversations format")

    stored_conversations[username] = payload.conversations
    return {"ok": True}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "gpt-4o-mini",
        "easter_eggs_active": True,
        "notes": "JD / Pranay / Mason rules live. Google login + autosave ready.",
    }
