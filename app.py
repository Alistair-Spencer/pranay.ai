import os
import uuid
import shutil
import sqlite3
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, Form, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from openai import OpenAI

from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

# -------------------------------------------------
# ENV / SETUP
# -------------------------------------------------

load_dotenv()

OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL         = os.getenv("OPENAI_OUTPUT_MODEL", "gpt-4o")
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "https://www.pranayai.com/google-callback")
JWT_SECRET           = os.getenv("JWT_SECRET", "dev-change-this")
UPLOADS_DIR          = os.getenv("UPLOADS_DIR", "uploads")
DB_DIR               = "data"
DB_PATH              = os.path.join(DB_DIR, "pranayai.db")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs("web", exist_ok=True)

app = FastAPI(title="PranayAI", docs_url=None, redoc_url=None)

# CORS - loosen now, you can tighten later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session cookie
app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)

# static mount for uploaded files and backgrounds
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/web", StaticFiles(directory="web"), name="web")

client = OpenAI(api_key=OPENAI_API_KEY)

# OAuth (Google)
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

# -------------------------------------------------
# DB SETUP
# -------------------------------------------------

def db_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = db_conn()
    c = conn.cursor()

    # users (email is key)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        name TEXT,
        picture TEXT
    )
    """)

    # chats
    c.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        title TEXT,
        created_at TEXT,
        FOREIGN KEY(user_email) REFERENCES users(email)
    )
    """)

    # messages
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

    # backgrounds
    c.execute("""
    CREATE TABLE IF NOT EXISTS backgrounds (
        user_email TEXT PRIMARY KEY,
        bg_url TEXT
    )
    """)

    # projects
    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        title TEXT,
        created_at TEXT,
        FOREIGN KEY(user_email) REFERENCES users(email)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def now_iso():
    return datetime.now().isoformat()

def get_session_user(request: Request):
    # session["user"] looks like {email, name, picture}
    u = request.session.get("user")
    if u:
        return u
    # allow guest mode:
    # if no user in session, create a guest id in-session
    if not request.session.get("guest_id"):
        request.session["guest_id"] = f"guest-{uuid.uuid4().hex[:10]}"
    return {
        "email": request.session["guest_id"] + "@guest.local",
        "name": "Guest",
        "picture": ""
    }

def set_session_user(request: Request, email: str, name: str, picture: str = ""):
    request.session["user"] = {
        "email": email,
        "name": name,
        "picture": picture
    }

def is_guest(user_dict):
    return user_dict["email"].endswith("@guest.local")

def upsert_user(email: str, name: str, picture: str = ""):
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

def create_chat(user_email: str, title_hint: str = "New chat"):
    conn = db_conn()
    c = conn.cursor()
    created = now_iso()
    c.execute(
        "INSERT INTO chats (user_email, title, created_at) VALUES (?,?,?)",
        (user_email, title_hint[:60], created)
    )
    chat_id = c.lastrowid
    conn.commit()
    conn.close()
    return chat_id

def get_chats_for_user(user_email: str):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, title, created_at FROM chats WHERE user_email=? ORDER BY id DESC",
        (user_email,)
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"id": rid, "title": t or "New chat", "created_at": ts}
        for (rid, t, ts) in rows
    ]

def get_chat_owner_email(chat_id: int):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT user_email FROM chats WHERE id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_chat_title(chat_id: int, user_email: str, new_title: str):
    conn = db_conn()
    c = conn.cursor()
    # check ownership
    c.execute("SELECT id FROM chats WHERE id=? AND user_email=?", (chat_id, user_email))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    c.execute("UPDATE chats SET title=? WHERE id=?", (new_title[:60], chat_id))
    conn.commit()
    conn.close()

def add_message(chat_id: int, role: str, content: str, msg_type: str = "text"):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (chat_id, role, content, msg_type, created_at) VALUES (?,?,?,?,?)",
        (chat_id, role, content, msg_type, now_iso())
    )
    conn.commit()
    conn.close()

def get_messages(chat_id: int, user_email: str):
    # check chat ownership
    owner = get_chat_owner_email(chat_id)
    if owner != user_email:
        return []
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT role, content, msg_type, created_at FROM messages WHERE chat_id=? ORDER BY id ASC",
        (chat_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"role": r, "content": ct, "msg_type": mt, "created_at": ts}
        for (r, ct, mt, ts) in rows
    ]

def delete_chat_row(chat_id: int, user_email: str):
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

def get_background(user_email: str):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT bg_url FROM backgrounds WHERE user_email=?", (user_email,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def set_background(user_email: str, bg_url: str):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO backgrounds (user_email, bg_url) VALUES (?,?)",
        (user_email, bg_url)
    )
    c.execute(
        "UPDATE backgrounds SET bg_url=? WHERE user_email=?",
        (bg_url, user_email)
    )
    conn.commit()
    conn.close()

def get_projects_for_user(user_email: str):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, title, created_at FROM projects WHERE user_email=? ORDER BY id DESC",
        (user_email,)
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"id": rid, "title": t, "created_at": ts}
        for (rid, t, ts) in rows
    ]

def create_project(user_email: str, title: str):
    conn = db_conn()
    c = conn.cursor()
    created = now_iso()
    c.execute(
        "INSERT INTO projects (user_email, title, created_at) VALUES (?,?,?)",
        (user_email, title[:100], created)
    )
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid

def rename_project(user_email: str, project_id: int, new_title: str):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM projects WHERE id=? AND user_email=?",
        (project_id, user_email)
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    c.execute(
        "UPDATE projects SET title=? WHERE id=?",
        (new_title[:100], project_id)
    )
    conn.commit()
    conn.close()
    return True

def delete_project_row(user_email: str, project_id: int):
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM projects WHERE id=? AND user_email=?",
        (project_id, user_email)
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    c.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return True

# -------------------------------------------------
# MODEL CALLS
# -------------------------------------------------

def call_model(messages):
    """
    messages: [{role:"user"/"assistant"/"system", content:"..."}]
    returns string response from the model.
    """
    if not OPENAI_API_KEY:
        return "Model is not configured (missing OPENAI_API_KEY)."

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
    )
    return resp.choices[0].message.content

def generate_title_from_first_user_msg(first_user_msg: str):
    """
    Ask model to summarize user's first message into a short chat title.
    You can keep this cheap because it's tiny text.
    """
    prompt = (
        "Summarize this request in 4 words max with no punctuation. "
        "Make it sound like a topic name, not a sentence:\n\n"
        f"{first_user_msg}"
    )
    result = call_model([
        {"role": "user", "content": prompt}
    ])
    # fallback
    if not result:
        return "New chat"
    return result.strip().replace("\n", " ")[:60]

# -------------------------------------------------
# ROUTES: FRONTEND SHELL
# -------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def serve_index():
    path = os.path.join("web", "index.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return HTMLResponse("<h1>Missing web/index.html</h1>", status_code=500)

@app.get("/health")
def health():
    return {"ok": True, "model": OPENAI_MODEL}

# -------------------------------------------------
# ROUTES: AUTH
# -------------------------------------------------

@app.get("/me")
def me(request: Request):
    u = request.session.get("user")
    if u:
        # logged in
        return {
            "logged_in": True,
            "user": {
                "id": u["email"],
                "name": u["name"],
                "email": u["email"],
                "picture": u.get("picture",""),
            }
        }
    # guest mode
    guest = get_session_user(request)
    return {
        "logged_in": False,
        "user": {
            "id": guest["email"],
            "name": guest["name"],
            "email": guest["email"],
            "picture": guest.get("picture",""),
        }
    }

@app.post("/manual-login")
async def manual_login(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(None)
):
    # no password check yet, acts as "sign up / sign in"
    upsert_user(email, name, "")
    set_session_user(request, email=email, name=name, picture="")
    return {"ok": True}

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/google-login")
async def google_login(request: Request):
    # If Google creds aren't set, don't 500, just tell frontend
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return JSONResponse(
            {"error": "google_not_configured"},
            status_code=500
        )
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)

@app.get("/google-callback")
async def google_callback(request: Request):
    # same guard
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return RedirectResponse(url="/")

    token = await oauth.google.authorize_access_token(request)
    userinfo = await oauth.google.get("userinfo", token=token)
    profile = userinfo.json()

    email   = profile.get("email")
    name    = profile.get("name","User")
    picture = profile.get("picture","")

    upsert_user(email, name, picture)
    set_session_user(request, email=email, name=name, picture=picture)

    return RedirectResponse(url="/")

# -------------------------------------------------
# ROUTES: CHATS / MESSAGES
# -------------------------------------------------

@app.get("/chats")
def list_chats(request: Request):
    user = get_session_user(request)
    user_email = user["email"]
    return {"chats": get_chats_for_user(user_email)}

@app.post("/chats/new")
def new_chat(request: Request):
    user = get_session_user(request)
    user_email = user["email"]
    chat_id = create_chat(user_email, "New chat")
    return {"chat_id": chat_id}

@app.post("/chats/delete")
async def chats_delete(request: Request):
    user = get_session_user(request)
    user_email = user["email"]
    body = await request.json()
    chat_id = body.get("chat_id")
    if not chat_id:
        return {"ok": False, "error": "chat_id required"}
    ok = delete_chat_row(int(chat_id), user_email)
    return {"ok": ok}

@app.get("/messages")
def get_chat_messages(request: Request, chat_id: int):
    user = get_session_user(request)
    user_email = user["email"]
    msgs = get_messages(chat_id, user_email)
    return {"messages": msgs}

@app.post("/chat")
async def chat_endpoint(
    request: Request,
    chat_id: str = Form(None),
    message: str = Form(None),
    image: UploadFile = File(None),
):
    """
    Handles both:
      - multipart/form-data with (chat_id?, message?, image?)
      - pure JSON {chat_id, message}
    We'll normalize so we always have final_chat_id and final_msg.
    Then we'll add to DB, call model, generate title (if first message),
    save assistant reply, return {response, chat_id, chat_title}.
    """
    user = get_session_user(request)
    user_email = user["email"]

    # if it's JSON, not multipart
    if "multipart/form-data" not in request.headers.get("content-type",""):
        data = await request.json()
        chat_id = data.get("chat_id")
        message = data.get("message","").strip()
        image = None

    # ensure chat exists
    if not chat_id:
        # create new chat with placeholder title
        new_id = create_chat(user_email, "New chat")
        chat_id = new_id

    # basic ownership check
    owner = get_chat_owner_email(int(chat_id))
    if owner != user_email:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    # save user's text
    txt = (message or "").strip()
    if txt:
        add_message(int(chat_id), "user", txt, "text")

    img_url = None
    if image:
        # store uploaded image file
        ext = image.filename.split(".")[-1].lower() if "." in image.filename else "bin"
        fname = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(UPLOADS_DIR, fname)
        with open(save_path, "wb") as buf:
            shutil.copyfileobj(image.file, buf)
        img_url = f"/uploads/{fname}"
        # record message of type "image"
        add_message(int(chat_id), "user", img_url, "image")

    # build full conversation for model
    # (simple: just dump all messages as text; images will be described by URL)
    history = get_messages(int(chat_id), user_email)
    openai_msgs = []
    for m in history:
        if m["msg_type"] == "image":
            # We'll just tell the model the user sent an image at URL.
            openai_msgs.append({
                "role": "user",
                "content": f"[User sent an image: {m['content']}]"
            })
        else:
            openai_msgs.append({
                "role": m["role"],
                "content": m["content"]
            })

    # call model
    ai_text = call_model(openai_msgs)

    if not ai_text:
        ai_text = "Sorry, I couldn't generate a response."

    # save assistant message
    add_message(int(chat_id), "assistant", ai_text, "text")

    # auto title logic:
    # if chat still has default-y title, try summarizing the FIRST user text msg as chat title
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT title FROM chats WHERE id=?", (chat_id,))
    row = c.fetchone()
    current_title = row[0] if row else "New chat"

    if not current_title or current_title == "New chat":
        # grab first user message in this chat
        c.execute("""
          SELECT content FROM messages
          WHERE chat_id=? AND role='user' AND msg_type='text'
          ORDER BY id ASC LIMIT 1
        """, (chat_id,))
        first_user_row = c.fetchone()
        if first_user_row:
            new_title = generate_title_from_first_user_msg(first_user_row[0])
            set_chat_title(int(chat_id), user_email, new_title)
            current_title = new_title

    conn.close()

    return {
        "chat_id": int(chat_id),
        "response": ai_text,
        "chat_title": current_title
    }

# -------------------------------------------------
# ROUTES: BACKGROUND
# -------------------------------------------------

@app.get("/get-background")
def get_bg(request: Request):
    user = get_session_user(request)
    bg = get_background(user["email"])
    return {"bg_url": bg or ""}

@app.post("/set-background")
async def set_bg(request: Request):
    user = get_session_user(request)
    data = await request.json()
    bg_url = data.get("bg_url","")
    set_background(user["email"], bg_url)
    return {"ok": True, "bg_url": bg_url}

@app.post("/upload-background")
async def upload_bg(request: Request, file: UploadFile = File(...)):
    user = get_session_user(request)
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    fname = f"bg-{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOADS_DIR, fname)
    with open(save_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    url = f"/uploads/{fname}"
    set_background(user["email"], url)
    return {"bg_url": url}

# -------------------------------------------------
# ROUTES: PROJECTS
# -------------------------------------------------

@app.get("/projects")
def list_projects(request: Request):
    user = get_session_user(request)
    projects = get_projects_for_user(user["email"])
    return {"projects": projects}

@app.post("/projects/new")
async def new_project(request: Request):
    user = get_session_user(request)
    body = await request.json()
    title = body.get("title","New project").strip() or "New project"
    pid = create_project(user["email"], title)
    return {"id": pid, "title": title, "created_at": now_iso()}

@app.post("/projects/rename")
async def rename_project_route(request: Request):
    user = get_session_user(request)
    body = await request.json()
    pid = body.get("project_id")
    new_title = body.get("title","").strip()
    if not pid or not new_title:
        return {"ok": False, "error": "project_id and title required"}
    ok = rename_project(user["email"], int(pid), new_title)
    return {"ok": ok}

@app.post("/projects/delete")
async def delete_project_route(request: Request):
    user = get_session_user(request)
    body = await request.json()
    pid = body.get("project_id")
    if not pid:
        return {"ok": False, "error": "project_id required"}
    ok = delete_project_row(user["email"], int(pid))
    return {"ok": ok}

# -------------------------------------------------
# ROUTES: HELP / POLICY
# -------------------------------------------------

@app.get("/help")
def help_info():
    return {
        "title": "Responsible Use & Academic Integrity",
        "for": "Poway Unified School District",
        "rules": [
            "This assistant is for learning support, explanations, brainstorming, and study guidance.",
            "Do not submit AI-generated answers as graded work unless your teacher says it’s allowed.",
            "Do not use this to harass others, cheat on tests, or get around school filters.",
            "All use may be logged to protect safety and academic integrity.",
            "This tool is categorized as Educational/Tutoring."
        ]
    }
