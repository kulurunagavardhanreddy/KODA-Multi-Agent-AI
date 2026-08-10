// --- KODA Clear All Chats UI Module ---
window.clearAllHistory = function () {
  if (confirm("Are you sure you want to delete all chat history? This cannot be undone.")) {
    chatSessions = [];
    storage.removeItem('chatSessions');
    storage.removeItem('currentSessionId');
    pushSyncData();
    startNewChat();
    const dropdown = document.getElementById('settings-dropdown') || document.querySelector('.settings-dropdown');
    if (dropdown) dropdown.classList.remove('show');
  }
};
