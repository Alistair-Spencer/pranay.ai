// =====================
// CONFIG
// =====================
const API_BASE = "";
const CHAT_URL = `${API_BASE}/chat`;
const GOOGLE_LOGIN_URL = `${API_BASE}/google-login`;
const HISTORY_URL = `${API_BASE}/history`;
const UPLOAD_IMAGE_URL = `${API_BASE}/upload-image`;

// =====================
// STATE
// =====================
let conversations = [];
let activeIndex = 0;

let authToken = localStorage.getItem("pranay_token") || null;
let authUser  = localStorage.getItem("pranay_user") || null;

/**
 * sessionId:
 * - used before login so we can track consent ("pledge") per browser
 */
let sessionId = localStorage.getItem("pranay_session_id") || null;
if (!sessionId) {
  sessionId = "session-" + Date.now();
  localStorage.setItem("pranay_session_id", sessionId);
}

/**
 * pledgeAccepted:
 * - did user check "I agree..." in Settings at least once?
 */
let pledgeAccepted = localStorage.getItem("pranay_pledge_ok") === "true";

/**
 * background setting
 * { mode: "default"|"preset1"|"preset2"|"preset3"|"custom", dataURL: string|null }
 */
let bgSetting = JSON.parse(localStorage.getItem("pranay_bg_setting") || "null") || {
  mode: "default",
  dataURL: null
};

// =====================
// DOM
// =====================

// left column
const historyList     = document.getElementById("history");
const newChatBtn      = document.getElementById("newChatBtn");
const profileInitial  = document.getElementById("profileInitial");
const accountUserEl   = document.getElementById("accountUser");
const signinBtn       = document.getElementById("signinBtn");
const logoutBtn       = document.getElementById("logoutBtn");
const settingsTrigger = document.getElementById("settingsTrigger");
const settingsMenu    = document.getElementById("settingsMenu");

// chat area
const chatWindow      = document.getElementById("chatWindow");
const typingRow       = document.getElementById("typingRow");

// input bar
const chatForm        = document.getElementById("chatForm");
const userInput       = document.getElementById("userInput");
const plusBtn         = document.getElementById("plusBtn");
const plusMenu        = document.getElementById("plusMenu");
const uploadImageBtn  = document.getElementById("uploadImageBtn");
const imageInput      = document.getElementById("imageInput");
const micBtn          = document.getElementById("micBtn");

// modal / views
const settingsModal       = document.getElementById("settingsModal");
const modalTitle          = document.getElementById("modalTitle");
const modalCloseBtn       = document.getElementById("modalCloseBtn");
const modalSaveBtn        = document.getElementById("modalSaveBtn");

const settingsView        = document.getElementById("settingsView");
const backgroundView      = document.getElementById("backgroundView");
const helpView            = document.getElementById("helpView");

const openSettingsPanel   = document.getElementById("openSettingsPanel");
const openBackgroundPanel = document.getElementById("openBackgroundPanel");
const openHelpPanel       = document.getElementById("openHelpPanel");

const settingsAccountName = document.getElementById("settingsAccountName");
const pledgeCheckbox      = document.getElementById("pledgeCheckbox");

const bgFileInput         = document.getElementById("bgFileInput");

const appShell            = document.querySelector(".app-shell");

// =====================
// BASIC HELPERS
// =====================

function ensureConversationExists() {
  if (conversations.length === 0) {
    conversations.push({
      id: `local-${Date.now()}`,
      title: "New chat",
      messages: []
    });
    activeIndex = 0;
  }
}

// render left sidebar chats
function renderSidebar() {
  historyList.innerHTML = "";
  conversations.forEach((conv, idx) => {
    const li = document.createElement("li");
    li.textContent = conv.title || "Untitled chat";
    if (idx === activeIndex) li.classList.add("active");
    li.onclick = () => {
      activeIndex = idx;
      renderSidebar();
      renderChat();
    };
    historyList.appendChild(li);
  });
}

// render chat messages
function renderChat() {
  chatWindow.innerHTML = "";
  const conv = conversations[activeIndex];

  conv.messages.forEach(msg => {
    const row = document.createElement("div");
    row.className = "msg-row " + (msg.role === "user" ? "user" : "ai");

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (msg.role === "ai" && msg.easter === true) {
      bubble.classList.add("special");
    }
    bubble.textContent = msg.text;

    row.appendChild(bubble);
    chatWindow.appendChild(row);
  });

  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// thinking indicator
function setThinking(active) {
  typingRow.hidden = !active;
}

// show a system-style message in chat
function addSystemMessage(text) {
  ensureConversationExists();
  const conv = conversations[activeIndex];
  conv.messages.push({
    role: "ai",
    text,
    easter: false,
  });
  renderChat();
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// =====================
// BACKEND CALLS
// =====================

async function sendMessageToAPI(text) {
  const payload = {
    message: text,
    session_id: sessionId,
    consent_ok: pledgeAccepted,
  };

  const res = await fetch(CHAT_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  // handle 403 (pledge not accepted)
  if (res.status === 403) {
    const data = await res.json();
    return {
      response: data.response || "Please accept responsible use first.",
      easter_egg: false
    };
  }

  if (!res.ok) {
    return {
      response: "Server error talking to model.",
      easter_egg: false
    };
  }

  return res.json();
}

// load/save history if signed in
async function saveHistoryToServer() {
  if (!authToken) return;
  try {
    await fetch(HISTORY_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ conversations })
    });
  } catch (err) {
    console.warn("Failed to save history:", err);
  }
}

async function loadHistoryFromServer() {
  if (!authToken) return;
  const res = await fetch(HISTORY_URL, {
    method: "GET",
    headers: { "Authorization": `Bearer ${authToken}` }
  });
  if (!res.ok) {
    console.warn("No server history or error loading history");
    return;
  }
  const data = await res.json();
  if (Array.isArray(data.conversations)) {
    conversations = data.conversations;
    activeIndex = conversations.length > 0 ? conversations.length - 1 : 0;
  }
}

// =====================
// UI STATE / ACCOUNT
// =====================

function updateAccountUI() {
  if (authUser) {
    profileInitial.textContent      = authUser[0]?.toUpperCase() || "?";
    accountUserEl.textContent       = authUser;
    signinBtn.style.display         = "none";
    settingsAccountName.textContent = authUser;
  } else {
    profileInitial.textContent      = "?";
    accountUserEl.textContent       = "";
    signinBtn.style.display         = "inline-flex";
    settingsAccountName.textContent = "(not signed in)";
  }
  pledgeCheckbox.checked = pledgeAccepted;
}

function doLogout() {
  authToken = null;
  authUser  = null;
  localStorage.removeItem("pranay_token");
  localStorage.removeItem("pranay_user");
  updateAccountUI();
  renderSidebar();
  renderChat();
  settingsMenu.setAttribute("hidden", "true");
}

// Google login callback (called by Google script)
window.onGoogleSignIn = async function onGoogleSignIn(googleResponse) {
  try {
    const id_token = googleResponse.credential;

    const res = await fetch(GOOGLE_LOGIN_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ id_token })
    });

    if (!res.ok) {
      alert("Google login failed.");
      return;
    }

    const data = await res.json();
    authToken = data.token;
    authUser  = data.username;

    localStorage.setItem("pranay_token", authToken);
    localStorage.setItem("pranay_user",  authUser);

    await loadHistoryFromServer();
    ensureConversationExists();
    updateAccountUI();
    renderSidebar();
    renderChat();
  } catch (err) {
    console.error(err);
    alert("Login error.");
  }
};

// =====================
// CHAT FORM HANDLING
// =====================

async function handleSubmit(e) {
  e.preventDefault();
  const text = userInput.value.trim();
  if (!text) return;

  ensureConversationExists();
  const conv = conversations[activeIndex];

  // first user message becomes chat title
  if (conv.messages.length === 0) {
    conv.title = text.slice(0, 40);
  }

  // push user msg
  conv.messages.push({
    role: "user",
    text
  });

  userInput.value = "";
  renderSidebar();
  renderChat();

  // think...
  setThinking(true);

  let data;
  try {
    data = await sendMessageToAPI(text);
  } catch (err) {
    data = { response: "Network error.", easter_egg: false };
  }

  // stop thinking
  setThinking(false);

  // add AI msg
  conv.messages.push({
    role: "ai",
    text: data.response,
    easter: data.easter_egg === true
  });

  renderChat();
  renderSidebar();

  // save to server if logged in
  if (authToken) {
    await saveHistoryToServer();
  }
}

// start new blank chat
function startNewChat() {
  conversations.push({
    id: `local-${Date.now()}`,
    title: "New chat",
    messages: []
  });
  activeIndex = conversations.length - 1;
  renderSidebar();
  renderChat();
  userInput.focus();
}

// =====================
// MENUS / DROPDOWNS
// =====================

// ⋯ menu
settingsTrigger.addEventListener("click", (e) => {
  e.stopPropagation();
  const hidden = settingsMenu.hasAttribute("hidden");
  if (hidden) {
    settingsMenu.removeAttribute("hidden");
  } else {
    settingsMenu.setAttribute("hidden", "true");
  }
});

// + menu
plusBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const hidden = plusMenu.hasAttribute("hidden");
  if (hidden) {
    plusMenu.removeAttribute("hidden");
  } else {
    plusMenu.setAttribute("hidden", "true");
  }
});

// click outside -> close both
document.addEventListener("click", (e) => {
  if (!plusBtn.contains(e.target) && !plusMenu.contains(e.target)) {
    plusMenu.setAttribute("hidden", "true");
  }
  if (!settingsTrigger.contains(e.target) && !settingsMenu.contains(e.target)) {
    settingsMenu.setAttribute("hidden", "true");
  }
});

// upload image
uploadImageBtn.addEventListener("click", () => {
  imageInput.click();
});
imageInput.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  plusMenu.setAttribute("hidden", "true");

  const formData = new FormData();
  formData.append("file", file);

  try {
    await fetch(UPLOAD_IMAGE_URL, {
      method: "POST",
      body: formData
    });
    addSystemMessage(`Image "${file.name}" uploaded (not analyzed yet).`);
  } catch (err) {
    addSystemMessage("Failed to upload image.");
  }
});

// mic (speech to text)
let recognizing = false;
let recognition;
if ("webkitSpeechRecognition" in window) {
  recognition = new webkitSpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    recognizing = true;
    micBtn.classList.add("recording");
    micBtn.title = "Listening…";
  };
  recognition.onend = () => {
    recognizing = false;
    micBtn.classList.remove("recording");
    micBtn.removeAttribute("title");
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    userInput.value = (userInput.value + " " + transcript).trim();
  };
}

micBtn.addEventListener("click", () => {
  if (!recognition) {
    alert("Speech recognition not supported in this browser.");
    return;
  }
  if (recognizing) {
    recognition.stop();
  } else {
    recognition.start();
  }
});

// =====================
// MODAL HANDLING
// =====================

function openModal(section) {
  // hide all
  settingsView.hidden   = true;
  backgroundView.hidden = true;
  helpView.hidden       = true;

  if (section === "settings") {
    modalTitle.textContent = "Settings";
    settingsView.hidden = false;
  } else if (section === "background") {
    modalTitle.textContent = "Background";
    backgroundView.hidden = false;

    // sync radio to current bgSetting
    const radios = backgroundView.querySelectorAll(
      'input[type="radio"][name="bgstyle"]'
    );
    radios.forEach(r => {
      r.checked = (r.value === bgSetting.mode);
    });
  } else if (section === "help") {
    modalTitle.textContent = "Help & Policies";
    helpView.hidden = false;
  }

  pledgeCheckbox.checked = pledgeAccepted;
  settingsModal.removeAttribute("hidden");
}

function closeModal() {
  settingsModal.setAttribute("hidden", "true");
}

// bottom-left menu -> open different views
openSettingsPanel.addEventListener("click", () => {
  settingsMenu.setAttribute("hidden", "true");
  openModal("settings");
});
openBackgroundPanel.addEventListener("click", () => {
  settingsMenu.setAttribute("hidden", "true");
  openModal("background");
});
openHelpPanel.addEventListener("click", () => {
  settingsMenu.setAttribute("hidden", "true");
  openModal("help");
});

modalCloseBtn.addEventListener("click", closeModal);

// Save button in modal
modalSaveBtn.addEventListener("click", () => {
  // If settings visible: record pledgeAccepted
  if (!settingsView.hidden) {
    pledgeAccepted = pledgeCheckbox.checked;
    localStorage.setItem("pranay_pledge_ok", pledgeAccepted ? "true" : "false");
  }

  // If background visible: save bg choice
  if (!backgroundView.hidden) {
    const selected = backgroundView.querySelector(
      'input[name="bgstyle"]:checked'
    );
    if (selected) {
      const mode = selected.value;
      if (mode === "default") {
        bgSetting = { mode: "default", dataURL: null };
      } else if (mode === "preset1") {
        bgSetting = { mode: "preset1", dataURL: null };
      } else if (mode === "preset2") {
        bgSetting = { mode: "preset2", dataURL: null };
      } else if (mode === "preset3") {
        bgSetting = { mode: "preset3", dataURL: null };
      } else if (mode === "custom") {
        bgSetting = { mode: "custom", dataURL: bgSetting.dataURL || null };
      }
      applyBackground();
      localStorage.setItem("pranay_bg_setting", JSON.stringify(bgSetting));
    }
  }

  closeModal();
});

// custom background file picker
bgFileInput.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(evt) {
    bgSetting = {
      mode: "custom",
      dataURL: evt.target.result
    };
    applyBackground();
    localStorage.setItem("pranay_bg_setting", JSON.stringify(bgSetting));
  };
  reader.readAsDataURL(file);
});

// apply background to .app-shell
function applyBackground() {
  if (bgSetting.mode === "default") {
    appShell.style.backgroundImage = "none";
    appShell.style.backgroundColor = "#0f0f12";
  } else if (bgSetting.mode === "preset1") {
    appShell.style.backgroundImage = "url('/static/bg1.jpg')";
    appShell.style.backgroundSize = "cover";
    appShell.style.backgroundPosition = "center";
    appShell.style.backgroundRepeat = "no-repeat";
  } else if (bgSetting.mode === "preset2") {
    appShell.style.backgroundImage = "url('/static/bg2.jpg')";
    appShell.style.backgroundSize = "cover";
    appShell.style.backgroundPosition = "center";
    appShell.style.backgroundRepeat = "no-repeat";
  } else if (bgSetting.mode === "preset3") {
    appShell.style.backgroundImage = "url('/static/bg3.jpg')";
    appShell.style.backgroundSize = "cover";
    appShell.style.backgroundPosition = "center";
    appShell.style.backgroundRepeat = "no-repeat";
  } else if (bgSetting.mode === "custom" && bgSetting.dataURL) {
    appShell.style.backgroundImage = `url(${bgSetting.dataURL})`;
    appShell.style.backgroundSize = "cover";
    appShell.style.backgroundPosition = "center";
    appShell.style.backgroundRepeat = "no-repeat";
  }
}

// =====================
// EVENTS
// =====================

chatForm.addEventListener("submit", handleSubmit);
newChatBtn.addEventListener("click", startNewChat);
logoutBtn.addEventListener("click", doLogout);

// clicking "Sign in with Google"
signinBtn.addEventListener("click", () => {
  google.accounts.id.prompt();
});

// =====================
// INIT
// =====================
(async function init() {
  // load history if logged in
  if (authToken) {
    await loadHistoryFromServer();
  }

  ensureConversationExists();
  updateAccountUI();
  renderSidebar();
  renderChat();
  applyBackground();
})();
