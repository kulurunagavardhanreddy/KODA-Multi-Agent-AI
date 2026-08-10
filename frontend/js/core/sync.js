// frontend/js/core/sync.js

// --- KODA Cloud Sync Module ---
// Handles two-way sync of user settings and chat sessions to the backend.
// Allows seamless experience across multiple devices.

let isSyncing = false;
let pendingSync = false;

async function loadSyncData() {
  if (isGuest || !token || token === "guest_token") return;
  try {
    const res = await fetch('/api/sync', { headers: { 'Authorization': `Bearer ${token}` } });
    if (res.status === 401) {
      if (typeof window.handleUnauthorizedToken === 'function') window.handleUnauthorizedToken();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      if (data.sync_data) {
        const parsed = JSON.parse(data.sync_data);
        if (parsed.chatSessions) {
          chatSessions = parsed.chatSessions;
          storage.setItem('chatSessions', JSON.stringify(chatSessions));
          if (typeof window.renderSidebar === 'function') window.renderSidebar();
        }
        if (parsed.userName) { userName = parsed.userName; storage.setItem('userName', userName); }
        if (parsed.botName) { botName = parsed.botName; storage.setItem('botName', botName); }
        if (parsed.micLang) { micLang = parsed.micLang; storage.setItem('micLang', micLang); }
        if (parsed.ttsVoice) { selectedVoiceURI = parsed.ttsVoice; storage.setItem('ttsVoice', selectedVoiceURI); }
      }
    }
  } catch (e) { console.error("Sync load error", e); }
}

async function pushSyncData() {
  if (isGuest || !token || token === "guest_token") return;

  if (isSyncing) {
    pendingSync = true;
    return;
  }

  isSyncing = true;
  pendingSync = false;

  const syncPayload = {
    chatSessions: chatSessions,
    userName: userName,
    botName: botName,
    micLang: micLang,
    ttsVoice: selectedVoiceURI
  };
  try {
    const res = await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ sync_data: JSON.stringify(syncPayload) })
    });
    if (res.status === 401) {
      isSyncing = false;
      if (typeof window.handleUnauthorizedToken === 'function') window.handleUnauthorizedToken();
      return;
    }
  } catch (e) { console.error("Sync push error", e); }

  isSyncing = false;
  if (pendingSync) {
    pushSyncData();
  }
}

window.loadSyncData = loadSyncData;
window.pushSyncData = pushSyncData;
