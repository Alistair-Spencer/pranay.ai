/* ---------- helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const toast = (msg, kind="ok") => {
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(()=> t.remove(), 4000);
};
const bytes = (n) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024**2) return `${(n/1024).toFixed(1)} KB`;
  if (n < 1024**3) return `${(n/1024**2).toFixed(1)} MB`;
  return `${(n/1024**3).toFixed(1)} GB`;
};
const setHealth = (txt, ok=true) => {
  const el = $("#health");
  el.textContent = txt;
  el.style.background = ok ? "color-mix(in srgb, var(--brand) 20%, var(--surface))"
                           : "color-mix(in srgb, var(--danger) 25%, var(--surface))";
};

/* ---------- theme toggle ---------- */
(() => {
  const btn = $("#themeToggle");
  const key = "pranay_theme";
  const apply = (m) => document.documentElement.dataset.theme = m;
  const current = localStorage.getItem(key);
  if (current) apply(current);
  btn.addEventListener("click", () => {
    const now = (document.documentElement.dataset.theme === "light") ? "dark" : "light";
    apply(now);
    localStorage.setItem(key, now);
  });
})();

/* ---------- health check ---------- */
async function checkHealth(){
  try{
    const t0 = performance.now();
    const r = await fetch("/health");
    const t1 = performance.now();
    if (r.ok){
      setHealth(`online • ${Math.max(1, Math.round(t1 - t0))}ms`, true);
    } else {
      setHealth("degraded", false);
    }
  } catch {
    setHealth("offline", false);
  }
}
checkHealth();
setInterval(checkHealth, 20000);

/* ---------- ingest ---------- */
let pendingFiles = [];

function renderFileList(){
  const box = $("#fileList");
  if (!pendingFiles.length){ 
    box.classList.add("empty");
    box.textContent = "No files selected.";
    $("#ingestBtn").disabled = true;
    $("#clearBtn").disabled = true;
    return;
  }
  box.classList.remove("empty");
  box.innerHTML = "";
  pendingFiles.forEach((f, i) => {
    const row = document.createElement("div");
    row.className = "fileitem";
    row.innerHTML = `
      <div>📄</div>
      <div class="name">${f.name}</div>
      <div class="meta">${bytes(f.size)}</div>
      <button class="ghost" data-i="${i}">✕</button>
    `;
    row.querySelector("button").onclick = (e)=>{
      const idx = +e.currentTarget.dataset.i;
      pendingFiles.splice(idx,1);
      renderFileList();
    };
    box.appendChild(row);
  });
  $("#ingestBtn").disabled = false;
  $("#clearBtn").disabled = false;
}

function hookDropzone(){
  const dz = $("#dropzone");
  const input = $("#fileInput");

  const accept = (fs) => {
    const ok = Array.from(fs).filter(f => /\.(pdf|txt|md)$/i.test(f.name));
    const bad = Array.from(fs).filter(f => !/\.(pdf|txt|md)$/i.test(f.name));
    if (bad.length) toast(`Ignored ${bad.length} unsupported file(s). Use PDF/TXT/MD.`, "err");
    pendingFiles.push(...ok);
    renderFileList();
  };

  dz.addEventListener("dragover", (e)=>{ e.preventDefault(); dz.style.borderColor = "var(--brand)" });
  dz.addEventListener("dragleave", ()=> dz.style.borderColor = "var(--border)");
  dz.addEventListener("drop", (e)=>{
    e.preventDefault(); dz.style.borderColor = "var(--border)";
    accept(e.dataTransfer.files);
  });
  dz.addEventListener("click", ()=> input.click());
  input.addEventListener("change", ()=> accept(input.files));

  $("#clearBtn").onclick = ()=>{ pendingFiles = []; renderFileList(); };
}
hookDropzone();

async function ingest(){
  if (!pendingFiles.length) return;
  $("#ingestProgress").classList.remove("hidden");
  $(".bar").style.width = "0%";
  $("#ingestBtn").disabled = true;

  // Build one multipart request as your API expects multiple "files"
  const fd = new FormData();
  pendingFiles.forEach(f => fd.append("files", f, f.name));

  try{
    const res = await new Promise((resolve, reject)=>{
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/ingest");
      xhr.responseType = "text";
      xhr.upload.onprogress = (e)=>{
        if (e.lengthComputable){
          const pct = Math.round(e.loaded / e.total * 100);
          $(".bar").style.width = `${pct}%`;
        }
      };
      xhr.onload = ()=> resolve({ ok: (xhr.status>=200 && xhr.status<300), status: xhr.status, text: xhr.responseText });
      xhr.onerror = ()=> reject(new Error("Network error"));
      xhr.send(fd);
    });
    if (res.ok){
      toast("Ingestion complete");
      $(".bar").style.width = "100%";
      pendingFiles = [];
      renderFileList();
      await listDocs();
    } else {
      toast(`Ingest failed (${res.status})`, "err");
    }
  } catch(err){
    toast(`Ingest error: ${err.message}`, "err");
  } finally {
    $("#ingestProgress").classList.add("hidden");
    $("#ingestBtn").disabled = !pendingFiles.length;
  }
}
$("#ingestBtn").onclick = ingest;

/* ---------- list docs ---------- */
async function listDocs(){
  const box = $("#docs");
  box.textContent = "Loading…";
  try{
    const r = await fetch("/list");
    const txt = await r.text();
    // Try to parse JSON; if not JSON, just show text.
    let data = null;
    try { data = JSON.parse(txt); } catch {}
    box.innerHTML = "";
    if (data && Array.isArray(data)){
      if (!data.length){ box.classList.add("empty"); box.textContent = "No documents indexed yet."; return; }
      data.forEach((name) => {
        const row = document.createElement("div");
        row.className = "doc";
        row.innerHTML = `
          <div class="name">📄 ${name}</div>
          <div class="meta">indexed</div>
        `;
        box.appendChild(row);
      });
    } else {
      // Fallback render
      box.textContent = txt || "No documents indexed yet.";
    }
  } catch(e){
    box.textContent = "Could not fetch documents.";
    toast("Failed to fetch /list", "err");
  }
}
$("#refreshList").onclick = listDocs;
listDocs();

/* ---------- chat ---------- */
function pushMsg(role, text){
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "U" : "A";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.append(avatar, bubble);
  $("#chatLog").appendChild(row);
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
}
async function send(){
  const ta = $("#prompt");
  const q = ta.value.trim();
  if (!q) return;
  ta.value = "";
  pushMsg("user", q);
  const placeholder = "Thinking…";
  const id = Math.random().toString(36).slice(2);
  pushMsg("bot", placeholder);
  const botBubble = $$(".msg.bot .bubble").at(-1);

  try{
    const r = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ question: q })
    });
    const text = await r.text();
    botBubble.textContent = text;
    if (!r.ok) toast(`/chat ${r.status}`, "err");
  } catch (e){
    botBubble.textContent = "Error contacting server.";
    toast("Chat error: " + e.message, "err");
  }
}
$("#sendBtn").onclick = send;
$("#prompt").addEventListener("keydown", (e)=>{
  if (e.key === "Enter" && !e.shiftKey){
    e.preventDefault(); send();
  }
});
