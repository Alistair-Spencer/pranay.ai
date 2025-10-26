// API base: same origin
const API_BASE = "";
const CHAT_URL = `${API_BASE}/chat`;
const GOOGLE_LOGIN_URL = `${API_BASE}/google-login`;
const HISTORY_URL = `${API_BASE}/history`;
const UPLOAD_IMAGE_URL = `${API_BASE}/upload-image`;
const UPLOAD_AUDIO_URL = `${API_BASE}/upload-audio`;

// state
let conversations = [];
let activeIndex = 0;

let authToken = localStorage.getItem("pranay_token") || null;
let authUser  = localStorage.getItem("pranay_user") || null;

let bgImageDataURL = localStorage.getItem("pranay_bg") || null;

const chatWindow    = document.getElementById("chatWindow");
const chatForm      = document.getElementById("chatForm");
const userInput     = document.getElementById("userInput");
const typingRow     = document.getElementById("typingRow");
const historyList   = document.getElementById("history");

const newChatBtn    = document.getElementById("newChatBtn");

const profileInitial = document.getElementById("profileInitial");
const accountUserEl  = document.getElementById("accountUser");
const signinBtn      = document.getElementById("signinBtn");
const logoutBtn      = document.getElementById("logoutBtn");

const settingsTrigger = document.getElementById("settingsTrigger");
const settingsMenu    = document.getElementById("settingsMenu");

const plusBtn      = document.getElementById("plusBtn");
const plusMenu     = document.getElementById("plusMenu");
const uploadImageBtn = document.getElementById("uploadImageBtn");
const imageInput     = document.getElementById("imageInput");
const uploadAudioBtn = document.getElementById("uploadAudioBtn");
const audioInput     = document.getElementById("audioInput");
const changeBgBtn    = document.getElementById("changeBgBtn");
const bgFileInput    = document.getElementById("bgFileInput");

const appShell = document.querySelector(".app-shell");

// ----- helpers -----

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

function renderSidebar() {
  historyList.innerHTML = "";
  conversations.forEach((conv, idx) => {
    const li = document.createElement("li");
    li.textContent = conv.title || "Untitled chat";
    if (idx === activeIndex) {
      li.classList.add("active");
    }
    li.onclick = () => {
      activeIndex = idx;
      renderSidebar();
      renderChat();
    };
    historyList.appendChild(li);
  });
}

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

function setTyping(active) {
  typingRow.hidden = !active;
}

async function sendMessageToAPI(text) {
  const res = await fetch(CHAT_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ message: text })
  });

  if (!res.ok) {
    return { response: "Server error talking to model.", easter_egg: false };
  }

  return res.json();
}

async function saveHistoryToServer() {
  if (!authToken) return;
  try {
    await fetch(HISTORY_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        conversations
      })
    });
  } catch (err) {
    console.warn("Failed to save history:", err);
  }
}

async function loadHistoryFromServer() {
  if (!authToken) return;
  const res = await fetch(HISTORY_URL, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${authToken}`
    }
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

// ----- UI actions -----

async function handleSubmit(e) {
  e.preventDefault();
  const text = userInput.value.trim();
  if (!text) return;

  ensureConversationExists();
  const conv = conversations[activeIndex];

  if (conv.messages.length === 0) {
    conv.title = text.slice(0, 40);
  }

  conv.messages.push({
    role: "user",
    text
  });

  userInput.value = "";
  renderSidebar();
  renderChat();

  setTyping(true);

  let data;
  try {
    data = await sendMessageToAPI(text);
  } catch (err) {
    data = { response: "Network error.", easter_egg: false };
  }

  setTyping(false);

  conv.messages.push({
    role: "ai",
    text: data.response,
    easter: data.easter_egg === true
  });

  renderChat();
  renderSidebar();

  if (authToken) {
    await saveHistoryToServer();
  }
}

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

// sign in via Google
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

function doLogout() {
  authToken = null;
  authUser = null;

  localStorage.removeItem("pranay_token");
  localStorage.removeItem("pranay_user");

  updateAccountUI();
}

// update account block bottom-left
function updateAccountUI() {
  if (authUser) {
    profileInitial.textContent = authUser[0]?.toUpperCase() || "?";
    accountUserEl.textContent  = authUser;
    signinBtn.style.display = "none";
    logoutBtn.style.display = "block";
  } else {
    profileInitial.textContent = "?";
    accountUserEl.textContent  = "(not signed in)";
    signinBtn.style.display = "inline-block";
    logoutBtn.style.display = "block"; // we'll keep sign out visible so you can clear local
  }
}

// open/close settings menu
settingsTrigger.addEventListener("click", () => {
  const isHidden = settingsMenu.hasAttribute("hidden");
  if (isHidden) {
    settingsMenu.removeAttribute("hidden");
  } else {
    settingsMenu.setAttribute("hidden", "true");
  }
});

// clicking "Sign in with Google"
signinBtn.addEventListener("click", () => {
  // This triggers Google's one-tap UI flow if available,
  // or you can manually render the Google button. For now we
  // just let onGoogleSignIn handle callback from Google's script.
  google.accounts.id.prompt(); // this is fine, Google's script is loaded in index.html
});

// manual logout
logoutBtn.addEventListener("click", () => {
  doLogout();
  renderSidebar();
  renderChat();
});

// plus menu open/close
plusBtn.addEventListener("click", () => {
  const isHidden = plusMenu.hasAttribute("hidden");
  if (isHidden) {
    plusMenu.removeAttribute("hidden");
  } else {
    plusMenu.setAttribute("hidden", "true");
  }
});

// choose image
uploadImageBtn.addEventListener("click", () => {
  imageInput.click();
});
imageInput.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  // send to backend placeholder
  const formData = new FormData();
  formData.append("file", file);

  try {
    await fetch(UPLOAD_IMAGE_URL, {
      method: "POST",
      body: formData
    });
    // OPTIONAL: Add a system message saying "Image received"
    addSystemMessage(`Image "${file.name}" uploaded (not analyzed yet).`);
  } catch (err) {
    addSystemMessage("Failed to upload image.");
  }
});

// choose audio
uploadAudioBtn.addEventListener("click", () => {
  audioInput.click();
});
audioInput.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    await fetch(UPLOAD_AUDIO_URL, {
      method: "POST",
      body: formData
    });
    addSystemMessage(`Audio "${file.name}" uploaded (not transcribed yet).`);
  } catch (err) {
    addSystemMessage("Failed to upload audio.");
  }
});

// change background (preset dark or clear custom)
changeBgBtn.addEventListener("click", () => {
  bgImageDataURL = null;
  localStorage.removeItem("pranay_bg");
  applyBackground();
  plusMenu.setAttribute("hidden", "true");
});

// upload custom background image
bgFileInput.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(evt) {
    bgImageDataURL = evt.target.result;
    localStorage.setItem("pranay_bg", bgImageDataURL);
    applyBackground();
  };
  reader.readAsDataURL(file);

  plusMenu.setAttribute("hidden", "true");
});

// insert a system-style bubble in chat (for status updates)
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

// actually apply background to the app-shell
function applyBackground() {
  if (bgImageDataURL) {
    appShell.style.backgroundImage = `url(${bgImageDataURL})`;
  } else {
    appShell.style.backgroundImage = "none";
  }
}

// ----- wire up listeners -----

chatForm.addEventListener("submit", handleSubmit);
newChatBtn.addEventListener("click", startNewChat);

// init
(async function init() {
  // load server history if logged in
  if (authToken) {
    await loadHistoryFromServer();
  }

  ensureConversationExists();
  updateAccountUI();
  renderSidebar();
  renderChat();
  applyBackground();
})();
