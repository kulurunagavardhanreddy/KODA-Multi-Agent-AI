// --- KODA Global State ---
// Single source of truth for all foundational app-wide variables.
// This file MUST be the very first module loaded.

// 🧠 DYNAMIC STORAGE LOGIC: Guest mode uses session-only memory
const isGuest = localStorage.getItem('isGuest') === 'true';
const storage = isGuest ? sessionStorage : localStorage;
window.isGuest = isGuest;
window.storage = storage;

// 🧠 SAFE STORAGE HELPERS: Prevents corrupt JSON & QuotaExceeded errors from crashing page load
window.safeStorage = {
  get: function (key, fallback = null) {
    try {
      const item = storage.getItem(key);
      if (!item || item === "undefined" || item === "null") return fallback;
      return JSON.parse(item);
    } catch (e) {
      console.warn(`[SafeStorage] Corrupted JSON for '${key}', resetting to fallback.`, e);
      try { storage.removeItem(key); } catch (_) { }
      return fallback;
    }
  },
  set: function (key, value) {
    try {
      storage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
      return true;
    } catch (e) {
      console.warn(`[SafeStorage] Storage setItem failed for '${key}'. Attempting cleanup...`, e);
      if (key === 'chatSessions' && Array.isArray(value)) {
        // Strip heavy HTML content from sessions to save space
        const lightweight = value.map(s => ({ id: s.id, title: s.title, history: s.history || [] }));
        try {
          storage.setItem(key, JSON.stringify(lightweight));
          return true;
        } catch (_) { }
      }
      return false;
    }
  }
};

// 🔒 Auth Check: Redirect to login if no JWT token is found
const token = storage.getItem('token') || localStorage.getItem('token') || sessionStorage.getItem('token');
window.token = token;
if (!token && !window.location.pathname.includes('login')) {
  window.location.href = '/login.html';
}

// 🧠 Global chat history to give the bot memory
var chatHistory = [];
window.chatHistory = chatHistory;

// 🌍 Global variable to store user's detected location
var userLocation = "";
window.userLocation = userLocation;

// 📄 Pending attachment state (document/image waiting to be sent)
var pendingDocument = null;
window.pendingDocument = pendingDocument;

var pendingImage = null;
window.pendingImage = pendingImage;

var isTemporaryChat = false;
window.isTemporaryChat = isTemporaryChat;

// 🧠 Global user/bot identity variables
var userName = storage.getItem('userName') || "User";
window.userName = userName;

var userEmail = storage.getItem('userEmail') || "user@example.com";
window.userEmail = userEmail;

var botName = storage.getItem('botName') || "";
window.botName = botName;

var micLang = storage.getItem('micLang') || "en-IN";
window.micLang = micLang;

var selectedVoiceURI = storage.getItem('ttsVoice') || "";
window.selectedVoiceURI = selectedVoiceURI;

var autoReadResponse = false;
window.autoReadResponse = autoReadResponse;

// 📜 Track whether user has manually scrolled up during AI streaming
var isUserScrolledUp = false;
window.isUserScrolledUp = isUserScrolledUp;

var isProgrammaticScrolling = false;
window.isProgrammaticScrolling = isProgrammaticScrolling;

// 💾 Chat session management (Safely parsed & attached to window!)
var chatSessions = safeStorage.get('chatSessions', []);
window.chatSessions = chatSessions;

var currentSessionId = storage.getItem('currentSessionId');
window.currentSessionId = currentSessionId;

// 🛑 Abort controller for stopping in-progress stream requests
var abortController = null;
window.abortController = abortController;

// 🎨 Active theme
var currentTheme = storage.getItem('theme') || 'dark';
window.currentTheme = currentTheme;

// 📜 Pagination & Infinite Scroll State
var currentChatOffset = 0;
window.currentChatOffset = currentChatOffset;

var hasMoreChatHistory = true;
window.hasMoreChatHistory = hasMoreChatHistory;

var isLoadingHistory = false;
window.isLoadingHistory = isLoadingHistory;
