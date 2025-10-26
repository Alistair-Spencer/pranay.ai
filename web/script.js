document.addEventListener("DOMContentLoaded", () => {
  // Grab elements
  const signinBtn = document.getElementById("signin-btn");
  const signinModal = document.getElementById("signin-modal");
  const signinClose = document.getElementById("signin-close");
  const googleLoginReal = document.getElementById("google-login-real");

  const plusButton = document.getElementById("plus-button");
  const uploadMenu = document.getElementById("upload-menu");

  const menuButton = document.getElementById("menu-button");
  const settingsModal = document.getElementById("settings-modal");

  const sendButton = document.getElementById("send-button");
  const userInput = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const loadingDots = document.getElementById("loading-dots");

  // Safety check so we don't throw if any element is missing
  function safeHide(el) {
    if (el && !el.classList.contains("hidden")) {
      el.classList.add("hidden");
    }
  }
  function safeShowFlex(el) {
    if (el && el.classList.contains("hidden")) {
      el.classList.remove("hidden");
    }
  }

  // Initial state: hide menus / modals / loading
  safeHide(uploadMenu);
  safeHide(settingsModal);
  safeHide(signinModal);
  safeHide(loadingDots);

  // ===== SIGN-IN FLOW =====
  if (signinBtn) {
    signinBtn.addEventListener("click", () => {
      // open modal
      safeShowFlex(signinModal);
    });
  }

  if (signinClose) {
    signinClose.addEventListener("click", () => {
      // close modal
      safeHide(signinModal);
    });
  }

  if (googleLoginReal) {
    googleLoginReal.addEventListener("click", async () => {
      // This is where you'd actually talk to /google-login
      // We'll just close it for now
      console.log("Google login clicked (placeholder)");
      safeHide(signinModal);
    });
  }

  // ===== PLUS MENU (UPLOAD MENU) =====
  if (plusButton) {
    plusButton.addEventListener("click", (e) => {
      e.stopPropagation();
      // toggle visibility
      if (uploadMenu.classList.contains("hidden")) {
        // open upload menu
        safeHide(settingsModal); // close the other menu just in case
        uploadMenu.classList.remove("hidden");
      } else {
        // close
        uploadMenu.classList.add("hidden");
      }
    });
  }

  // ===== TOP RIGHT MENU (SETTINGS) =====
  if (menuButton) {
    menuButton.addEventListener("click", (e) => {
      e.stopPropagation();
      if (settingsModal.classList.contains("hidden")) {
        // open settings
        safeHide(uploadMenu); // close other
        settingsModal.classList.remove("hidden");
      } else {
        // close
        settingsModal.classList.add("hidden");
      }
    });
  }

  // ===== CLOSE MENUS WHEN CLICKING OUTSIDE =====
  document.addEventListener("click", (e) => {
    const clickedUploadMenu = uploadMenu.contains(e.target);
    const clickedPlus = plusButton.contains(e.target);

    const clickedSettingsMenu = settingsModal.contains(e.target);
    const clickedMenuBtn = menuButton.contains(e.target);

    // if click is outside upload menu and plus button, hide upload menu
    if (!clickedUploadMenu && !clickedPlus) {
      safeHide(uploadMenu);
    }

    // if click is outside settings menu and menu button, hide settings menu
    if (!clickedSettingsMenu && !clickedMenuBtn) {
      safeHide(settingsModal);
    }

    // if click is on overlay background outside signin card, close signin
    if (signinModal && !signinModal.classList.contains("hidden")) {
      const card = signinModal.querySelector(".overlay-card");
      if (card && !card.contains(e.target) && !signinBtn.contains(e.target)) {
        // clicked the dark background -> close
        if (!signinModal.contains(e.target)) return;
        if (!card.contains(e.target)) {
          // still allow click to "fall through"
        }
      }
    }
  });

  // ===== SEND MESSAGE TO BACKEND =====
  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // clear input for UX
    userInput.value = "";

    // hide menus if open
    safeHide(uploadMenu);
    safeHide(settingsModal);

    // show "thinking" dots
    safeShowFlex(loadingDots);

    // append user msg immediately
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

      // hide dots after response
      safeHide(loadingDots);

      if (resp.ok) {
        appendMessage("PranayAI", data.response || "[no response]");
      } else {
        appendMessage("PranayAI", "Server error talking to model.");
      }
    } catch (err) {
      console.error(err);
      safeHide(loadingDots);
      appendMessage("PranayAI", "Network error.");
    }
  }

  // click send
  if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
  }

  // enter key submit
  if (userInput) {
    userInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // ===== appendMessage helper =====
  function appendMessage(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = sender === "You" ? "user-msg" : "bot-msg";
    bubble.textContent = text;
    chatBox.appendChild(bubble);

    // auto-scroll to bottom
    chatBox.parentElement.scrollTop = chatBox.parentElement.scrollHeight;
  }
});
