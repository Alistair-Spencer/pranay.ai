import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import jwt

# -----------------------
# ENV + CLIENTS
# -----------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_INPUT_MODEL = os.getenv("OPENAI_INPUT_MODEL", "gpt-3.5-turbo")
OPENAI_OUTPUT_MODEL = os.getenv("OPENAI_OUTPUT_MODEL", "gpt-4o")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", "change_this_to_a_long_random_secret")
PORT = int(os.getenv("PORT", "8000"))

if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY is not set. The /chat route will 500.")

client = OpenAI(api_key=OPENAI_API_KEY)

# in-memory db (Render starter only - we replace w/ disk/db later)
USERS: Dict[str, Dict[str, Any]] = {}
SESSIONS: Dict[str, str] = {}
CHATS: Dict[str, List[Dict[str, Any]]] = {}
PROJECTS: Dict[str, List[Dict[str, Any]]] = {}
USER_BG: Dict[str, str] = {}

# structure:
# USERS[user_id] = {
#    "name": "...",
#    "email": "...",
#    "picture": "...(or default)",
# }
#
# CHATS[user_id] = [
#    {
#      "id": "chat_123",
#      "title": "Bio Unit 3",
#      "created_at": "...iso...",
#      "messages": [
#           {"role":"user","text":"...","ts":"..."},
#           {"role":"assistant","text":"...","ts":"..."},
#      ]
#    },
#    ...
# ]
#
# PROJECTS[user_id] = [
#    {"id":"proj_...","name":"Math Study"},
#    ...
# ]
#
# USER_BG[user_id] = "/web/bg2.jpg" or "none"

def new_user(email: str, name: str, picture: str = "/web/logo.png") -> str:
    """
    Create a new user if not exists and return user_id.
    """
    for uid, data in USERS.items():
        if data["email"].lower() == email.lower():
            return uid

    user_id = str(uuid.uuid4())
    USERS[user_id] = {
        "name": name,
        "email": email,
        "picture": picture,
    }
    CHATS[user_id] = []
    PROJECTS[user_id] = [
        {"id": str(uuid.uuid4()), "name": "Math Study"},
        {"id": str(uuid.uuid4()), "name": "Bio Unit 3"},
        {"id": str(uuid.uuid4()), "name": "History DBQ Draft"},
    ]
    USER_BG[user_id] = "none"
    return user_id


def create_session(user_id: str) -> str:
    sess_id = str(uuid.uuid4())
    SESSIONS[sess_id] = user_id
    return sess_id


def get_user_id_from_cookie(request: Request) -> Optional[str]:
    sess_id = request.cookies.get("session_id")
    if not sess_id:
        return None
    return SESSIONS.get(sess_id)


def require_user(request: Request) -> str:
    uid = get_user_id_from_cookie(request)
    if not uid:
        raise HTTPException(status_code=401, detail="Not signed in")
    return uid


# -----------------------
# FASTAPI APP
# -----------------------

app = FastAPI()

# Allow browser JS from same origin to talk to API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session middleware (used for potential google auth handoff etc)
app.add_middleware(
    SessionMiddleware,
    secret_key=JWT_SECRET,
    same_site="lax",
    https_only=True,
)

# serve /web/* as static
app.mount("/web", StaticFiles(directory="web"), name="web")


# -----------------------
# UTIL
# -----------------------

def friendly_timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"


def pick_or_create_chat(user_id: str) -> Dict[str, Any]:
    """
    Grab newest chat or create a brand new one called 'New chat'.
    """
    if user_id not in CHATS:
        CHATS[user_id] = []

    if len(CHATS[user_id]) == 0:
        c = {
            "id": str(uuid.uuid4()),
            "title": "New chat",
            "created_at": friendly_timestamp(),
            "messages": [],
        }
        CHATS[user_id].insert(0, c)
        return c
    return CHATS[user_id][0]


def summarize_title(history: List[Dict[str, Any]]) -> str:
    """
    quick dumb heuristic: look at first user message and shorten to 6 words
    """
    for m in history:
        if m["role"] == "user":
            words = m["text"].strip().split()
            return " ".join(words[:6])
    return "New chat"


async def call_openai(user_text: str, image_data_b64: Optional[str]) -> str:
    """
    Calls OpenAI. If image_data_b64 is provided, ask GPT-4o vision-style.
    Otherwise do normal text.
    """
    if not OPENAI_API_KEY:
        return "[OpenAI key not configured]"

    # message list for model
    msgs = []

    # system prompt w/ safe school policy
    msgs.append({
        "role": "system",
        "content": (
            "You are PranayAI, a study assistant for students in Poway Unified. "
            "You help explain, you don't just give final answers to turn in. "
            "Always encourage using results responsibly."
        )
    })

    # user block
    if image_data_b64:
        # vision style prompt
        # NOTE: true vision multimodal with OpenAI REST is different format
        # here we just tell the model there's an image, but not actually sending bytes yet,
        # because that's a separate upload route we'd wire later.
        msgs.append({
            "role": "user",
            "content": f"[Image attached - base64 not fully wired yet]\n{user_text}"
        })
    else:
        msgs.append({
            "role": "user",
            "content": user_text
        })

    # Use output model for final reasoning (gpt-4o)
    completion = client.chat.completions.create(
        model=OPENAI_OUTPUT_MODEL,
        messages=msgs,
        temperature=0.4,
    )

    # new-style client returns .choices[0].message.content
    return completion.choices[0].message.content if completion.choices else "[no response]"


# -----------------------
# ROUTES
# -----------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    # return the built React-style HTML we wrote
    with open("web/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/me")
async def me(request: Request):
    uid = get_user_id_from_cookie(request)
    if uid and uid in USERS:
        u = USERS[uid]
        return {
            "logged_in": True,
            "user": {
                "name": u["name"],
                "email": u["email"],
                "picture": u["picture"],
            },
            "background": USER_BG.get(uid, "none"),
        }
    else:
        return {
            "logged_in": False,
            "user": {
                "name": "Guest",
                "email": "Not signed in",
                "picture": "/web/logo.png",
            },
            "background": "none",
        }


class ChatRequest(BaseModel):
    message: str
    image_b64: Optional[str] = None
    chat_id: Optional[str] = None


@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    uid = get_user_id_from_cookie(request)

    # if not signed in, let them still chat but it's "guest" in memory
    guest_mode = False
    if not uid:
        guest_mode = True
        uid = "GUEST"
        if uid not in USERS:
            USERS[uid] = {
                "name": "Guest",
                "email": "guest@local",
                "picture": "/web/logo.png",
            }
        if uid not in CHATS:
            CHATS[uid] = []
        if uid not in USER_BG:
            USER_BG[uid] = "none"
        if uid not in PROJECTS:
            PROJECTS[uid] = [
                {"id": str(uuid.uuid4()), "name": "Math Study"},
                {"id": str(uuid.uuid4()), "name": "Bio Unit 3"},
                {"id": str(uuid.uuid4()), "name": "History DBQ Draft"},
            ]

    # pick chat
    if req.chat_id:
        # find existing
        chat_obj = None
        for c in CHATS[uid]:
            if c["id"] == req.chat_id:
                chat_obj = c
                break
        if chat_obj is None:
            # create new if not found
            chat_obj = {
                "id": req.chat_id,
                "title": "New chat",
                "created_at": friendly_timestamp(),
                "messages": [],
            }
            CHATS[uid].insert(0, chat_obj)
    else:
        chat_obj = pick_or_create_chat(uid)

    # store user message
    user_msg = {
        "role": "user",
        "text": req.message,
        "ts": friendly_timestamp(),
    }
    chat_obj["messages"].append(user_msg)

    # call model
    ai_text = await call_openai(req.message, req.image_b64)

    # store assistant message
    asst_msg = {
        "role": "assistant",
        "text": ai_text,
        "ts": friendly_timestamp(),
    }
    chat_obj["messages"].append(asst_msg)

    # update chat title if still default
    if chat_obj["title"] == "New chat":
        chat_obj["title"] = summarize_title(chat_obj["messages"])

    return {
        "chat_id": chat_obj["id"],
        "assistant": ai_text,
        "ts": asst_msg["ts"],
        "guest_mode": guest_mode,
    }


@app.get("/chats")
async def list_chats(request: Request):
    uid = get_user_id_from_cookie(request)
    if not uid:
        uid = "GUEST"
    arr = []
    for c in CHATS.get(uid, []):
        arr.append({
            "id": c["id"],
            "title": c["title"],
            "created_at": c["created_at"]
        })
    return arr


@app.get("/chat/{chat_id}")
async def get_chat(chat_id: str, request: Request):
    uid = get_user_id_from_cookie(request)
    if not uid:
        uid = "GUEST"

    for c in CHATS.get(uid, []):
        if c["id"] == chat_id:
            return {
                "id": c["id"],
                "title": c["title"],
                "messages": c["messages"],
            }
    raise HTTPException(status_code=404, detail="chat not found")


@app.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str, request: Request):
    uid = require_user(request)
    CHATS[uid] = [c for c in CHATS.get(uid, []) if c["id"] != chat_id]
    return {"ok": True}


class NewProjectReq(BaseModel):
    name: str


@app.post("/projects")
async def create_project(req: NewProjectReq, request: Request):
    uid = get_user_id_from_cookie(request)
    if not uid:
        uid = "GUEST"
    if uid not in PROJECTS:
        PROJECTS[uid] = []
    proj_id = str(uuid.uuid4())
    PROJECTS[uid].insert(0, {"id": proj_id, "name": req.name or "Untitled"})
    return {"id": proj_id, "name": req.name}


@app.get("/projects")
async def list_projects(request: Request):
    uid = get_user_id_from_cookie(request)
    if not uid:
        uid = "GUEST"
    return PROJECTS.get(uid, [])


class BGReq(BaseModel):
  background_url: str


@app.post("/set-background")
async def set_background(req: BGReq, request: Request):
    uid = get_user_id_from_cookie(request)
    if not uid:
        uid = "GUEST"
    USER_BG[uid] = req.background_url
    return {"ok": True}


@app.get("/background")
async def get_background(request: Request):
    uid = get_user_id_from_cookie(request)
    if not uid:
        uid = "GUEST"
    return {"background_url": USER_BG.get(uid, "none")}


@app.post("/auth/manual")
async def manual_auth(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    # password not actually validated in this toy version
    user_id = new_user(email=email, name=name, picture="/web/logo.png")
    sess_id = create_session(user_id)

    resp = RedirectResponse(url="/", status_code=302)
    # cookie so browser stays signed in
    resp.set_cookie("session_id", sess_id, httponly=True, samesite="lax")
    return resp


@app.get("/logout")
async def do_logout(request: Request):
    sess_id = request.cookies.get("session_id")
    if sess_id in SESSIONS:
        del SESSIONS[sess_id]
    resp = RedirectResponse(url="/", status_code=302)
    resp.delete_cookie("session_id")
    return resp


# basic help/policy for the modal
@app.get("/help")
async def help_page():
    return {
        "title": "Responsible Use Policy",
        "body": [
            "PranayAI is here to explain, tutor, and help you study.",
            "Do not turn in AI-generated text as your own graded work unless your teacher gave permission.",
            "No harassment, hate, self-harm, or illegal content.",
            "This service is categorized as Educational/Study Support — not gaming, not adult, not unknown.",
        ],
        "district_note": "Built for students to learn how and why, not just copy answers.",
    }
