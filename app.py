import os
import uuid
import shutil
import sqlite3
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from openai import OpenAI

from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse

from authlib.integrations.starlette_client import OAuth

# -------------------------
# ENV / CONSTANTS
# -------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_OUTPUT_MODEL", "gpt-4o")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://www.pranayai.com/google-callback")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-this")

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pranayai.db")

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")

# Make sure folders exist at startup
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs("web", exist_ok=True)

# -------------------------
# FASTAPI APP + MIDDLEWARE
# -------------------------

app = FastAPI(title="PranayAI", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # If you want to lock this down later you can
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session cookies for login
app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)

# static file serving for uploaded images
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# -------------------------
# DB INIT
# -------------------------

def db_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = db_conn()
    c = conn.cursor()

    # users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        name TEXT,
        picture TEXT
    )
    """)

    # chats table
    c.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        title TEXT,
        timestamp TEXT,
        FOREIGN KEY(user_email) REFERENCES users(email)
    )
    """)

    # messages table (so each chat can have many messages)
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        role TEXT,
        content TEXT,
        msg_type TEXT,
        created_at TEXT,
        FOREIGN KEY(chat_id) REFERENCES chats(id)
    )
    """)

    # backgrounds per user
    c.execute("""
    CREATE TABLE IF NOT EXISTS backgrounds (
        user_email TEXT PRIMARY KEY,
        bg_url TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# OPENAI CLIENT
# -------------------------

client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------
# GOOGLE OAUTH
# -------------------------

oauth = OAuth()

oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    access_token_url="https://oauth2.googleapis.com/token",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    api_base_url="https://www.googleapis.com/oauth2/v2/",
    client_kwargs={"scope": "openid email profile"},
)

# -------------------------
# HELPERS
# -------------------------

def get_session_user(request: Request):
    """Return dict {email, name, picture} or None."""
    return request.session.get("user")

def set_session_user(request: Request, email: str, name: str, picture: str = ""):
    request.session["user"] = {
        "email": email,
        "name": name,
        "picture": picture
    }

def require_user(request: Request):
    user = get_session_user(request)
    if not user:
        return None
    return user

def create_chat_if_needed(user_email: str, title_hint: str = "New chat"):
    """Create a new chat row and return its id."""
    conn = db_conn()
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute(
        "INSERT INTO chats (user_email, title, timestamp) VALUES (?,?,?)",
        (user_email, title_hint[:50], timestamp)
    )
    chat_id = c.lastrowid
    conn.commit()
    conn.close()
    return chat_id

def add_message(chat_id: int, role: str, content: str, msg_type: str = "text"):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (chat_id, role, content, msg_type, created_at) VALUES (?,?,?,?,?)",
        (chat_id, role, content, msg_type, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_chat_messages(chat_id: int, user_email: str):
    conn = db_conn()
    c = conn.cursor()
    # verify chat belongs to this user
    c.execute("SELECT id FROM chats WHERE id=? AND user_email=?", (chat_id, user_email))
    row = c.fetchone()
    if not row:
        conn.close()
        return []

    c.execute(
        "SELECT role, content, msg_type FROM messages WHERE chat_id=? ORDER BY id ASC",
        (chat_id,)
    )
    msgs = [{"role": r, "content": ct, "msg_type": mt} for (r, ct, mt) in c.fetchall()]
    conn.close()
    return msgs

def list_chats(user_email: str):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, title, timestamp FROM chats WHERE user_email=? ORDER BY id DESC",
        (user_email,)
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"id": chat_id, "title": title, "timestamp": ts}
        for (chat_id, title, ts) in rows
    ]

def delete_chat(user_email: str, chat_id: int):
    conn = db_conn()
    c = conn.cursor()
    # verify ownership
    c.execute("SELECT id FROM chats WHERE id=? AND user_email=?", (chat_id, user_email))
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    c.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    conn.commit()
    conn.close()
    return True

# -------------------------
# ROUTES
# -------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """
    Serve the frontend. We inject nothing here
    because the frontend will call /me, /chats, /get-background, etc.
    """
    index_path = os.path.join("web", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse("<h1>Missing web/index.html</h1>", status_code=500)

# ---- Auth ----

@app.get("/google-login")
async def google_login(request: Request):
    # real Google OAuth redirect
    return await oauth.google.authorize_redirect(
        request,
        GOOGLE_REDIRECT_URI
    )

@app.get("/google-callback")
async def google_callback(request: Request):
    # exchange auth code for tokens + profile
    token = await oauth.google.authorize_access_token(request)
    # token now has access_token/id_token etc
    userinfo = await oauth.google.get("userinfo", token=token)
    profile = userinfo.json()

    email = profile.get("email")
    name = profile.get("name", "User")
    picture = profile.get("picture", "")

    # upsert user in DB
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (email, name, picture) VALUES (?,?,?)",
        (email, name, picture)
    )
    c.execute(
        "UPDATE users SET name=?, picture=? WHERE email=?",
        (name, picture, email)
    )
    conn.commit()
    conn.close()

    # store session
    set_session_user(request, email=email, name=name, picture=picture)

    return RedirectResponse(url="/")

@app.post("/manual-login")
async def manual_login(request: Request, name: str = Form(...), email: str = Form(...)):
    """
    fallback login using name + email (no password enforcement right now)
    """
    if not name or not email:
        return JSONResponse({"error": "missing name or email"}, status_code=400)

    # upsert user
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (email, name, picture) VALUES (?,?,?)",
        (email, name, "")
    )
    c.execute(
        "UPDATE users SET name=? WHERE email=?",
        (name, email)
    )
    conn.commit()
    conn.close()

    set_session_user(request, email=email, name=name, picture="")
    return JSONResponse({"ok": True})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/me")
async def me(request: Request):
    user = get_session_user(request)
    if not user:
        return {"logged_in": False}
    return {
        "logged_in": True,
        "user": user
    }

# ---- Chat management ----

@app.get("/chats")
async def get_chats(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)

    chats_for_user = list_chats(user["email"])
    return {"chats": chats_for_user}

@app.post("/chats/new")
async def new_chat(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)

    chat_id = create_chat_if_needed(user["email"], "New chat")
    return {"chat_id": chat_id}

@app.post("/chats/delete")
async def remove_chat(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)

    data = await request.json()
    chat_id = data.get("chat_id")
    if not chat_id:
        return JSONResponse({"error": "chat_id required"}, status_code=400)

    ok = delete_chat(user["email"], int(chat_id))
    return {"deleted": ok}

@app.get("/chats/{chat_id}")
async def load_chat(chat_id: int, request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)

    msgs = get_chat_messages(chat_id, user["email"])
    return {"messages": msgs}

# ---- Chat with model ----

@app.post("/chat")
async def chat(request: Request):
    """
    Takes JSON:
    {
      "chat_id": number (optional),
      "message": string
    }
    If chat_id is missing, we'll create a new chat.
    """
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)

    data = await request.json()
    user_msg = data.get("message", "").strip()
    chat_id = data.get("chat_id")

    if not user_msg:
        return JSONResponse({"error": "empty message"}, status_code=400)

    # create chat if none
    if not chat_id:
        chat_id = create_chat_if_needed(user["email"], user_msg[:40] or "New chat")

    # store user's message
    add_message(chat_id, "user", user_msg, "text")

    # build conversation to send to OpenAI
    history = get_chat_messages(chat_id, user["email"])
    # convert to OpenAI format
    openai_msgs = []
    for m in history:
        if m["msg_type"] == "text":
            openai_msgs.append({"role": m["role"], "content": m["content"]})
        # we could extend for images later

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=openai_msgs,
    )
    ai_text = completion.choices[0].message.content

    # save assistant reply
    add_message(chat_id, "assistant", ai_text, "text")

    return {"chat_id": chat_id, "response": ai_text}

# ---- Image upload ----

@app.post("/upload-image")
async def upload_image(request: Request, file: UploadFile):
    """
    Returns a URL we can embed in chat. This does NOT yet run vision,
    but stores the file and gives you back a path.
    """
    # save file
    filename = f"{uuid.uuid4()}.{file.filename.split('.')[-1]}"
    save_path = os.path.join(UPLOADS_DIR, filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    url = f"/uploads/{filename}"
    return {"url": url}

# ---- Background preference ----

@app.post("/set-background")
async def set_background(request: Request):
    """
    body: {"bg_url": "..."}
    saves per-user background so it persists across reload
    """
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)

    data = await request.json()
    bg_url = data.get("bg_url", "")

    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO backgrounds (user_email, bg_url) VALUES (?,?)",
        (user["email"], bg_url)
    )
    c.execute(
        "UPDATE backgrounds SET bg_url=? WHERE user_email=?",
        (bg_url, user["email"])
    )
    conn.commit()
    conn.close()

    return {"ok": True}

@app.get("/get-background")
async def get_background(request: Request):
    user = require_user(request)
    if not user:
        return {"bg_url": ""}

    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT bg_url FROM backgrounds WHERE user_email=?",
        (user["email"],)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return {"bg_url": ""}
    return {"bg_url": row[0]}

# ---- Help / policy ----

@app.get("/help")
async def help_info():
    """
    This returns school-facing safety text. You can show this
    in your Help modal so teachers/admins see it's framed
    as academic support, not cheating.
    """
    return {
        "title": "Responsible Use & Academic Integrity",
        "for": "Poway Unified School District",
        "rules": [
            "This assistant is for learning support, explanations, brainstorming, and study guidance.",
            "Do not submit AI-generated answers as graded work unless your teacher says it’s allowed.",
            "Do not use this to break school rules, harass others, or access blocked content.",
            "All activity may be logged to improve safety and quality.",
            "This tool is categorized as Educational/Tutoring."
        ]
    }

# ---- Healthcheck ----

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": OPENAI_MODEL,
        "domain": "https://www.pranayai.com"
    }
