document.addEventListener("DOMContentLoaded", () => {
  // ===== grab DOM refs =====
  const newChatBtn        = document.getElementById("new-chat-btn");

  const signinBtn         = document.getElementById("signin-btn");
  const signinModal       = document.getElementById("signin-modal");
  const signinClose       = document.getElementById("signin-close");
  const googleLoginBtn    = document.getElementById("google-login-btn");
  const emailLoginBtn     = document.getElementById("email-login-btn");
  const loginEmailInput   = document.getElementById("login-email");
  const loginPassInput    = document.getElementById("login-pass");

  const plusButton        = document.getElementById("plus-button");
  const uploadPopover     = document.getElementById("upload-popover");
  const uploadImageTrigger= document.getElementById("upload-image-trigger");

  const menuButton        = document.getElementById("menu-button");
  const settingsPopover   = document.getElementById("settings-popover");

  const sendButton        = document.getElementById("send-button");
  const userInput         = document.getElementById("user-input");
  const chatBox           = document.getElementById("chat-box");
  const loadingDots       = document.getElementById("loading-dots");
  const chatScroll        = document.getElementById("chat-scroll");

  const imageFileInput    = document.getElementById("image-file-input");
  const bgFileInput       = document.getElementById("bg-file-input");

  const backgroundModal   = document.getElementById("background-modal");
  const backgroundClose   = document.getElementById("background-close");
  const bgUploadBtn       = document.getElementById("bg-upload-btn");

  const prefsModal        = document.getElementById("prefs-modal");
  const prefsClose        = document.getElementById("prefs-close");

  const helpModal         = document.getElementById("help-modal");
  const helpClose         = document.getElementById("help-close");

  const signedInRow       = document.getElementById("signed-in-row");
  const signedInEmail     = document.getElementById("signed-in-email");
  const signinBtnText     = document.getElementById("signin-btn-text");
  const onlineStatus      = document.getElementById("online-status");

  // ===== helpers =====
  function show(el)     { if (el) el.classList.remove("hidden"); }
  function hide(el)     { if (el && !el.classList.contains("hidden")) el.classList.add("hidden"); }
  function toggle(el)   { if (!el) return; el.classList.toggle("hidden"); }

  function scrollToBottom() {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  function appendMessage(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = sender === "You" ? "user-msg" : "bot-msg";
    bubble.textContent = text;
    chatBox.appendChild(bubble);
    scrollToBottom();
  }

  function appendImageMessage(sender, imgURL) {
    const wrapper = document.createElement("div");
    wrapper.className = sender === "You" ? "user-msg" : "bot-msg";

    const img = document.createElement("img");
    img.src = imgURL;
    img.alt = "uploaded";
    img.style.maxWidth = "200px";
    img.style.borderRadius = "6px";
    img.style.display = "block";

    wrapper.appendChild(img);
    chatBox.appendChild(wrapper);
    scrollToBottom();
  }

  // clear current chat + add new chat item in sidebar
  function startNewChat() {
    chatBox.innerHTML = "";
    hide(loadingDots);

    // create new entry in chat list
    const chatList = document.getElementById("chat-list");
    if (chatList) {
      // remove "active-chat" from all
      chatList.querySelectorAll(".chat-list-item").forEach(item => {
        item.classList.remove("active-chat");
      });
      // add a new item
      const newItem = document.createElement("div");
      newItem.className = "chat-list-item active-chat";
      newItem.innerHTML = `<span class="chat-list-title">New chat</span>`;
      chatList.prepend(newItem);
    }
    // reset input placeholder
    userInput.placeholder = "Message PranayAI...";
  }

  // apply new bg
  function setBackground(url) {
    const root = document.getElementById("app-root");
    root.style.backgroundImage = `url('${url}')`;
  }

  // reset all floating things
  function closeAllFloating() {
    hide(uploadPopover);
    hide(settingsPopover);
    hide(signinModal);
    hide(backgroundModal);
    hide(prefsModal);
    hide(helpModal);
  }

  // ===== INIT =====
  closeAllFloating();
  hide(loadingDots);

  // ===== NEW CHAT BTN =====
  if (newChatBtn) {
    newChatBtn.addEventListener("click", e => {
      e.stopPropagation();
      startNewChat();
    });
  }

  // ===== SIGN-IN FLOW =====
  // open sign-in modal
  if (signinBtn) {
    signinBtn.addEventListener("click", e => {
      e.stopPropagation();
      closeAllFloating();
      show(signinModal);
    });
  }

  // close sign-in modal (X)
  if (signinClose) {
    signinClose.addEventListener("click", e => {
      e.stopPropagation();
      hide(signinModal);
    });
  }

  // click outside card closes sign-in
  if (signinModal) {
    signinModal.addEventListener("click", e => {
      const card = signinModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(signinModal);
      }
    });
  }

  // Google sign-in
  if (googleLoginBtn) {
    googleLoginBtn.addEventListener("click", async e => {
      e.stopPropagation();
      // fake call
      try {
        const resp = await fetch("/google-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: "fake_google_token" })
        });
        const data = await resp.json();
        if (data && data.jwt) {
          signedInEmail.textContent = "user@example.com";
          show(signedInRow);
          signinBtnText.textContent = "Signed in";
          onlineStatus.textContent = "Online";
        }
      } catch (err) {
        console.error("google login fail", err);
      }
      hide(signinModal);
    });
  }

  // Email/password sign-in
  if (emailLoginBtn) {
    emailLoginBtn.addEventListener("click", e => {
      e.stopPropagation();
      const emailVal = (loginEmailInput && loginEmailInput.value.trim()) || "";
      // we don't care about password here, it's fake
      if (emailVal) {
        signedInEmail.textContent = emailVal;
        show(signedInRow);
        signinBtnText.textContent = "Signed in";
        onlineStatus.textContent = "Online";
      }
      hide(signinModal);
    });
  }

  // ===== PLUS BUTTON / UPLOAD IMAGE =====
  if (plusButton) {
    plusButton.addEventListener("click", e => {
      e.stopPropagation();
      // toggle upload popover, close others
      hide(settingsPopover);
      toggle(uploadPopover);
    });
  }

  // clicking "Upload image" opens file picker
  if (uploadImageTrigger) {
    uploadImageTrigger.addEventListener("click", e => {
      e.stopPropagation();
      hide(uploadPopover);
      if (imageFileInput) {
        imageFileInput.value = ""; // <-- reset so same file can be chosen again
        imageFileInput.click();
      }
    });
  }

  // when user picks an image file
  if (imageFileInput) {
    imageFileInput.addEventListener("change", () => {
      const file = imageFileInput.files && imageFileInput.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      appendImageMessage("You", url);
      // After preview we could also send it to backend with FormData later.
    });
  }

  // ===== ⋯ BUTTON / SETTINGS POPOVER =====
  if (menuButton) {
    menuButton.addEventListener("click", e => {
      e.stopPropagation();
      hide(uploadPopover);
      toggle(settingsPopover);
    });
  }

  // clicking outside popovers closes them
  document.addEventListener("click", e => {
    const clickedUpload    = uploadPopover.contains(e.target) || plusButton.contains(e.target);
    const clickedSettings  = settingsPopover.contains(e.target) || menuButton.contains(e.target);
    if (!clickedUpload)    hide(uploadPopover);
    if (!clickedSettings)  hide(settingsPopover);
  });

  // settings popover click actions
  if (settingsPopover) {
    settingsPopover.addEventListener("click", e => {
      const item = e.target.closest(".popover-item");
      if (!item) return;
      const action = item.getAttribute("data-action");

      if (action === "open-settings") {
        hide(settingsPopover);
        closeAllFloating();
        show(prefsModal);
      } else if (action === "open-background") {
        hide(settingsPopover);
        closeAllFloating();
        show(backgroundModal);
      } else if (action === "open-help") {
        hide(settingsPopover);
        closeAllFloating();
        show(helpModal);
      } else if (action === "sign-out") {
        hide(settingsPopover);
        // reset "logged in" state visually
        signedInEmail.textContent = "";
        hide(signedInRow);
        signinBtnText.textContent = "Sign in";
        onlineStatus.textContent = "Online";
      }
    });
  }

  // ===== BACKGROUND MODAL =====
  if (backgroundClose) {
    backgroundClose.addEventListener("click", () => {
      hide(backgroundModal);
    });
  }
  if (backgroundModal) {
    backgroundModal.addEventListener("click", e => {
      const card = backgroundModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(backgroundModal);
      }
    });
    backgroundModal.querySelectorAll(".bg-choice").forEach(tile => {
      tile.addEventListener("click", () => {
        const bgUrl = tile.getAttribute("data-bg");
        setBackground(bgUrl);
        hide(backgroundModal);
      });
    });
  }

  // upload your own bg
  if (bgUploadBtn) {
    bgUploadBtn.addEventListener("click", e => {
      e.stopPropagation();
      if (bgFileInput) {
        bgFileInput.value = "";
        bgFileInput.click();
      }
    });
  }

  if (bgFileInput) {
    bgFileInput.addEventListener("change", () => {
      const file = bgFileInput.files && bgFileInput.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      setBackground(url);
      hide(backgroundModal);
    });
  }

  // ===== PREFS MODAL =====
  if (prefsClose) {
    prefsClose.addEventListener("click", () => hide(prefsModal));
  }
  if (prefsModal) {
    prefsModal.addEventListener("click", e => {
      const card = prefsModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(prefsModal);
      }
    });
  }

  // ===== HELP MODAL =====
  if (helpClose) {
    helpClose.addEventListener("click", () => hide(helpModal));
  }
  if (helpModal) {
    helpModal.addEventListener("click", e => {
      const card = helpModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(helpModal);
      }
    });
  }

  // ===== SEND CHAT MESSAGE =====
  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    userInput.value = "";
    hide(uploadPopover);
    hide(settingsPopover);

    show(loadingDots);
    appendMessage("You", text);

    try {
      const resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: "default",
          consent_ok: true
        })
      });

      const data = await resp.json();
      hide(loadingDots);

      if (resp.ok) {
        appendMessage("PranayAI", data.response || "[no response]");
      } else {
        appendMessage("PranayAI", "Server error talking to model.");
      }

    } catch (err) {
      console.error(err);
      hide(loadingDots);
      appendMessage("PranayAI", "Network error.");
    }
  }

  if (sendButton) {
    sendButton.addEventListener("click", e => {
      e.preventDefault();
      sendMessage();
    });
  }

  if (userInput) {
    userInput.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }
});
