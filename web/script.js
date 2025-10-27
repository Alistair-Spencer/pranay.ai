document.addEventListener("DOMContentLoaded", () => {
  // ===== APP STATE =====
  let chats = [];
  let activeChatId = null;

  // holds most recently uploaded image (File + previewURL) waiting to send
  let lastUploadedImage = null;

  // signed-in state
  let currentUserEmail = null;
  let currentUserName = null; // derived from email / google

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

  const chatList          = document.getElementById("chat-list");
  const appRoot           = document.getElementById("app-root");
  const brandNameEl       = document.querySelector(".brand-name");

  // ===== small helpers =====
  function show(el)     { if (el) el.classList.remove("hidden"); }
  function hide(el)     { if (el && !el.classList.contains("hidden")) el.classList.add("hidden"); }
  function toggle(el)   { if (el) el.classList.toggle("hidden"); }

  function scrollToBottom() {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  // render a text bubble into chatBox
  function renderBubble(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = sender === "You" ? "user-msg" : "bot-msg";
    bubble.textContent = text;
    chatBox.appendChild(bubble);
  }

  // render an image bubble into chatBox
  function renderImageBubble(sender, imgURL) {
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
  }

  // update the DOM chatBox to match chats[activeChatId]
  function renderActiveChatMessages() {
    chatBox.innerHTML = "";
    hide(loadingDots);

    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;

    chat.messages.forEach(msg => {
      if (msg.type === "text") {
        renderBubble(msg.role === "user" ? "You" : "PranayAI", msg.content);
      } else if (msg.type === "image") {
        renderImageBubble(msg.role === "user" ? "You" : "PranayAI", msg.urlPreview);
        if (msg.captionText) {
          renderBubble(msg.role === "user" ? "You" : "PranayAI", msg.captionText);
        }
      }
    });

    scrollToBottom();
  }

  // create a new chat object in memory and make it active
  function createNewChat() {
    const id = "chat_" + Date.now();
    const newChat = {
      id,
      title: "New chat",
      messages: [] // {role:'user'|'assistant','type':'text'|'image',content?,urlPreview?,captionText?}
    };
    chats.unshift(newChat);
    activeChatId = id;
    renderChatList();
    renderActiveChatMessages();
    userInput.placeholder = "Message PranayAI...";
  }

  // change which chat is active
  function activateChat(chatId) {
    activeChatId = chatId;
    renderChatList();
    renderActiveChatMessages();
  }

  // make sidebar list reflect chats[]
  function renderChatList() {
    chatList.innerHTML = "";
    chats.forEach(chat => {
      const item = document.createElement("div");
      item.className = "chat-list-item" + (chat.id === activeChatId ? " active-chat" : "");
      item.innerHTML = `<span class="chat-list-title">${chat.title}</span>`;
      item.addEventListener("click", () => {
        activateChat(chat.id);
      });
      chatList.appendChild(item);
    });
  }

  // push a new user message into active chat
  function pushUserTextMessage(text) {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;
    chat.messages.push({
      role: "user",
      type: "text",
      content: text
    });

    // If this is the first message in an empty chat, set chat title
    if (chat.title === "New chat" && text.trim() !== "") {
      chat.title = text.length > 30 ? text.slice(0,30)+"…" : text;
      renderChatList();
    }
  }

  // push an assistant text message
  function pushAssistantTextMessage(text) {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;
    chat.messages.push({
      role: "assistant",
      type: "text",
      content: text
    });
  }

  // push a user image message
  function pushUserImageMessage(previewURL, captionText="") {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;
    chat.messages.push({
      role: "user",
      type: "image",
      urlPreview: previewURL,
      captionText
    });

    // If first message, also rename chat
    if (chat.title === "New chat") {
      chat.title = captionText ? captionText.slice(0,30)+"…" : "Image";
      renderChatList();
    }
  }

  // push an assistant image message (not used yet but ready)
  function pushAssistantImageMessage(previewURL, captionText="") {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;
    chat.messages.push({
      role: "assistant",
      type: "image",
      urlPreview: previewURL,
      captionText
    });
  }

  function showLoadingDots() {
    show(loadingDots);
    scrollToBottom();
  }

  function hideLoadingDots() {
    hide(loadingDots);
  }

  // close popovers/modals so they don’t overlap
  function closeAllFloatingExcept(exceptEl) {
    const list = [
      uploadPopover,
      settingsPopover,
      signinModal,
      backgroundModal,
      prefsModal,
      helpModal
    ];
    list.forEach(el => {
      if (!exceptEl || el !== exceptEl) hide(el);
    });
  }

  function setBackground(url) {
    appRoot.style.backgroundImage = `url('${url}')`;
  }

  // login helpers
  function setSignedIn(email) {
    currentUserEmail = email;
    currentUserName  = deriveNameFromEmail(email);

    // update sidebar
    signedInEmail.textContent = email;
    show(signedInRow);

    signinBtnText.textContent = "Signed in";
    onlineStatus.textContent = "Online";

    // update brand line "PranayAI"
    if (brandNameEl) {
      if (currentUserName) {
        brandNameEl.textContent = `PranayAI (${currentUserName})`;
      } else {
        brandNameEl.textContent = "PranayAI";
      }
    }
  }

  function clearSignedIn() {
    currentUserEmail = null;
    currentUserName  = null;

    signedInEmail.textContent = "";
    hide(signedInRow);

    signinBtnText.textContent = "Sign in";
    onlineStatus.textContent = "Online";

    if (brandNameEl) {
      brandNameEl.textContent = "PranayAI";
    }
  }

  function deriveNameFromEmail(email) {
    // super simple: part before '@'
    if (!email) return "";
    const atIndex = email.indexOf("@");
    if (atIndex === -1) return email;
    return email.slice(0, atIndex);
  }

  // ===== init first chat if none =====
  createNewChat(); // creates 1 chat, sets activeChatId

  // ===== NEW CHAT CLICK =====
  if (newChatBtn) {
    newChatBtn.addEventListener("click", e => {
      e.stopPropagation();
      closeAllFloatingExcept(null);
      createNewChat();
    });
  }

  // ===== SIGN-IN BTN => open modal =====
  if (signinBtn) {
    signinBtn.addEventListener("click", e => {
      e.stopPropagation();
      closeAllFloatingExcept(null);
      show(signinModal);
    });
  }

  // ===== SIGN-IN MODAL BEHAVIOR =====
  if (signinClose) {
    signinClose.addEventListener("click", e => {
      e.stopPropagation();
      hide(signinModal);
    });
  }
  if (signinModal) {
    // click outside card closes
    signinModal.addEventListener("click", e => {
      const card = signinModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(signinModal);
      }
    });
  }

  // Google sign-in (LOCAL MOCK)
  // We are NOT calling backend because that was flaky for you.
  // We just pretend success with a demo email.
  if (googleLoginBtn) {
    googleLoginBtn.addEventListener("click", e => {
      e.stopPropagation();
      const fakeEmail = "you@gmail.com";
      setSignedIn(fakeEmail);
      hide(signinModal);
    });
  }

  // Email/password sign-in
  if (emailLoginBtn) {
    emailLoginBtn.addEventListener("click", e => {
      e.stopPropagation();
      const emailVal = loginEmailInput.value.trim();
      // ignoring password check for now
      if (emailVal) {
        setSignedIn(emailVal);
      }
      hide(signinModal);
    });
  }

  // ===== MENU ⋯ BUTTON / SETTINGS POPOVER =====
  if (menuButton) {
    menuButton.addEventListener("click", e => {
      e.stopPropagation();
      // toggle only this popover, close all else
      const willShow = settingsPopover.classList.contains("hidden");
      closeAllFloatingExcept(willShow ? settingsPopover : null);
      toggle(settingsPopover);
    });
  }

  // settings popover click actions
  if (settingsPopover) {
    settingsPopover.addEventListener("click", e => {
      const item = e.target.closest(".popover-item");
      if (!item) return;
      const action = item.getAttribute("data-action");

      if (action === "open-settings") {
        hide(settingsPopover);
        closeAllFloatingExcept(prefsModal);
        show(prefsModal);
      } else if (action === "open-background") {
        hide(settingsPopover);
        closeAllFloatingExcept(backgroundModal);
        show(backgroundModal);
      } else if (action === "open-help") {
        hide(settingsPopover);
        closeAllFloatingExcept(helpModal);
        show(helpModal);
      } else if (action === "sign-out") {
        hide(settingsPopover);
        clearSignedIn();
      }
    });
  }

  // clicking outside popovers closes them
  document.addEventListener("click", e => {
    const clickedSettings = settingsPopover.contains(e.target) || menuButton.contains(e.target);
    const clickedUpload   = uploadPopover.contains(e.target)   || plusButton.contains(e.target);

    if (!clickedSettings) hide(settingsPopover);
    if (!clickedUpload)   hide(uploadPopover);
  });

  // ===== BACKGROUND MODAL =====
  if (backgroundClose) {
    backgroundClose.addEventListener("click", e => {
      e.stopPropagation();
      hide(backgroundModal);
    });
  }
  if (backgroundModal) {
    // click outside card closes
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

  // custom bg upload
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
    prefsClose.addEventListener("click", e => {
      e.stopPropagation();
      hide(prefsModal);
    });
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
    helpClose.addEventListener("click", e => {
      e.stopPropagation();
      hide(helpModal);
    });
  }
  if (helpModal) {
    helpModal.addEventListener("click", e => {
      const card = helpModal.querySelector(".overlay-card");
      if (!card.contains(e.target)) {
        hide(helpModal);
      }
    });
  }

  // ===== PLUS BUTTON / UPLOAD IMAGE =====
  if (plusButton) {
    plusButton.addEventListener("click", e => {
      e.stopPropagation();
      const willShow = uploadPopover.classList.contains("hidden");
      closeAllFloatingExcept(willShow ? uploadPopover : null);
      toggle(uploadPopover);
    });
  }

  if (uploadImageTrigger) {
    uploadImageTrigger.addEventListener("click", e => {
      e.stopPropagation();
      hide(uploadPopover);

      if (imageFileInput) {
        imageFileInput.value = ""; // so you can pick same file again
        imageFileInput.click();
      }
    });
  }

  // when user picks image
  if (imageFileInput) {
    imageFileInput.addEventListener("change", () => {
      const file = imageFileInput.files && imageFileInput.files[0];
      if (!file) return;

      const previewURL = URL.createObjectURL(file);

      // remember this before sending to backend
      lastUploadedImage = {
        file,
        previewURL
      };

      // push to active chat state immediately
      pushUserImageMessage(previewURL, "");
      renderActiveChatMessages();
    });
  }

  // ===== SENDING MESSAGES (TEXT OR TEXT+IMAGE) =====
  async function sendMessage() {
    const text = userInput.value.trim();
    const hadImage = !!lastUploadedImage;

    if (!text && !hadImage) {
      return;
    }

    // record in state first
    if (hadImage) {
      // update captionText on the just-added image message
      const chat = chats.find(c => c.id === activeChatId);
      if (chat && chat.messages.length > 0) {
        const lastMsg = chat.messages[chat.messages.length - 1];
        if (lastMsg.type === "image" && lastMsg.role === "user" && !lastMsg.captionText) {
          lastMsg.captionText = text;
        }
      }
    } else {
      // just text
      pushUserTextMessage(text);
    }

    userInput.value = "";

    renderActiveChatMessages();
    showLoadingDots();

    try {
      let assistantReply = "";

      if (hadImage && lastUploadedImage) {
        // send multipart form data for vision route (future back end)
        const fd = new FormData();
        fd.append("message", text);
        fd.append("session_id", activeChatId);
        fd.append("file", lastUploadedImage.file);

        const resp = await fetch("/chat-image", {
          method: "POST",
          body: fd
        });

        const data = await resp.json();
        if (resp.ok) {
          assistantReply = data.response || "[no response]";
        } else {
          assistantReply = "Image route error.";
        }
      } else {
        // normal text route
        const resp = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            session_id: activeChatId,
            consent_ok: true
          })
        });
        const data = await resp.json();
        if (resp.ok) {
          assistantReply = data.response || "[no response]";
        } else {
          assistantReply = "Server error talking to model.";
        }
      }

      hideLoadingDots();

      // save assistant reply to active chat
      const chat = chats.find(c => c.id === activeChatId);
      if (chat) {
        chat.messages.push({
          role: "assistant",
          type: "text",
          content: assistantReply
        });
      }

      // clear the remembered image after we send
      lastUploadedImage = null;

      renderActiveChatMessages();

    } catch (err) {
      console.error(err);
      hideLoadingDots();

      const chat = chats.find(c => c.id === activeChatId);
      if (chat) {
        chat.messages.push({
          role: "assistant",
          type: "text",
          content: "Network error."
        });
      }
      renderActiveChatMessages();
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
