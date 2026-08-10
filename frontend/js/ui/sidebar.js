// --- KODA Sidebar & Session UI Module ---

window.deleteSession = async function (e, id) {
  e.stopPropagation();

  // Soft Delete via API
  if (!isGuest) {
    try {
      fetch(`/api/history/${id}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
    } catch (error) {
      console.error("Failed to delete session on server", error);
    }
  }

  chatSessions = chatSessions.filter(s => s.id !== id);
  storage.setItem('chatSessions', JSON.stringify(chatSessions));
  pushSyncData();

  if (currentSessionId === id) {
    chatSessions.length > 0 ? loadSession(chatSessions[0].id) : startNewChat();
  } else {
    pushSyncData();
    renderSidebar();
  }
};

window.renderSidebar = function () {
  const list = document.getElementById('history-list');
  if (!list) return;
  list.innerHTML = "";
  chatSessions.forEach(session => {
    if (!session || !session.id) return;
    // Skip empty temporary "New Chat" drafts that haven't sent any messages yet
    if (session.title === "New Chat" && (!session.history || session.history.length === 0)) return;

    const item = document.createElement('div');
    item.className = `history-item ${session.id === currentSessionId ? 'active' : ''}`;
    item.innerHTML = `
      <div class="session-title-text" style="flex-grow: 1; overflow: hidden; text-overflow: ellipsis;">${session.title || "Chat Session"}</div>
      <div class="session-actions">
        <div class="options-btn" onclick="toggleChatOptions(event, '${session.id}')" title="Options">${threeDotsSvg}</div>
      </div>
    `;
    item.onclick = () => loadSession(session.id);
    list.appendChild(item);
  });
};

window.toggleChatOptions = function (e, id) {
  e.stopPropagation();
  let dropdown = document.getElementById('chat-options-dropdown');
  if (!dropdown) {
    dropdown = document.createElement('div');
    dropdown.id = 'chat-options-dropdown';
    dropdown.className = 'chat-options-dropdown';
    document.body.appendChild(dropdown);
  }

  if (dropdown.classList.contains('show') && dropdown.dataset.sessionId === id) {
    dropdown.classList.remove('show');
    return;
  }

  dropdown.dataset.sessionId = id;
  dropdown.innerHTML = `
    <button onclick="editSessionTitle(event, '${id}'); document.getElementById('chat-options-dropdown').classList.remove('show');">${sidebarEditSvg} Rename</button>
    <button onclick="shareSession(event, '${id}'); document.getElementById('chat-options-dropdown').classList.remove('show');">${shareSvg} Share</button>
    <button class="delete-opt" onclick="deleteSession(event, '${id}'); document.getElementById('chat-options-dropdown').classList.remove('show');">${sidebarTrashSvg} Delete</button>
  `;

  const rect = e.currentTarget.getBoundingClientRect();
  dropdown.style.top = `${rect.bottom + window.scrollY}px`;
  dropdown.style.left = `${rect.left + window.scrollX - 100}px`;
  dropdown.classList.add('show');
};

// --- Spotlight Search Modal Logic ---
window.openSearchModal = function () {
  const modal = document.getElementById('search-modal');
  modal.style.display = 'flex';
  const input = document.getElementById('modal-search-input');
  input.value = ''; // Clear prior searches
  input.focus();
  filterModalChats(); // Show all initially
};

window.closeSearchModal = function () {
  document.getElementById('search-modal').style.display = 'none';
};

window.filterModalChats = function () {
  const queryInput = document.getElementById('modal-search-input');
  if (!queryInput) return;
  const query = queryInput.value.toLowerCase();
  const resultsContainer = document.getElementById('modal-search-results');
  if (!resultsContainer) return;
  resultsContainer.innerHTML = '';

  let matchCount = 0;
  chatSessions.forEach(session => {
    if (!session || !session.id) return;

    if (!query || (session.title && session.title.toLowerCase().includes(query))) {
      matchCount++;
      const item = document.createElement('div');
      item.className = 'search-result-item';
      const userMsgCount = session.history ? session.history.filter(m => m.role === 'user').length || Math.ceil(session.history.length / 2) : 0;
      const convLabel = userMsgCount === 1 ? '1 conversation' : `${userMsgCount} conversations`;
      const msgText = userMsgCount > 0 ? `Contains ${convLabel}` : 'Saved chat session';
      item.innerHTML = `
        <div class="search-result-title">${session.title || "Chat Session"}</div>
        <div class="search-result-date">${msgText}</div>
      `;
      item.onclick = () => {
        closeSearchModal();
        loadSession(session.id);
        // Auto close sidebar on mobile if active
        if (window.innerWidth <= 1024 && !document.querySelector('.sidebar').classList.contains('collapsed')) {
          window.toggleSidebar();
        }
      };
      resultsContainer.appendChild(item);
    }
  });

  if (matchCount === 0) {
    resultsContainer.innerHTML = '<div style="padding: 16px; color: #b4b4b4; text-align: center;">No matching chats found.</div>';
  }
};

window.saveCurrentSession = function () {
  // 🚀 Skip saving to local browser storage if Temporary Chat is ON!
  if (!currentSessionId || isTemporaryChat) return;
  const sessionIndex = chatSessions.findIndex(s => s.id === currentSessionId);
  if (sessionIndex !== -1) {
    const session = chatSessions[sessionIndex];
    session.history = chatHistory;

    // 🚀 PHASE 1: Eliminate HTML caching completely! Pure JSON architecture.
    delete session.html;

    // 🧠 AUTO-TITLE GENERATION
    if (session.title === "New Chat" && chatHistory.length > 0) {
      const firstUserMsg = chatHistory.find(m => m.role === 'user');
      if (firstUserMsg && !session.titleGenerated) {
        session.titleGenerated = true; // Lock to prevent multiple network calls
        session.title = "Generating..."; // Show temporary loading state

        // Fire background request to generate professional AI title
        fetch('/api/generate-title', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ message: firstUserMsg.content })
        })
          .then(res => res.json())
          .then(data => {
            if (data.title) {
              const sIdx = chatSessions.findIndex(s => s.id === session.id);
              if (sIdx !== -1) {
                chatSessions[sIdx].title = data.title;
                try {
                  storage.setItem('chatSessions', JSON.stringify(chatSessions));
                } catch (err) {
                  console.warn("Storage quota exceeded on title update:", err);
                }
                renderSidebar();
              }
            }
          })
          .catch(err => {
            console.error("Title generation failed:", err);
          });
      }
    }

    // Move this active session to the top of the list!
    chatSessions.splice(sessionIndex, 1);
    chatSessions.unshift(session);

    try {
      storage.setItem('chatSessions', JSON.stringify(chatSessions));
    } catch (e) {
      if (e.name === 'QuotaExceededError' || e.name === 'NS_ERROR_DOM_QUOTA_REACHED') {
        console.warn("⚠️ Storage quota exceeded! Aggressively cleaning up old sessions...");
        // Keep only the 5 most recent sessions to free up space instantly
        while (chatSessions.length > 5) {
          chatSessions.pop();
        }
        try {
          storage.setItem('chatSessions', JSON.stringify(chatSessions));
        } catch (e2) {
          console.error("Still exceeding quota after cleanup!", e2);
          alert("Your browser's storage is completely full! We had to remove some old chats to keep the bot working.");
        }
      }
    }

    pushSyncData();
    renderSidebar();
  }
};

// --- Inline Edit Chat Title Logic ---
window.editSessionTitle = function (e, id) {
  e.stopPropagation();
  const session = chatSessions.find(s => s.id === id);
  if (!session) return;

  const newTitle = prompt("Rename this chat:", session.title);
  if (newTitle !== null) {
    const cleanedTitle = newTitle.trim();
    if (cleanedTitle !== "") {
      session.title = cleanedTitle;
    } else {
      // If they leave it blank, reset it to "New Chat"
      session.title = "New Chat";
    }
    storage.setItem('chatSessions', JSON.stringify(chatSessions));
    pushSyncData();
    renderSidebar();
  }
};

window.shareSession = async function (e, id) {
  e.stopPropagation();
  const session = chatSessions.find(s => s.id === id);
  if (!session) return;
  if (isGuest) {
    alert("Please log in to share chats.");
    return;
  }
  try {
    const response = await fetch(`/api/share/${id}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (response.ok) {
      const data = await response.json();
      const shareUrl = window.location.origin + data.share_url;

      // Safe fallback for non-HTTPS environments where clipboard API is blocked by the browser
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(shareUrl).then(() => {
          alert(`Link copied to clipboard!\n\n${shareUrl}`);
        }).catch(() => { prompt("Link generated! Copy it below:", shareUrl); });
      } else {
        prompt("Link generated! Copy it below:", shareUrl);
      }
    } else {
      let errorMsg = "Unknown error";
      try { const errData = await response.json(); errorMsg = errData.detail || errorMsg; } catch (e) { }
      alert(`Failed to generate share link.\nServer Status: ${response.status}\nDetails: ${errorMsg}\n\n(Did you completely restart your Python server?)`);
    }
  } catch (error) { console.error(error); alert("Error sharing session: " + error.message); }
};

// --- Scroll to Bottom ---
window.scrollToBottom = function () {
  const chatbox = document.getElementById("chatbox");
  isUserScrolledUp = false; // Reset lock when clicking the down arrow
  chatbox.scrollTo({ top: chatbox.scrollHeight, behavior: 'smooth' });
};

// --- Sidebar Toggle ---
window.toggleSidebar = function () {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;

  sidebar.classList.toggle('collapsed');
  const isCollapsed = sidebar.classList.contains('collapsed');

  // Only persist state on desktop; on mobile always reset to closed
  if (window.innerWidth > 1024) {
    localStorage.setItem('sidebarCollapsed', isCollapsed);
  }

  const openBtn = document.getElementById('open-sidebar-btn');
  if (openBtn) openBtn.setAttribute('title', isCollapsed ? 'Expand menu' : 'Collapse menu');

  document.body.classList.toggle('sidebar-closed', isCollapsed);
};
