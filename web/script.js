document.addEventListener("DOMContentLoaded", () => {
  // ===== grab DOM =====
  const signinBtn         = document.getElementById("signin-btn");
  const signinModal       = document.getElementById("signin-modal");
  const signinClose       = document.getElementById("signin-close");
  const googleLoginReal   = document.getElementById("google-login-real");

  const plusButton        = document.getElementById("plus-button");
  const uploadMenu        = document.getElementById("upload-menu");

  const menuButton        = document.getElementById("menu-button");
  const settingsModal     = document.getElementById("settings-modal");

  const sendButton        = document.getElementById("send-button");
  const userInput         = document.getElementById("user-input");
  const chatBox           = document.getElementById("chat-box");
  const loadingDots       = document.getElementById("loading-dots");

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
  function show(el) { if (el) el.classList.remove("hidden"); }
  function hide(el) { if (el && !el.classList.contains("hidden")) el.classList.add("hidden"); }
  function toggle(el) {
    if (!el) return;
    if (el.classList.contains("hidden")) { el.classList.remove("hidden"); }
    else { el.classList.add("hidden"); }
  }

  // close all popovers/overlays
  function closeAllFloating() {
    hide(uploadMenu);
    hide(settingsModal);
    hide(signinModal);
    hide(backgroundModal);
    hide(prefsModal);
    hide(helpModal);
  }

  // init state
  closeAllFloating();
  hide(loadingDots);

  // ===== SIGN-IN =====
  if (signinBtn) {
    signinBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      // open the sign-in modal
      show(signinModal);
    });
  }

  if (signinClose) {
    signinClose.addEventListener("click", (e) => {
      e.stopPropagation();
      hide(signinModal);
    });
  }

  // fake google login -> call backend, then mark UI as "signed in"
  if (googleLoginReal) {
    googleLoginReal.addEventListener("click", async (e) => {
      e.stopPropagation();
      try {
        const resp = await fetch("/google-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: "fake_google_id_token_from_client" })
        });
        const data = await resp.json();

        // pretend we're signed in:
        // show email, change button text
        if (data && data.jwt) {
          signedInEmail.textContent = "user@example.com";
          show(signedInRow);
          signinBtnText.textContent = "Signed in";
          onlineStatus.textContent = "Online";
        }

        hide(signinModal);
      } catch (err) {
        console.error("google login fail", err);
        hide(signinModal);
      }
    });
  }

  // clicking outside the sign-in card closes it
  if (signinModal) {
    signinModal.addEventListener("click", (e) => {
      const card = signinModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(signinModal);
      }
    });
  }

  // ===== PLUS / UPLOAD MENU =====
  if (plusButton) {
    plusButton.addEventListener("click", (e) => {
      e.stopPropagation();
      // open/close upload menu, close other menus
      hide(settingsModal);
      toggle(uploadMenu);
    });
  }

  // upload image option -> open file picker
  const uploadImageTrigger = document.getElementById("upload-image-trigger");
  if (uploadImageTrigger) {
    uploadImageTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      hide(uploadMenu);
      if (imageFileInput) {
        imageFileInput.click();
      }
    });
  }

  // listen for chosen image
  if (imageFileInput) {
    imageFileInput.addEventListener("change", () => {
      const file = imageFileInput.files && imageFileInput.files[0];
      if (!file) return;
      // just preview it in chat for now
      const url = URL.createObjectURL(file);
      appendImageMessage("You", url);
    });
  }

  // custom background option -> open background modal
  const customBgTrigger = document.getElementById("custom-bg-trigger");
  if (customBgTrigger) {
    customBgTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      hide(uploadMenu);
      show(backgroundModal);
    });
  }

  // ===== ⋯ / SETTINGS MENU =====
  if (menuButton) {
    menuButton.addEventListener("click", (e) => {
      e.stopPropagation();
      hide(uploadMenu);
      toggle(settingsModal);
    });
  }

  // settings popover actions
  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      const target = e.target.closest(".popover-item");
      if (!target) return;

      const action = target.getAttribute("data-action");

      if (action === "open-settings") {
        hide(settingsModal);
        show(prefsModal);
      } else if (action === "open-background") {
        hide(settingsModal);
        show(backgroundModal);
      } else if (action === "open-help") {
        hide(settingsModal);
        show(helpModal);
      } else if (action === "sign-out") {
        // reset fake login state
        hide(settingsModal);
        signedInEmail.textContent = "";
        hide(signedInRow);
        signinBtnText.textContent = "Sign in with Google";
        onlineStatus.textContent = "Online";
      }
    });
  }

  // clicking outside popovers closes them
  document.addEventListener("click", (e) => {
    const clickInUpload   = uploadMenu.contains(e.target);
    const clickInPlusBtn  = plusButton.contains(e.target);
    const clickInSettings = settingsModal.contains(e.target);
    const clickInMenuBtn  = menuButton.contains(e.target);

    if (!clickInUpload && !clickInPlusBtn) {
      hide(uploadMenu);
    }
    if (!clickInSettings && !clickInMenuBtn) {
      hide(settingsModal);
    }
  });

  // ===== BACKGROUND MODAL =====
  if (backgroundClose) {
    backgroundClose.addEventListener("click", () => {
      hide(backgroundModal);
    });
  }
  if (backgroundModal) {
    // close if you click dim outside card
    backgroundModal.addEventListener("click", (e) => {
      const card = backgroundModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(backgroundModal);
      }
    });

    // click a preset tile
    backgroundModal.querySelectorAll(".bg-choice").forEach(tile => {
      tile.addEventListener("click", () => {
        const bgUrl = tile.getAttribute("data-bg");
        setBackground(bgUrl);
        hide(backgroundModal);
      });
    });
  }

  // Upload your own background button
  if (bgUploadBtn) {
    bgUploadBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (bgFileInput) {
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

  function setBackground(url) {
    // apply background to the whole app shell
    const root = document.getElementById("app-root");
    root.style.backgroundImage = `url('${url}')`;
  }

  // ===== PREFS MODAL (Settings) =====
  if (prefsClose) {
    prefsClose.addEventListener("click", () => hide(prefsModal));
  }
  if (prefsModal) {
    prefsModal.addEventListener("click", (e) => {
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
    helpModal.addEventListener("click", (e) => {
      const card = helpModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(helpModal);
      }
    });
  }

  // ===== CHAT SEND =====
  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    userInput.value = "";

    hide(uploadMenu);
    hide(settingsModal);

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

  // send on click
  if (sendButton) {
    sendButton.addEventListener("click", (e) => {
      e.preventDefault();
      sendMessage();
    });
  }

  // send on Enter
  if (userInput) {
    userInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // ===== message helpers =====
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

  function scrollToBottom() {
    const scrollArea = document.getElementById("chat-scroll");
    scrollArea.scrollTop = scrollArea.scrollHeight;
  }
});
