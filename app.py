import os
import uuid
import sqlite3
import shutil
from datetime import datetime
from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

# ===== Load Environment Variables =====
load_dotenv()

app = FastAPI(title="PranayAI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET", "supersecret"))

# ===== Static & Files =====
if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ===== Database =====
DB_PATH = "data/pranayai.db"
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    name TEXT,
    picture TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    title TEXT,
    content TEXT,
    timestamp TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    name TEXT
)""")
conn.commit()
conn.close()

# ===== OpenAI =====
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ===== Google OAuth =====
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
)

# ===== ROUTES =====

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("web/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/google-login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/google-callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    email = user["email"]
    name = user.get("name", "User")
    picture = user.get("picture", "")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (email, name, picture) VALUES (?, ?, ?)", (email, name, picture))
    conn.commit()
    conn.close()

    request.session["user"] = {"email": email, "name": name, "picture": picture}
    return RedirectResponse(url="/")


@app.get("/me")
async def get_user(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse({"logged_in": False})
    return JSONResponse({"logged_in": True, "user": user})


@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    user = request.session.get("user")

    if not user_message:
        return JSONResponse({"error": "Message missing"}, status_code=400)

    # OpenAI GPT-4o response
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_OUTPUT_MODEL", "gpt-4o"),
        messages=[{"role": "user", "content": user_message}],
    )
    response_text = completion.choices[0].message.content

    if user:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO chats (user_email, title, content, timestamp) VALUES (?, ?, ?, ?)",
                  (user["email"], user_message[:30], response_text, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    return JSONResponse({"response": response_text})


@app.post("/upload-image")
async def upload_image(file: UploadFile):
    ext = file.filename.split(".")[-1]
    file_path = f"uploads/{uuid.uuid4()}.{ext}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"/{file_path}"}


@app.post("/set-background")
async def set_background(request: Request):
    data = await request.json()
    background_url = data.get("background_url")
    request.session["background"] = background_url
    return {"message": "Background updated"}


@app.get("/get-background")
async def get_background(request: Request):
    bg = request.session.get("background", None)
    return {"background": bg}


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


@app.get("/health")
async def health():
    return {"status": "running", "model": os.getenv("OPENAI_OUTPUT_MODEL")}
