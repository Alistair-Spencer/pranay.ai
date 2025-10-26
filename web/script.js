document.addEventListener("DOMContentLoaded", () => {
  // ===== query all elements we need =====
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

  // --- helper to show / hide ---
  function show(el) {
    if (!el) return;
    el.classList.remove("hidden");
  }
  function hide(el) {
    if (!el) return;
    if (!el.classList.contains("hidden")) {
      el.classList.add("hidden");
    }
  }

  // initial state
  hide(uploadMenu);
  hide(settingsModal);
  hide(signinModal);
  hide(loadingDots);

  // ===== SIGN-IN MODAL BEHAVIOR =====
  if (signinBtn) {
    signinBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      show(signinModal);
    });
  }

  if (signinClose) {
    signinClose.addEventListener("click", (e) => {
      e.stopPropagation();
      hide(signinModal);
    });
  }

  if (googleLoginReal) {
    googleLoginReal.addEventListener("click", async (e) => {
      e.stopPropagation();
      console.log("TODO: implement /google-login real OAuth call");
      hide(signinModal);
    });
  }

  // close sign-in if you click the dark background outside the card
  if (signinModal) {
    signinModal.addEventListener("click", (e) => {
      const card = signinModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(signinModal);
      }
    });
  }

  // ===== PLUS BUTTON (UPLOAD MENU) =====
  if (plusButton) {
    plusButton.addEventListener("click", (e) => {
      e.stopPropagation();
      // toggle upload menu
      if (uploadMenu.classList.contains("hidden")) {
        hide(settingsModal); // only one menu open at a time
        show(uploadMenu);
      } else {
        hide(uploadMenu);
      }
    });
  }

  // ===== TOP RIGHT MENU (SETTINGS) =====
  if (menuButton) {
    menuButton.addEventListener("click", (e) => {
      e.stopPropagation();
      // toggle settings menu
      if (settingsModal.classList.contains("hidden")) {
        hide(uploadMenu);
        show(settingsModal);
      } else {
        hide(settingsModal);
      }
    });
  }

  // ===== GLOBAL CLICK TO CLOSE MENUS =====
  document.addEventListener("click", (e) => {
    // don't close if click is actually inside these popovers/buttons
    const clickedUploadMenu   = uploadMenu && uploadMenu.contains(e.target);
    const clickedPlusButton   = plusButton && plusButton.contains(e.target);
    const clickedSettingsMenu = settingsModal && settingsModal.contains(e.target);
    const clickedMenuButton   = menuButton && menuButton.contains(e.target);

    if (!clickedUploadMenu && !clickedPlusButton) {
      hide(uploadMenu);
    }
    if (!clickedSettingsMenu && !clickedMenuButton) {
      hide(settingsModal);
    }
  });

  // ===== SEND MESSAGE TO BACKEND =====
  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // clear input box
    userInput.value = "";

    // hide menus just in case
    hide(uploadMenu);
    hide(settingsModal);

    // show typing dots
    show(loadingDots);

    // append user bubble instantly
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

  // clicking send
  if (sendButton) {
    sendButton.addEventListener("click", (e) => {
      e.preventDefault();
      sendMessage();
    });
  }

  // pressing Enter
  if (userInput) {
    userInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // helper to append chat bubbles
  function appendMessage(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = sender === "You" ? "user-msg" : "bot-msg";
    bubble.textContent = text;

    chatBox.appendChild(bubble);

    // auto-scroll chat pane to bottom
    const scrollArea = document.getElementById("chat-scroll");
    scrollArea.scrollTop = scrollArea.scrollHeight;
  }
});
