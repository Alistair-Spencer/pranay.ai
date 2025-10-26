document.addEventListener("DOMContentLoaded", () => {
  const signInModal = document.getElementById("signin-modal");
  const settingsModal = document.getElementById("settings-modal");
  const menuButton = document.getElementById("menu-button");
  const plusButton = document.getElementById("plus-button");
  const uploadMenu = document.getElementById("upload-menu");
  const loadingDots = document.getElementById("loading-dots");
  const sendButton = document.getElementById("send-button");

  // Hide all modals on load
  [signInModal, settingsModal, uploadMenu].forEach(el => {
    if (el) el.style.display = "none";
  });
  if (loadingDots) loadingDots.style.display = "none";

  // ===== SIGN-IN =====
  const openSignIn = () => {
    signInModal.style.display = "flex";
  };
  const closeSignIn = () => {
    signInModal.style.display = "none";
  };
  document.getElementById("signin-close")?.addEventListener("click", closeSignIn);
  document.getElementById("signin-btn")?.addEventListener("click", openSignIn);

  // ===== MENU (three dots) =====
  menuButton?.addEventListener("click", () => {
    settingsModal.style.display =
      settingsModal.style.display === "flex" ? "none" : "flex";
  });

  // ===== PLUS BUTTON (upload image) =====
  plusButton?.addEventListener("click", () => {
    uploadMenu.style.display =
      uploadMenu.style.display === "flex" ? "none" : "flex";
  });

  // ===== SEND MESSAGE =====
  sendButton?.addEventListener("click", async () => {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    loadingDots.style.display = "inline-block";

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });
      const data = await res.json();

      loadingDots.style.display = "none";
      appendMessage("You", message);
      appendMessage("PranayAI", data.response);
    } catch (err) {
      console.error(err);
      loadingDots.style.display = "none";
    }
  });

  // ===== Message appender =====
  function appendMessage(sender, text) {
    const chatBox = document.getElementById("chat-box");
    const msg = document.createElement("div");
    msg.className = sender === "You" ? "user-msg" : "bot-msg";
    msg.innerText = `${sender}: ${text}`;
    chatBox.appendChild(msg);
  }
});
