// --- KODA Shared Chat Importer ---
// Handles importing a publicly shared conversation via its share ID.
// Called when the URL is: /shared/<shareId>

async function importSharedChat(shareId) {
  try {
    const res = await fetch(`/api/shared/${shareId}`);
    if (res.ok) {
      const data = await res.json();
      if (data.history && data.history.length > 0) {
        startNewChat(false);
        chatHistory = data.history;

        const chatbox = document.getElementById("chatbox");
        chatbox.innerHTML = "";

        chatHistory.forEach(msg => {
          const msgId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
          const encodedContent = encodeURIComponent(msg.content).replace(/'/g, "%27");

          if (msg.role === 'user') {
            const isLong = msg.content.length > 600 || (msg.content.match(/\n/g) || []).length > 6;
            const collapseClass = isLong ? " collapsed" : "";
            const hasExpandClass = isLong ? " has-expand-btn" : "";
            const expandBtnHtml = isLong ? `
              <button class="expand-toggle-btn" onclick="toggleMessageExpand(this)" title="Expand text">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="expand-icon"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </button>
            ` : "";

            chatbox.insertAdjacentHTML("beforeend", `
              <div class="message user" id="${msgId}" data-role="user" data-raw="${encodedContent}">
                <div class="user-wrapper">
                  <div class="message-content${hasExpandClass}">
                    ${expandBtnHtml}
                    <div class="message-header"><div class="sender-name">User</div></div>
                    <div class="text-body${collapseClass}">${msg.content}</div>
                  </div>
                </div>
              </div>
            `);
          } else if (msg.role === 'assistant') {
            chatbox.insertAdjacentHTML("beforeend", `
              <div class="message bot" id="${msgId}" data-role="assistant" data-raw="${encodedContent}">
                <div class="message-content">
                  <div class="message-header">
                    <div class="bot-avatar">${botLogoSvg}</div>
                    <div class="sender-name">AI Assistant</div>
                  </div>
                  <div class="text-body">${typeof marked !== 'undefined' ? marked.parse(msg.content) : msg.content}</div>
                </div>
              </div>
            `);
          }
        });

        saveCurrentSession();
        window.history.replaceState({}, document.title, "/");
      }
    } else {
      alert("Shared chat not found.");
      window.location.href = "/";
    }
    updateEmptyChatState();
  } catch (e) {
    console.error("Failed to load shared chat:", e);
  }
}

window.importSharedChat = importSharedChat;
