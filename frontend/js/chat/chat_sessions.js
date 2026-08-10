// --- KODA Chat Sessions & History Loader UI Module ---

window.startNewChat = function (render = true) {
  // Close sources panel if open when starting a new chat
  const sourcesPanel = document.querySelector('.sources-panel');
  if (sourcesPanel) {
    sourcesPanel.classList.remove('open');
    document.body.classList.remove('sources-open');
  }

  // Clean up any existing empty sessions before creating a new one
  chatSessions = chatSessions.filter(s => s.history && s.history.length > 0);

  currentSessionId = Date.now().toString();
  chatHistory = [];
  document.getElementById('chatbox').innerHTML = "";

  const scrollBtn = document.getElementById("scroll-bottom-btn");
  if (scrollBtn) scrollBtn.classList.remove("show");
  if (typeof isUserScrolledUp !== 'undefined') isUserScrolledUp = false;

  if (chatSessions.length > 50) chatSessions.pop(); // Keep storage clean

  chatSessions.unshift({ id: currentSessionId, title: "New Chat", history: [], html: "" });

  storage.setItem('currentSessionId', currentSessionId);

  try {
    storage.setItem('chatSessions', JSON.stringify(chatSessions));
  } catch (e) {
    console.warn("Storage quota exceeded when starting new chat!");
  }

  pushSyncData();
  updateEmptyChatState();

  if (render) {
    renderSidebar();
    document.getElementById('input').focus();

    // Auto-close sidebar on mobile devices
    if (window.innerWidth <= 1024 && !document.querySelector('.sidebar').classList.contains('collapsed')) {
      window.toggleSidebar();
    }
  }
};

window.loadSession = async function (id) {
  // Close sources panel if open when switching to another chat
  const sourcesPanel = document.querySelector('.sources-panel');
  if (sourcesPanel) {
    sourcesPanel.classList.remove('open');
    document.body.classList.remove('sources-open');
  }

  currentSessionId = id;
  storage.setItem('currentSessionId', id);
  document.getElementById('chatbox').innerHTML = "<div style='padding:20px; text-align:center; color:#888;'>Loading chat history...</div>";

  // Reset Pagination trackers for the new chat
  currentChatOffset = 0;
  hasMoreChatHistory = true;
  isLoadingHistory = false;

  // Verify auth with backend
  try {
    const response = await fetch(`/history/${id}?limit=20&offset=0`, { headers: { "Authorization": `Bearer ${token}` } });
    if (response.status === 401) {
      if (typeof window.handleUnauthorizedToken === 'function') {
        window.handleUnauthorizedToken();
      } else {
        window.location.href = '/login.html';
      }
      return;
    }
    const data = await response.json();
    if (data.history && Array.isArray(data.history)) {
      if (data.history.length < 20) hasMoreChatHistory = false;
      renderChatHistory(data.history);
      if (typeof scrollToBottom === 'function') scrollToBottom();
    } else {
      document.getElementById('chatbox').innerHTML = "";
      chatHistory = [];
    }
  } catch (error) {
    console.error("Failed to fetch history from DB:", error);
    document.getElementById('chatbox').innerHTML = "";
    chatHistory = [];
  }

  const scrollBtn = document.getElementById("scroll-bottom-btn");
  if (scrollBtn) scrollBtn.classList.remove("show");
  if (typeof isUserScrolledUp !== 'undefined') isUserScrolledUp = false;

  updateEmptyChatState();
  renderSidebar();
  document.getElementById('input').focus();
};

window.loadOlderMessages = async function () {
  if (!currentSessionId || !hasMoreChatHistory || isLoadingHistory) return;
  isLoadingHistory = true;

  const chatbox = document.getElementById('chatbox');

  // Show silent loading spinner at the very top of the chat
  const loadingHtml = `<div id="history-loader" style="text-align:center; padding:10px; color:#888;"><span class="btn-spinner"></span> Loading older messages...</div>`;
  chatbox.insertAdjacentHTML('afterbegin', loadingHtml);

  currentChatOffset += 20;

  try {
    const response = await fetch(`/history/${currentSessionId}?limit=20&offset=${currentChatOffset}`, { headers: { "Authorization": `Bearer ${token}` } });
    const data = await response.json();

    const loaderNode = document.getElementById('history-loader');
    if (loaderNode) loaderNode.remove();

    if (data.history && data.history.length > 0) {
      if (data.history.length < 20) hasMoreChatHistory = false;

      // 🛡️ Enterprise Deduplication Safeguard: Ensure we don't duplicate messages if offset shifts!
      const existingSignatures = new Set(chatHistory.map(m => `${m.role}:${m.content}`));
      const uniqueOlderMsgs = data.history.filter(m => !existingSignatures.has(`${m.role}:${m.content}`));

      if (uniqueOlderMsgs.length === 0) {
        isLoadingHistory = false;
        return;
      }

      // Lock the current scroll position so the screen doesn't snap abruptly
      const previousScrollHeight = chatbox.scrollHeight;

      // Temporarily swap chatHistory, render just the old chunk, then merge them safely
      const backupHistory = [...chatHistory];
      const backupHtml = chatbox.innerHTML;

      // We will reuse renderChatHistory by giving it an empty box, grabbing the generated HTML, then assembling
      chatbox.innerHTML = '';
      renderChatHistory(uniqueOlderMsgs);
      const olderHtml = chatbox.innerHTML;

      chatbox.innerHTML = olderHtml + backupHtml;
      chatHistory = [...uniqueOlderMsgs, ...backupHistory];

      // Restore exact scroll position!
      chatbox.scrollTop = chatbox.scrollHeight - previousScrollHeight;

    } else {
      hasMoreChatHistory = false;
    }
  } catch (e) {
    console.error("Failed to load older messages", e);
    const loaderNode = document.getElementById('history-loader');
    if (loaderNode) loaderNode.remove();
  }

  isLoadingHistory = false;
};
