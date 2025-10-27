// ==================================================
// STATE
// ==================================================
let currentUser = null;     // {id,name,email,picture} or null
let chats = [];             // [{id,title,created_at}, ...]
let projects = [];          // [{id,title,created_at}, ...]
let activeChatId = null;
let pendingImageFile = null;
let pendingImagePreviewURL = null;

// DOM refs
const userRow            = document.getElementById("user-row");
const newChatBtn         = document.getElementById("new-chat-btn");
const chatListEl         = document.getElementById("chat-list");
const projectListEl      = document.getElementById("project-list");
const newProjectBtn      = document.getElementById("new-project-btn");

const mainPane           = document.getElementById("main-pane");
const messagesScroll     = document.getElementById("messages-scroll");
const pendingImageArea   = document.getElementById("pending-image-area");
const composerInput      = document.getElementById("composer-input");
const sendBtn            = document.getElementById("send-btn");

const plusTrigger        = document.getElementById("plus-trigger");
const plusMenuCard       = document.getElementById("plus-menu-card");
const imageUploadInput   = document.getElementById("image-upload-input");

const topMenuTrigger     = document.getElementById("top-menu-trigger");
const topMenuCard        = document.getElementById("top-menu-card");
const openBgPickerBtn    = document.getElementById("open-background-picker");
const openHelpBtn        = document.getElementById("open-help");
const logoutBtn          = document.getElementById("do-logout");

const authOverlay        = document.getElementById("auth-overlay");
const authClose          = document.getElementById("auth-close");
const googleAuthBtn      = document.getElementById("google-auth-btn");
const authSubmitBtn      = document.getElementById("auth-submit-btn");
const authNameInput      = document.getElementById("auth-name");
const authEmailInput     = document.getElementById("auth-email");
const authPassInput      = document.getElementById("auth-pass");

const bgOverlay          = document.getElementById("bg-overlay");
const bgClose            = document.getElementById("bg-close");
const bgChoices          = document.querySelectorAll(".bg-choice");
const bgUploadInput      = document.getElementById("bg-upload-input");

const helpOverlay        = document.getElementById("help-overlay");
const helpClose          = document.getElementById("help-close");
const helpBody           = document.getElementById("help-body");

// ==================================================
// INIT
// ==================================================
init();

async function init() {
  await loadUser();
  await loadProjects();
  await loadChats();
  await loadBackground();

  renderUserHeader();
  renderProjectList();
  renderChatList();

  if (chats.length > 0) {
    selectChat(chats[0].id);
  }

  setupGlobalEvents();
}

// ==================================================
// FETCH HELPERS
// ==================================================
async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}

async function postJSON(url, bodyObj) {
  const res = await fetch(url, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(bodyObj)
  });
  return res.json();
}

// ==================================================
// LOAD DATA FROM BACKEND
// ==================================================

async function loadUser() {
  try {
    const data = await getJSON("/me");
    currentUser = data.user || null;
  } catch (err) {
    console.error("loadUser", err);
    currentUser = null;
  }
}

async function loadChats() {
  try {
    const data = await getJSON("/chats");
    chats = Array.isArray(data.chats) ? data.chats : [];
  } catch (err) {
    console.error("loadChats", err);
    chats = [];
  }
}

async function loadProjects() {
  try {
    const data = await getJSON("/projects");
    projects = Array.isArray(data.projects) ? data.projects : [];
  } catch (err) {
    console.error("loadProjects", err);
    projects = [];
  }
}

async function loadBackground() {
  try {
    const data = await getJSON("/get-background");
    if (data.bg_url && data.bg_url !== "none") {
      mainPane.style.backgroundImage = `url('${data.bg_url}')`;
      mainPane.style.backgroundSize = "cover";
      mainPane.style.backgroundPosition = "center";
    } else {
      mainPane.style.backgroundImage = "";
      mainPane.style.backgroundColor = "#121212";
    }
  } catch (err) {
    console.error("loadBackground", err);
  }
}

// messages for a chat
async function fetchMessages(chatId) {
  const res = await fetch(`/messages?chat_id=${encodeURIComponent(chatId)}`);
  const data = await res.json();
  return Array.isArray(data.messages) ? data.messages : [];
}

// ==================================================
// RENDER UI
// ==================================================

function renderUserHeader() {
  if (currentUser && currentUser.email && !currentUser.email.endsWith("@guest.local")) {
    userRow.innerHTML = `
      <div class="user-inline">
        <img class="user-avatar" src="${escapeHtml(currentUser.picture || "/logo.png")}" />
        <div class="user-main">
          <div class="user-name">${escapeHtml(currentUser.name || "User")}</div>
          <div class="user-email">${escapeHtml(currentUser.email)}</div>
        </div>
      </div>
    `;
  } else {
    userRow.innerHTML = `
      <div class="user-inline">
        <img class="user-avatar" src="/logo.png" />
        <div class="user-main">
          <div class="user-name">Guest</div>
          <div class="user-email">Not signed in</div>
        </div>
      </div>
      <button class="signin-btn" id="open-auth">Sign in</button>
    `;
    const openAuthBtn = document.getElementById("open-auth");
    if (openAuthBtn) {
      openAuthBtn.addEventListener("click", showAuthModal);
    }
  }
}

function renderChatList() {
  chatListEl.innerHTML = "";
  if (!chats.length) {
    chatListEl.innerHTML = `<div class="empty-hint">No chats yet</div>`;
    return;
  }

  chats.forEach(chat => {
    const row = document.createElement("div");
    row.className = "list-row" + (chat.id === activeChatId ? " active" : "");
    row.innerHTML = `
      <div class="list-row-main">
        <div class="list-row-title">${escapeHtml(chat.title || "New chat")}</div>
        <div class="list-row-sub">${formatTimestamp(chat.created_at)}</div>
      </div>
      <button class="row-delete-btn" data-id="${chat.id}" title="Delete chat">✕</button>
    `;

    row.querySelector(".list-row-main").addEventListener("click", () => {
      selectChat(chat.id);
    });

    row.querySelector(".row-delete-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      await postJSON("/chats/delete", { chat_id: chat.id });
      await loadChats();
      if (activeChatId === chat.id) {
        activeChatId = null;
        messagesScroll.innerHTML = "";
      }
      renderChatList();
    });

    chatListEl.appendChild(row);
  });
}

function renderProjectList() {
  projectListEl.innerHTML = "";
  if (!projects.length) {
    projectListEl.innerHTML = `<div class="empty-hint">No projects yet</div>`;
    return;
  }

  projects.forEach(p => {
    const row = document.createElement("div");
    row.className = "list-row";
    row.innerHTML = `
      <div class="list-row-main">
        <div class="list-row-title">${escapeHtml(p.title)}</div>
        <div class="list-row-sub">${formatTimestamp(p.created_at)}</div>
      </div>
      <div class="proj-row-actions">
        <button class="row-rename-btn" data-id="${p.id}" title="Rename">✎</button>
        <button class="row-delete-btn" data-id="${p.id}" title="Delete">✕</button>
      </div>
    `;

    row.querySelector(".row-rename-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      const newName = prompt("Rename project:", p.title);
      if (!newName) return;
      await postJSON("/projects/rename", { project_id: p.id, title: newName });
      await loadProjects();
      renderProjectList();
    });

    row.querySelector(".row-delete-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      await postJSON("/projects/delete", { project_id: p.id });
      await loadProjects();
      renderProjectList();
    });

    projectListEl.appendChild(row);
  });
}

function renderMessagesBubbleList(msgs) {
  messagesScroll.innerHTML = "";

  msgs.forEach(m => {
    if (m.role === "assistant") {
      appendAIBubble(m.content, false); // false = not live (no typing anim)
    } else if (m.role === "user" && m.msg_type === "image") {
      appendUserImageBubble(m.content);
    } else if (m.role === "user") {
      appendUserBubble(m.content);
    }
  });

  scrollMessagesToBottom();
}

function appendUserBubble(text) {
  const wrap = document.createElement("div");
  wrap.className = "bubble bubble-user";
  wrap.textContent = text;
  messagesScroll.appendChild(wrap);
}

function appendUserImageBubble(imgUrl) {
  const wrap = document.createElement("div");
  wrap.className = "bubble bubble-user bubble-img";
  const img = document.createElement("img");
  img.src = imgUrl;
  wrap.appendChild(img);
  messagesScroll.appendChild(wrap);
}

function appendAIBubble(text, isTyping) {
  const wrap = document.createElement("div");
  wrap.className = "bubble bubble-ai";

  const body = document.createElement("div");
  body.className = "bubble-ai-body";

  if (isTyping) {
    body.innerHTML = `
      <div class="typing-dots">
        <span></span><span></span><span></span>
      </div>
    `;
  } else {
    body.textContent = text;
  }

  wrap.appendChild(body);

  // footer actions (copy / ask about this)
  const footer = document.createElement("div");
  footer.className = "bubble-footer";

  const copyBtn = document.createElement("button");
  copyBtn.className = "bubble-action-btn";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(isTyping ? "" : text || "");
  });

  const followBtn = document.createElement("button");
  followBtn.className = "bubble-action-btn";
  followBtn.textContent = "Ask about this";
  followBtn.addEventListener("click", () => {
    composerInput.value = `Can you explain more about: "${(text||"").slice(0,200)}"...`;
    composerInput.focus();
  });

  footer.appendChild(copyBtn);
  footer.appendChild(followBtn);

  wrap.appendChild(footer);

  messagesScroll.appendChild(wrap);

  return {wrap, body}; // so we can update text after typing anim
}

function showTypingBubble() {
  return appendAIBubble("", true); // returns {wrap,body}
}

function replaceTypingBubble(typingRef, finalText) {
  // typingRef.body is the div with dots
  typingRef.body.textContent = finalText;
}

function scrollMessagesToBottom() {
  messagesScroll.scrollTop = messagesScroll.scrollHeight;
}

// ==================================================
// CHAT / MESSAGE FLOW
// ==================================================

async function selectChat(chatId) {
  activeChatId = chatId;
  // highlight in sidebar again
  renderChatList();

  const msgs = await fetchMessages(chatId);
  renderMessagesBubbleList(msgs);
}

async function createNewChat() {
  const data = await postJSON("/chats/new", {});
  activeChatId = data.chat_id;
  await loadChats();
  renderChatList();
  messagesScroll.innerHTML = "";
  composerInput.focus();
}

async function handleSend() {
  const text = composerInput.value.trim();
  const hasImage = !!pendingImageFile;

  if (!text && !hasImage) return;

  // show user bubble(s)
  if (hasImage && pendingImagePreviewURL) {
    appendUserImageBubble(pendingImagePreviewURL);
  }
  if (text) {
    appendUserBubble(text);
  }
  scrollMessagesToBottom();

  // clear composer
  composerInput.value = "";

  // clear preview chip UI
  clearPendingImagePreview();

  // make sure we have a chat
  let useChatId = activeChatId;
  if (!useChatId) {
    const nc = await postJSON("/chats/new", {});
    useChatId = nc.chat_id;
    activeChatId = nc.chat_id;
    await loadChats();
    renderChatList();
  }

  // typing bubble
  const typingRef = showTypingBubble();
  scrollMessagesToBottom();

  // send request to /chat
  let responseData;
  if (hasImage) {
    const fd = new FormData();
    fd.append("chat_id", useChatId);
    fd.append("message", text);
    fd.append("image", pendingImageFile);

    const res = await fetch("/chat", {
      method: "POST",
      body: fd
    });
    responseData = await res.json();
  } else {
    const res = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        chat_id: useChatId,
        message: text
      })
    });
    responseData = await res.json();
  }

  // update typing bubble -> real text
  const finalReply = responseData.response || "Sorry, no response.";
  replaceTypingBubble(typingRef, finalReply);

  // refresh chat list to pull new title
  await loadChats();
  renderChatList();
}

// ==================================================
// IMAGE ATTACH PREVIEW
// ==================================================
function showPendingImagePreview(file) {
  // revoke old previewURL if exists
  if (pendingImagePreviewURL) {
    URL.revokeObjectURL(pendingImagePreviewURL);
  }

  pendingImagePreviewURL = URL.createObjectURL(file);

  pendingImageArea.innerHTML = `
    <div class="pending-chip">
      <img class="pending-thumb" src="${pendingImagePreviewURL}" />
      <button class="pending-clear-btn" id="pending-clear-btn">✕</button>
    </div>
  `;

  const clearBtn = document.getElementById("pending-clear-btn");
  clearBtn.addEventListener("click", () => {
    clearPendingImagePreview();
  });
}

function clearPendingImagePreview() {
  pendingImageFile = null;
  if (pendingImagePreviewURL) {
    URL.revokeObjectURL(pendingImagePreviewURL);
  }
  pendingImagePreviewURL = null;
  pendingImageArea.innerHTML = "";
}

// ==================================================
// BACKGROUND PICKER
// ==================================================

function showBgPicker() {
  bgOverlay.classList.remove("hidden");
}

function hideBgPicker() {
  bgOverlay.classList.add("hidden");
}

async function applyBackground(bgUrl) {
  // set in UI
  if (bgUrl === "none") {
    mainPane.style.backgroundImage = "";
    mainPane.style.backgroundColor = "#121212";
  } else {
    mainPane.style.backgroundImage = `url('${bgUrl}')`;
    mainPane.style.backgroundSize = "cover";
    mainPane.style.backgroundPosition = "center";
  }

  // persist to backend
  await postJSON("/set-background", { bg_url: bgUrl });
}

async function handleBgUpload(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/upload-background", {
    method: "POST",
    body: fd
  });
  const data = await res.json();
  if (data.bg_url) {
    await applyBackground(data.bg_url);
  }
}

// ==================================================
// HELP MODAL
// ==================================================

async function showHelpModal() {
  const info = await getJSON("/help");
  helpBody.innerHTML = `
    <div class="policy-block-head">${escapeHtml(info.title)}</div>
    <div class="policy-block-sub">For: ${escapeHtml(info.for)}</div>
    <ul class="policy-list">
      ${info.rules.map(rule => `<li>${escapeHtml(rule)}</li>`).join("")}
    </ul>
  `;
  helpOverlay.classList.remove("hidden");
}

function hideHelpModal() {
  helpOverlay.classList.add("hidden");
}

// ==================================================
// AUTH MODAL
// ==================================================

function showAuthModal() {
  authOverlay.classList.remove("hidden");
}

function hideAuthModal() {
  authOverlay.classList.add("hidden");
}

async function handleGoogleAuth() {
  try {
    // just bounce to /google-login
    window.location.href = "/google-login";
  } catch (err) {
    alert("Google login not available right now.");
  }
}

async function handleManualAuth() {
  const nameVal  = authNameInput.value.trim();
  const emailVal = authEmailInput.value.trim();
  const passVal  = authPassInput.value.trim(); // currently unused on backend
  if (!nameVal || !emailVal) {
    alert("Please enter name and email.");
    return;
  }

  const fd = new FormData();
  fd.append("name", nameVal);
  fd.append("email", emailVal);
  fd.append("password", passVal);

  const res = await fetch("/manual-login", {
    method: "POST",
    body: fd
  });
  const data = await res.json();
  if (data.ok) {
    hideAuthModal();
    await loadUser();
    renderUserHeader();
  } else {
    alert("Sign in failed.");
  }
}

// ==================================================
// PROJECT ACTIONS
// ==================================================

async function createNewProject() {
  const title = prompt("New project name:");
  if (!title) return;
  await postJSON("/projects/new", { title });
  await loadProjects();
  renderProjectList();
}

// ==================================================
// MENUS / CLICK OUTSIDE HANDLING
// ==================================================

function closeTopMenu() {
  topMenuCard.classList.remove("show");
}
function toggleTopMenu() {
  topMenuCard.classList.toggle("show");
}

function closePlusMenu() {
  plusMenuCard.classList.remove("show");
}
function togglePlusMenu() {
  plusMenuCard.classList.toggle("show");
}

// click-outside
document.addEventListener("click", (e) => {
  // top menu
  if (e.target !== topMenuTrigger && !topMenuCard.contains(e.target)) {
    closeTopMenu();
  }
  // plus menu
  if (e.target !== plusTrigger && !plusMenuCard.contains(e.target)) {
    closePlusMenu();
  }
});

// ==================================================
// EVENT WIRING
// ==================================================

function setupGlobalEvents() {
  // new chat
  newChatBtn.addEventListener("click", createNewChat);

  // send
  sendBtn.addEventListener("click", handleSend);
  composerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // top menu
  topMenuTrigger.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleTopMenu();
  });

  logoutBtn.addEventListener("click", () => {
    window.location.href = "/logout";
  });

  openHelpBtn.addEventListener("click", async () => {
    closeTopMenu();
    await showHelpModal();
  });

  openBgPickerBtn.addEventListener("click", () => {
    closeTopMenu();
    showBgPicker();
  });

  // bg picker modal
  bgClose.addEventListener("click", hideBgPicker);
  bgChoices.forEach((choice) => {
    choice.addEventListener("click", async () => {
      const bgUrl = choice.dataset.bg;
      await applyBackground(bgUrl);
      hideBgPicker();
    });
  });
  bgUploadInput.addEventListener("change", async () => {
    const f = bgUploadInput.files && bgUploadInput.files[0];
    if (!f) return;
    await handleBgUpload(f);
    hideBgPicker();
  });

  // help modal close
  helpClose.addEventListener("click", hideHelpModal);

  // plus menu
  plusTrigger.addEventListener("click", (e) => {
    e.stopPropagation();
    togglePlusMenu();
  });

  // image upload
  imageUploadInput.addEventListener("change", () => {
    const f = imageUploadInput.files && imageUploadInput.files[0];
    if (!f) return;
    pendingImageFile = f;
    showPendingImagePreview(f);
    closePlusMenu();
  });

  // auth modal open/close
  if (authClose) {
    authClose.addEventListener("click", hideAuthModal);
  }
  if (googleAuthBtn) {
    googleAuthBtn.addEventListener("click", handleGoogleAuth);
  }
  if (authSubmitBtn) {
    authSubmitBtn.addEventListener("click", handleManualAuth);
  }

  // new project
  newProjectBtn.addEventListener("click", createNewProject);
}

// ==================================================
// SMALL HELPERS
// ==================================================

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#039;");
}

function formatTimestamp(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}
