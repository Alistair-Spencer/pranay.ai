// API_BASE is blank because frontend and backend are same domain now
const API_BASE = "";
const CHAT_URL = `${API_BASE}/chat`;
const GOOGLE_LOGIN_URL = `${API_BASE}/google-login`;
const HISTORY_URL = `${API_BASE}/history`;

let conversations = [];
let activeIndex = 0;

let authToken = localStorage.getItem("pranay_token") || null;
let authUser  = localStorage.getItem("pranay_user") || null;

let autosave = localStorage.getItem("pranay_autosave") === "true";

const historyList = document.getElementById("history");
const chatWindow = document.getElementById("chatWindow");
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const typingRow = document.getElementById("typingRow");
const newChatBtn = document.getElementById("newChatBtn");

const profileBtn = document.getElementById("profileBtn");
const accountCard = document.getElementById("accountCard");
const profileInitial = document.getElementById("profileInitial");
const accountUserEl = document.getElementById("accountUser");
const autosaveToggle = document.getElementById("autosaveToggle");

const authAreaSignedOut = document.getElementById("authAreaSignedOut");
const authAreaSignedIn  = document.getElementById("authAreaSignedIn");
const logoutBtn         = document.getElementById("logoutBtn");

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
      li.style.backgroundColor = "rgba(255,255,255,0.07)";
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

function updateAccountUI() {
  if (authUser) {
    profileInitial.textContent = authUser[0]?.toUpperCase() || "?";
    accountUserEl.textContent  = authUser;
    authAreaSignedOut.style.display = "none";
    authAreaSignedIn.style.display  = "flex";
  } else {
    profileInitial.textContent = "?";
    accountUserEl.textContent  = "(not signed in)";
    authAreaSignedOut.style.display = "flex";
    authAreaSignedIn.style.display  = "none";
  }

  autosaveToggle.checked = autosave && !!authUser;
  autosaveToggle.disabled = !authUser;
}

function toggleAccountCard() {
  accountCard.hidden = !accountCard.hidden;
}

function setAutosavePreference(on) {
  autosave = on;
  localStorage.setItem("pranay_autosave", String(on));
  updateAccountUI();
}

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

  if (authToken && autosave) {
    try {
      await saveHistoryToServer();
    } catch (err) {
      console.warn("Failed to save history:", err);
    }
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

async function saveHistoryToServer() {
  if (!authToken) return;
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
  autosave = false;

  localStorage.removeItem("pranay_token");
  localStorage.removeItem("pranay_user");
  localStorage.setItem("pranay_autosave", "false");

  updateAccountUI();
}

chatForm.addEventListener("submit", handleSubmit);
newChatBtn.addEventListener("click", startNewChat);

profileBtn.addEventListener("click", toggleAccountCard);
logoutBtn.addEventListener("click", doLogout);

autosaveToggle.addEventListener("change", (e) => {
  setAutosavePreference(e.target.checked);
});

(async function init() {
  if (authToken) {
    await loadHistoryFromServer();
  }

  ensureConversationExists();
  updateAccountUI();
  renderSidebar();
  renderChat();
})();
