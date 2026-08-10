// frontend/js/ui/toolbar.js

// --- KODA Toolbar Controls ---
// Handles the attach file menu, temporary chat toggle, and export menu.

// --- Attach Menu Toggle ---
window.toggleAttachMenu = function (e) {
  e.stopPropagation();
  const dropdown = document.getElementById('attach-dropdown');
  if (dropdown) dropdown.classList.toggle('show');
};

// --- Temporary Chat Toggle ---
// When active, AI responses are NOT saved to session history.
window.toggleTemporaryChat = function (e) {
  if (e) e.stopPropagation();
  isTemporaryChat = !isTemporaryChat;
  const btn = document.getElementById("temp-chat-btn");
  const icon = document.getElementById("temp-chat-icon");
  if (isTemporaryChat) {
    btn.setAttribute("title", "Temporary Chat (ON)");
    btn.style.color = "#10a37f"; // Green active state
    icon.innerHTML = '<path d="M20.5 14.9A9 9 0 0 0 9.1 3.5"></path><path d="M5.3 5.3A9 9 0 0 0 4 16.1L2 22l5.9-2a9 9 0 0 0 7.1-.6"></path><line x1="2" y1="2" x2="22" y2="22"></line>';
  } else {
    btn.setAttribute("title", "Temporary Chat (OFF)");
    btn.style.color = ""; // Revert to default
    icon.innerHTML = '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"></path>';
  }
};

// --- Export Format Menu Toggle ---
window.toggleExportMenu = function (e) {
  e.stopPropagation();
  const dropdown = document.getElementById('export-dropdown');
  if (dropdown) dropdown.classList.toggle('show');
};
