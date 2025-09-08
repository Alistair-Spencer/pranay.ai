const $ = (s)=>document.querySelector(s);
const messagesEl = $('#messages');
const input = $('#message');
const sendBtn = $('#sendBtn');
const chooseFileBtn = $('#chooseFile');
const fileInput = $('#fileInput');
const dropZone = $('#dropZone');
const preview = $('#preview');
const toast = $('#toast');

let sending = false;
let queueImages = []; // {data, media_type, name}

function toastMsg(t){
  toast.textContent = t;
  toast.classList.add('show');
  setTimeout(()=>toast.classList.remove('show'), 1400);
}

function addMsg(text, who='assistant'){
  const div = document.createElement('div');
  div.className = `msg ${who}`;
  if (text === '__typing__'){
    div.innerHTML = `<span class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>`;
    div.dataset.typing = '1';
  } else {
    div.textContent = text;
  }
  messagesEl.appendChild(div);
  div.scrollIntoView({behavior:'smooth', block:'end'});
  return div;
}

function addImageStrip(files){
  // render thumbnails under composer
  files.forEach(f=>{
    const wrap = document.createElement('div');
    wrap.className = 'thumb';
    const img = document.createElement('img');
    img.src = `data:${f.media_type};base64,${f.data}`;
    const x = document.createElement('button');
    x.className = 'x';
    x.textContent = '×';
    x.onclick = ()=>{
      preview.removeChild(wrap);
      queueImages = queueImages.filter(q=>q !== f);
    };
    wrap.appendChild(img); wrap.appendChild(x);
    preview.appendChild(wrap);
  });
}

function updateSend(){
  sendBtn.disabled = sending || input.value.trim().length===0;
}

function handleFiles(fileList){
  const readers = [];
  [...fileList].forEach(file=>{
    if (!file.type.startsWith('image/')) return;
    const rd = new FileReader();
    rd.onload = ()=>{
      const base64 = rd.result.split(',')[1]; // after data:...;base64,
      const obj = { data: base64, media_type: file.type || 'image/jpeg', name: file.name };
      queueImages.push(obj);
      addImageStrip([obj]);
    };
    rd.readAsDataURL(file);
    readers.push(rd);
  });
}

chooseFileBtn.addEventListener('click', ()=>fileInput.click());
fileInput.addEventListener('change', e=>{
  handleFiles(e.target.files);
  fileInput.value = '';
});

;['dragenter','dragover'].forEach(evt=>{
  dropZone.addEventListener(evt, e=>{
    e.preventDefault(); e.stopPropagation();
    dropZone.style.boxShadow = '0 0 0 2px rgba(111,243,214,.3)';
  });
});
;['dragleave','drop'].forEach(evt=>{
  dropZone.addEventListener(evt, e=>{
    e.preventDefault(); e.stopPropagation();
    dropZone.style.boxShadow = 'none';
  });
});
dropZone.addEventListener('drop', (e)=>{
  const files = e.dataTransfer.files;
  handleFiles(files);
});

input.addEventListener('input', updateSend);
input.addEventListener('keydown', (e)=>{
  if ((e.ctrlKey||e.metaKey) && e.key==='Enter'){ e.preventDefault(); send(); }
});
sendBtn.addEventListener('click', send);

async function send(){
  if (sendBtn.disabled) return;
  const text = input.value.trim();
  input.value = ''; updateSend();

  // Render user's message and any image previews inline in the chat
  const userDiv = addMsg(text, 'user');
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

  const typing = addMsg('__typing__', 'assistant');
  sending = true; updateSend();

  try{
    const r = await fetch('/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ message: text, images: queueImages, max_tokens: 800 })
    });
    const data = await r.json();
    typing.remove();
    if (data.reply){
      addMsg(data.reply, 'assistant');
    }else{
      addMsg("Error: " + (data.error||'unknown'), 'assistant');
    }
  }catch(e){
    typing.remove();
    addMsg("Network error: " + e.message, 'assistant');
  }finally{
    sending = false; updateSend();
    queueImages = []; preview.innerHTML = '';
    input.focus();
  }
}

(async function init(){
  try{
    const s = await (await fetch('/status')).json();
    $('#service').textContent = s.ok ? `OK • Model: ${s.model}` : 'API key missing';
    if(!s.ok) toastMsg('Add your Anthropic key to .env');
  }catch{
    $('#service').textContent = 'Status check failed';
  }
  updateSend();
})();
