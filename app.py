import os
import re
import uuid
from typing import Dict, Any, List, Optional

import requests
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI

#
# ENV
#
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
if not GOOGLE_CLIENT_ID:
    print("WARNING: GOOGLE_CLIENT_ID not set (Google login will fail).")

client = OpenAI(api_key=OPENAI_API_KEY)

#
# APP + CORS
#
app = FastAPI(title="PranayAI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # lock to https://www.pranayai.com later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#
# STATIC FRONTEND
#
# Serve everything in /web under /static/*
app.mount("/static", StaticFiles(directory="web"), name="static")


#
# RUNTIME STATE (in-memory for now; resets on restart)
#
# sessions[token] = username
sessions: Dict[str, str] = {}

# stored_conversations[username] = [ {id, title, messages:[{role,text,easter?}]} ]
stored_conversations: Dict[str, Any] = {}

# user_consents[username or session_token] = True/False
# if no login yet, we'll temporarily bind to a temp_session_id in frontend localStorage
user_consents: Dict[str, bool] = {}


#
# REQUEST / RESPONSE MODELS
#
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # front-end unique local id
    consent_ok: Optional[bool] = None # did user check "I agree" box yet?

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


#
# EASTER EGG LOGIC
#
def check_easter_eggs(user_text: str) -> Optional[str]:
    t = user_text.lower().strip()

    # "hi im jd"
    jd_pattern = r"\b(hi|hey|hello|yo)\s+i[' ]?m\s+jd\b"
    if re.search(jd_pattern, t):
        return "hey jd I heard you’re trash at ap bio."

    # "i'm pranay"
    pranay_pattern = r"\b(my name is|i am|i'm|im|this is)\s+pranay\b"
    if re.search(pranay_pattern, t):
        return "I can't help you because you are too bad at Clash Royale."

    # mention mason richards
    if "mason richards" in t:
        return "it's slim time"

    return None


#
# AI RESPONSE
#
def normal_ai_response(user_text: str) -> str:
    """
    Call OpenAI chat.completions to answer normally.
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PranayAI. "
                        "You answer like a helpful, calm friend. "
                        "You speak clearly, like you're explaining something to a smart classmate over coffee. "
                        "You do not sound corporate or cringe. "
                        "Stay safe and do not help with cheating on graded work."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"There was an issue talking to the model ({e})."


#
# AUTH HELPERS
#
def get_username_from_auth(authorization_header: Optional[str]) -> str:
    """
    Pull username from Bearer token in Authorization header.
    """
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
    """
    Verify Google Sign-In ID token and return username (display name or email).
    """
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


#
# ROUTES
#

# serve frontend
@app.get("/")
async def root_page():
    return FileResponse("web/index.html")


# health ping
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "gpt-4o-mini",
        "easter_eggs_active": True,
    }


# chat
@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """
    Main message endpoint.
    We also track if the user gave 'consent_ok' (pledge box).
    """
    user_msg = body.message.strip()
    session_id = body.session_id or "anon"
    consent_ok = bool(body.consent_ok)

    # user must consent before we answer normal
    if not consent_ok and not user_consents.get(session_id, False):
        # store refusal state
        return JSONResponse(
            status_code=403,
            content={
                "response": (
                    "Please agree to the responsible use policy before messaging. "
                    "Open the menu at the bottom left, go to Settings, and confirm the pledge."
                ),
                "easter_egg": False,
            },
        )

    # mark them as pledged once
    if consent_ok:
        user_consents[session_id] = True

    # easter egg?
    egg_reply = check_easter_eggs(user_msg)
    if egg_reply is not None:
        return JSONResponse(
            content={"response": egg_reply, "easter_egg": True}
        )

    # normal AI
    ai_reply = normal_ai_response(user_msg)
    return JSONResponse(
        content={"response": ai_reply, "easter_egg": False}
    )


# google login
@app.post("/google-login", response_model=LoginResponse)
async def google_login(body: GoogleLoginRequest):
    username = verify_google_id_token(body.id_token)

    token = str(uuid.uuid4())
    sessions[token] = username

    if username not in stored_conversations:
        stored_conversations[username] = []

    return {"token": token, "username": username}


# get history
@app.get("/history")
async def get_history(authorization: str = Header(None)):
    username = get_username_from_auth(authorization)
    convo_list = stored_conversations.get(username, [])
    return {"conversations": convo_list}


# save history
@app.post("/history")
async def save_history(payload: HistoryPayload, authorization: str = Header(None)):
    username = get_username_from_auth(authorization)

    if not isinstance(payload.conversations, list):
        raise HTTPException(status_code=400, detail="invalid conversations format")

    stored_conversations[username] = payload.conversations
    return {"ok": True}


# image upload stub (called when user chooses "Upload image")
@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    return {"ok": True, "filename": file.filename}
