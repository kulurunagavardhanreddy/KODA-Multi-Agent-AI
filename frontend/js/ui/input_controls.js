// frontend/js/ui/input_controls.js

// --- KODA Input Controls ---
// Manages chat input field state, send/stop button visibility,
// welcome screen greeting, and keyboard/click shortcut helpers.

window.stopGenerating = function () {
  if (abortController) abortController.abort();
};

window.toggleSendButtonState = function () {
  const sendBtn = document.getElementById("send-btn");
  const voiceModeBtn = document.getElementById("voice-mode-btn");
  const inputField = document.getElementById("input");
  const clearBtn = document.getElementById("clear-btn");

  if (!sendBtn || !inputField) return;
  const isGenerating = abortController !== null;

  if (isGenerating || inputField.value.trim() !== "" || pendingDocument !== null || pendingImage !== null) {
    sendBtn.style.display = "block";
    if (voiceModeBtn) voiceModeBtn.style.display = "none";
  } else {
    sendBtn.style.display = "none";
    if (voiceModeBtn) voiceModeBtn.style.display = "flex";
  }

  if (clearBtn) {
    clearBtn.style.display = inputField.value.trim() !== "" ? "flex" : "none";
  }
};

window.updateEmptyChatState = function () {
  const mainContent = document.getElementById("main-content");
  if (chatHistory.length === 0) {
    mainContent.classList.add("empty-chat");

    const greetings = [
      "How can I help you today?",
      "What's on your mind?",
      "How can I assist you right now?",
      "Ready to build something great?",
      "What would you like to explore today?",
      "How can I make your day easier?",
      "What shall we create today?"
    ];
    const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
    const firstName = (userName && userName !== "User" && userName !== "Guest") ? userName.split(" ")[0] : "there";

    const welcomeH2 = document.querySelector('.welcome-screen h2');
    if (welcomeH2) {
      welcomeH2.innerHTML = `Hi ${firstName},<br><span class="greeting-sub">${randomGreeting}</span>`;
    }
  } else {
    mainContent.classList.remove("empty-chat");
  }
};

window.clearInput = function () {
  const inputField = document.getElementById("input");
  inputField.value = "";
  inputField.style.height = "auto";
  if (typeof dictationBaseText !== 'undefined') {
    dictationBaseText = "";
  }
  toggleSendButtonState();
  inputField.focus();
};

// Clickable suggestion pill logic
window.sendSuggestion = function (text) {
  document.getElementById('input').value = text;
  sendMessage();
};

// Handle Enter key in textarea (Shift+Enter for new line)
window.handleEnter = function (event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
};
