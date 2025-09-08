import os, base64
from typing import List, Optional, Any
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from anthropic import Anthropic

# ----------- ENV -----------
load_dotenv()
APP_TITLE = "PranayAI"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-haiku-20240307")  # text+vision model
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ----------- APP -----------
app = FastAPI(title=APP_TITLE)

# ----------- ROUTES -----------
@app.get("/", response_class=HTMLResponse)
def root():
    # Serve the single-file front-end (no /static needed)
    return INDEX_HTML

@app.get("/status")
def status():
    ok = bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant-"))
    return {"ok": ok, "model": MODEL, "brand": APP_TITLE}

class ImagePayload(BaseModel):
    data: str                                      # base64 only (no data: prefix)
    media_type: str = Field(default="image/jpeg")  # e.g. image/png
    name: Optional[str] = None

class ChatIn(BaseModel):
    message: str                                   # primary: TEXT CHAT
    images: Optional[List[ImagePayload]] = None    # optional photos
    max_tokens: int = 800

@app.post("/chat")
def chat(payload: ChatIn):
    if not ANTHROPIC_API_KEY:
        return JSONResponse({"error": "Missing ANTHROPIC_API_KEY"}, status_code=500)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # assemble content blocks
    content: List[Any] = []
    if payload.message:
        content.append({"type": "text", "text": payload.message})

    if payload.images:
        for img in payload.images:
            # validate base64
            try:
                base64.b64decode(img.data, validate=True)
            except Exception:
                return JSONResponse({"error": f"Invalid base64 for {img.name or 'image'}"}, status_code=400)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": img.media_type, "data": img.data}
            })

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=payload.max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        # collect text blocks
        text = "".join([blk.text for blk in resp.content if getattr(blk, "type", "") == "text"]).strip()
        return {"reply": text or "[empty response]"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

# ----------- INLINE FRONT-END (no static files required) -----------
INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>PranayAI</title>
<style>
:root{--bg:#06060a;--panel:#0d0f17;--text:#eef1ff;--muted:#a7b0d0;--border:#1b2030;--a1:#7aa2ff;--a2:#b97aff;--a3:#6ff3d6;}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;color:var(--text);
background:radial-gradient(1000px 600px at 20% -20%,#12203a 0%,transparent 60%),radial-gradient(1200px 700px at 80% -30%,#2a0f48 0%,transparent 65%),linear-gradient(180deg,#07080e 0%,#05060a 100%)}
.top{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;padding:12px 16px;
background:color-mix(in oklab,var(--panel) 92%,black 8%);border-bottom:1px solid var(--border);backdrop-filter:blur(10px) saturate(1.2)}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.2px}
.logo{width:26px;height:26px;border-radius:8px;display:inline-grid;place-items:center;color:#0b1030;font-weight:900;
background:conic-gradient(from 210deg,var(--a1),var(--a2),var(--a1));
box-shadow:0 0 22px rgba(122,162,255,.35),inset 0 0 12px rgba(255,255,255,.35)}
.service{color:var(--muted);font-size:13px}
.chat{max-width:880px;margin:0 auto;padding:18px 16px 140px}
.messages{display:grid;gap:12px;margin-bottom:16px}
.msg{border:1px solid var(--border);border-radius:16px;background:color-mix(in oklab,var(--panel) 96%,black 4%);
padding:14px 16px;animation:pop .25s ease-out;box-shadow:0 0 0 1px rgba(106,121,255,.05),0 10px 30px rgba(0,0,0,.3)}
.msg.user{border-color:color-mix(in oklab,var(--a1) 30%,var(--border));background:linear-gradient(180deg,rgba(122,162,255,.10),rgba(122,162,255,.03))}
.msg.assistant{border-color:color-mix(in oklab,var(--a2) 25%,var(--border));background:linear-gradient(180deg,rgba(185,122,255,.10),rgba(185,122,255,.03))}
.composer{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);width:min(880px,calc(100% - 24px));display:grid;gap:10px}
.upload{display:flex;align-items:center;gap:12px;padding:10px;border:1px dashed var(--border);border-radius:12px;background:color-mix(in oklab,var(--panel) 96%,black 4%)}
.ghost{background:transparent;border:1px solid var(--border);color:var(--text);border-radius:10px;padding:8px 10px;cursor:pointer}
.ghost:hover{border-color:color-mix(in oklab,var(--a3) 40%,var(--border));box-shadow:0 0 12px rgba(111,243,214,.12)}
.hint{color:var(--muted)}
.preview{display:flex;gap:8px;flex-wrap:wrap}
.thumb{width:64px;height:64px;border-radius:10px;overflow:hidden;position:relative;border:1px solid var(--border);box-shadow:0 8px 24px rgba(0,0,0,.3);animation:pop .2s ease-out}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb .x{position:absolute;top:2px;right:2px;width:18px;height:18px;border-radius:6px;background:rgba(0,0,0,.5);color:#fff;border:none;cursor:pointer;font-size:12px}
.inputrow{display:grid;grid-template-columns:1fr auto;gap:8px;border:1px solid var(--border);border-radius:14px;background:color-mix(in oklab,var(--panel) 95%,black 5%);padding:8px;box-shadow:0 0 32px rgba(122,162,255,.08),0 0 40px rgba(185,122,255,.06)}
textarea{resize:none;border:none;outline:none;background:transparent;color:var(--text);padding:10px 12px;font-size:15px;min-height:48px}
.send{position:relative;border:none;border-radius:10px;background:linear-gradient(135deg,var(--a1),var(--a2));color:#fff;font-weight:800;padding:10px 16px;cursor:pointer;overflow:hidden}
.send[disabled]{opacity:.55;cursor:not-allowed}
.send .pulse{position:absolute;inset:0;pointer-events:none;opacity:0;background:radial-gradient(120px 80px at 20% 50%,rgba(255,255,255,.35),transparent 50%),radial-gradient(120px 80px at 80% 50%,rgba(255,255,255,.35),transparent 50%);mix-blend-mode:screen}
.send:active .pulse{animation:pulse .45s ease-out}
.typing{display:inline-flex;gap:6px;align-items:center;opacity:.8}
.dot{width:6px;height:6px;border-radius:50%;background:var(--muted);animation:bounce 1.1s infinite ease-in-out}
.dot:nth-child(2){animation-delay:.15s}.dot:nth-child(3){animation-delay:.3s}
@keyframes pop{from{transform:translateY(6px);opacity:0}to{transform:none;opacity:1}}
@keyframes pulse{from{opacity:.75}to{opacity:0}}
@keyframes bounce{0%,80%,100%{transform:translateY(0);opacity:.6}40%{transform:translateY(-4px);opacity:1}}
@media(max-width:640px){.brand .text{display:none}}
</style>
</head>
<body>
<header class="top">
  <div class="brand"><span class="logo">P</span><span class="text">PranayAI</span></div>
  <div id="service" class="service">Checking status…</div>
</header>

<main class="chat">
  <div id="messages" class="messages"></div>

  <div class="composer">
    <div class="upload" id="dropZone">
      <input id="fileInput" type="file" accept="image/*" multiple hidden>
      <button id="chooseFile" class="ghost" type="button">＋ Add photos</button>
      <span class="hint">or drag & drop images here</span>
    </div>
    <div id="preview" class="preview"></div>

    <div class="inputrow">
      <textarea id="message" placeholder="Ask anything… (Ctrl/Cmd + Enter to send)"></textarea>
      <button id="sendBtn" class="send" type="button"><span>Send</span><span class="pulse"></span></button>
    </div>
  </div>
</main>

<script>
const $ = s => document.querySelector(s);
const messagesEl = $('#messages');
const input = $('#message');
const sendBtn = $('#sendBtn');
const chooseBtn = $('#chooseFile');
const fileInput = $('#fileInput');
const dropZone = $('#dropZone');
const preview = $('#preview');

let sending = false;
let queueImages = []; // {data, media_type, name}

function addMsg(text, who='assistant'){
  const div = document.createElement('div');
  div.className = 'msg ' + who;
  if (text === '__typing__'){
    div.innerHTML = '<span class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>';
    div.dataset.typing = '1';
  } else { div.textContent = text; }
  messagesEl.appendChild(div);
  div.scrollIntoView({behavior:'smooth', block:'end'});
  return div;
}
function updateSend(){ sendBtn.disabled = sending || input.value.trim().length===0; }
function handleFiles(list){
  [...list].forEach(file=>{
    if (!file.type.startsWith('image/')) return;
    const rd = new FileReader();
    rd.onload = ()=>{
      const b64 = rd.result.split(',')[1];
      const obj = {data:b64, media_type:file.type||'image/jpeg', name:file.name};
      queueImages.push(obj);
      const t = document.createElement('div'); t.className='thumb';
      const im = document.createElement('img'); im.src = `data:${obj.media_type};base64,${obj.data}`;
      const x = document.createElement('button'); x.className='x'; x.textContent='×';
      x.onclick = ()=>{ preview.removeChild(t); queueImages = queueImages.filter(q=>q!==obj); };
      t.appendChild(im); t.appendChild(x); preview.appendChild(t);
    };
    rd.readAsDataURL(file);
  });
}
chooseBtn.addEventListener('click', ()=>fileInput.click());
fileInput.addEventListener('change', e=>{ handleFiles(e.target.files); fileInput.value=''; });
;['dragenter','dragover'].forEach(evt=>dropZone.addEventListener(evt, e=>{ e.preventDefault(); dropZone.style.boxShadow='0 0 0 2px rgba(111,243,214,.3)'; }));
;['dragleave','drop'].forEach(evt=>dropZone.addEventListener(evt, e=>{ e.preventDefault(); dropZone.style.boxShadow='none'; }));
dropZone.addEventListener('drop', e=>handleFiles(e.dataTransfer.files));

input.addEventListener('input', updateSend);
input.addEventListener('keydown', e=>{
  if ((e.ctrlKey||e.metaKey) && e.key==='Enter'){ e.preventDefault(); send(); }
});
sendBtn.addEventListener('click', send);

async function send(){
  if (sendBtn.disabled) return;
  const text = input.value.trim();
  input.value=''; updateSend();

  // show user message + thumbnails
  const userDiv = addMsg(text,'user');
  if (queueImages.length){
    const strip = document.createElement('div');
    strip.style.display='flex'; strip.style.gap='8px'; strip.style.marginTop='8px';
    queueImages.forEach(q=>{
      const t = document.createElement('div'); t.className='thumb';
      const im = document.createElement('img'); im.src = `data:${q.media_type};base64,${q.data}`;
      t.appendChild(im); strip.appendChild(t);
    });
    userDiv.appendChild(strip);
  }

  const typing = addMsg('__typing__','assistant');
  sending = true; updateSend();
  try{
    const r = await fetch('/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ message:text, images:queueImages, max_tokens:800 })
    });
    const data = await r.json();
    typing.remove();
    addMsg(data.reply ? data.reply : ("Error: " + (data.error||"unknown")),'assistant');
  }catch(e){
    typing.remove(); addMsg("Network error: " + e.message,'assistant');
  }finally{
    sending = false; updateSend(); queueImages = []; preview.innerHTML=''; input.focus();
  }
}

(async function init(){
  try{
    const s = await (await fetch('/status')).json();
    document.getElementById('service').textContent = s.ok ? `OK · Model: ${s.model}` : 'API key missing';
  }catch{ document.getElementById('service').textContent = 'Status check failed'; }
  updateSend();
})();
</script>
</body>
</html>
"""
# ----------- DEV RUN -----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
