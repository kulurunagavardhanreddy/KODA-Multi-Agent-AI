// --- KODA Chat Renderer UI Module ---

window.renderChatHistory = function (history) {
  const chatbox = document.getElementById('chatbox');
  chatbox.innerHTML = '';
  chatHistory = [];

  history.forEach(msg => {
    if (!msg || !msg.role) return;
    const msgContent = msg.content || "";
    const msgId = `${msg.role}-msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const encodedMessage = encodeURIComponent(msgContent).replace(/'/g, "%27");

    if (msg.role === 'user') {
      const cleanUserText = msgContent.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");

      const isLong = msgContent.length > 600 || (msgContent.match(/\n/g) || []).length > 6;
      const collapseClass = isLong ? " collapsed" : "";
      const hasExpandClass = isLong ? " has-expand-btn" : "";
      const expandBtnHtml = isLong ? `
                <button class="expand-toggle-btn" onclick="toggleMessageExpand(this)" title="Expand text">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="expand-icon"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </button>
            ` : "";

      chatbox.insertAdjacentHTML("beforeend", `
                <div class="message user" id="${msgId}" data-role="user" data-raw="${encodedMessage}">
                    <div class="user-wrapper">
                        <div class="message-content${hasExpandClass}">
                            ${expandBtnHtml}
                            <div class="message-header"><div class="sender-name">${userName || "You"}</div></div>
                            <div class="text-body${collapseClass}">${cleanUserText}</div>
                        </div>
                        <div class="message-actions">
                            <button class="action-btn" title="Edit" onclick="editMessage('${msgId}')">${typeof editSvg !== 'undefined' ? editSvg : '✏️'}</button>
                            <button class="action-btn" title="Copy" onclick="copyMessageText(this)">${typeof copySvg !== 'undefined' ? copySvg : '📋'}</button>
                        </div>
                    </div>
                </div>
            `);
    } else if (msg.role === 'assistant') {
      let displayMarkdown = msg.content;

      // Clean up any markdown code blocks wrapping the map card
      if (displayMarkdown.includes("koda-map-card")) {
        displayMarkdown = displayMarkdown.replace(/```(?:html|xml)?\s*(<div class=["']koda-map-card["'][\s\S]*?<\/div>)\s*```/gi, "$1");
      }

      let suggestionsHtml = "";
      let followUpRegex = /<followup>([\s\S]*?)<\/followup>/i;
      let hasMatch = displayMarkdown.match(followUpRegex);
      if (!hasMatch) {
        followUpRegex = /(?:[#\s*-]*)*(?:\*\*|__)?[Ff]ollow-up\s+(?:[Qq]uestions?|[Oo]ptions?):?(?:\*\*|__)?\s*([\s\S]+)$/i;
        hasMatch = displayMarkdown.match(followUpRegex);
      }
      if (hasMatch) {
        displayMarkdown = displayMarkdown.replace(followUpRegex, (match, listBlock) => {
          const items = listBlock.split('\n');
          items.forEach(item => {
            const cleanQuestion = item.replace(/^[ \t]*(?:-\s*|\*\s*|\d+\.\s*)/, '').replace(/^[\[\]*"'`_-]+|[\[\]*"'`_-]+$/g, '').trim();
            if (cleanQuestion) {
              const safeQuestion = encodeURIComponent(cleanQuestion).replace(/'/g, "%27");
              suggestionsHtml += `<button class="suggestion-pill" onclick="sendSuggestion(decodeURIComponent('${safeQuestion}'))">${cleanQuestion}</button>`;
            }
          });
          return "";
        });
      }

      const rawText = (displayMarkdown || "").trim();
      const encodedClean = encodeURIComponent(rawText).replace(/'/g, "%27");
      let renderedMarkdown = rawText;
      try {
        const preprocessed = wrapRawMermaidBlocks(rawText);
        renderedMarkdown = (typeof marked !== 'undefined' && marked.parse) ? marked.parse(preprocessed) : preprocessed;
      } catch (e) {
        console.warn("Markdown render error fallback:", e);
        renderedMarkdown = rawText.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
      }
      const finalHtml = renderedMarkdown + (suggestionsHtml ? `<div class="suggestions-container" style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px;">${suggestionsHtml}</div>` : "");

      chatbox.insertAdjacentHTML("beforeend", `
                <div class="message bot" id="${msgId}" data-role="assistant" data-raw="${encodedMessage}" data-copy-text="${encodedClean}">
                    <div class="message-content">
                        <div class="message-header">
                            <div class="bot-avatar">${typeof botLogoSvg !== 'undefined' ? botLogoSvg : '🤖'}</div>
                            <div class="sender-name">${botName || "AI Assistant"}</div>
                        </div>
                        <div class="text-body">${finalHtml}</div>
                        <div class="message-actions" style="display: flex;">
                            <button class="action-btn" title="Translate" onclick="translateMessage('${msgId}', this)">${typeof translateSvg !== 'undefined' ? translateSvg : '🌐'}</button>
                            <button class="action-btn" title="Read Aloud" onclick="toggleSpeak('${msgId}', this)">${typeof speakerSvg !== 'undefined' ? speakerSvg : '🔊'}</button>
                            <button class="action-btn" title="Copy" onclick="copyMessageText(this)">${typeof copySvg !== 'undefined' ? copySvg : '📋'}</button>
                            <button class="action-btn" title="Regenerate" onclick="regenerateMessage('${msgId}')">${typeof reloadSvg !== 'undefined' ? reloadSvg : '🔄'}</button>
                        </div>
                    </div>
                </div>
            `);
      applyCodeBlockFormatting(chatbox.lastElementChild, true);
    }
    chatHistory.push({ id: msgId, role: msg.role, content: msg.content });
  });
  chatbox.scrollTop = chatbox.scrollHeight;
};

// --- Expand/Collapse Long Message Logic ---
window.toggleMessageExpand = function (btn) {
  const content = btn.closest('.message-content');
  const textBody = content.querySelector('.text-body');

  if (textBody.classList.contains('collapsed')) {
    textBody.classList.remove('collapsed');
    content.classList.add('expanded');
    btn.setAttribute('title', 'Collapse text');
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="expand-icon" style="transform: rotate(180deg);"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
  } else {
    textBody.classList.add('collapsed');
    content.classList.remove('expanded');
    btn.setAttribute('title', 'Expand text');
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="expand-icon"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
  }
};

window.toggleSpeak = function (msgId, btnElement) {
  if (btnElement.innerHTML.includes('#ff4a4a')) {
    stopAllAudio();
    return;
  }
  stopAllAudio();

  const msgNode = document.getElementById(msgId);
  let textToSpeak = "";

  const transBox = msgNode.querySelector('.translation-box .trans-content');
  if (transBox) {
    textToSpeak = transBox.innerText || transBox.textContent;
  } else {
    const clone = msgNode.cloneNode(true);
    clone.querySelectorAll('.code-header, .code-wrapper, .suggestions-container, .translation-box').forEach(el => el.remove());
    textToSpeak = clone.innerText || clone.textContent;
  }

  playTextOutLoud(textToSpeak, btnElement);
};

window.playTextOutLoud = async function (text, btnElement) {
  if (btnElement.innerHTML.includes('#ff4a4a')) {
    stopAllAudio();
    return;
  }
  stopAllAudio();

  let cleanText = text.replace(/[*_#`~>|\-\\/]/g, ' ');
  cleanText = cleanText.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, '');

  const detectedLang = detectLanguageCode(cleanText) || micLang || "en-US";
  const voices = window.speechSynthesis.getVoices();
  let localVoice = null;

  if (detectedLang) {
    const langPrefix = detectedLang.split('-')[0];
    localVoice = voices.find(v => v.lang.startsWith(langPrefix) && v.name.includes("Google")) ||
      voices.find(v => v.lang.startsWith(langPrefix));
  }

  // 🧠 FAST FRONTEND TTS ONLY
  const utterance = new SpeechSynthesisUtterance(cleanText);
  if (localVoice) utterance.voice = localVoice;
  else if (selectedVoiceURI) {
    const customVoice = voices.find(v => v.voiceURI === selectedVoiceURI);
    if (customVoice) utterance.voice = customVoice;
  }
  utterance.lang = detectedLang;

  utterance.onstart = () => {
    btnElement.innerHTML = speakerStopSvg;
    if (isVoiceMode) {
      document.getElementById("voice-visualizer").className = "speaking";
      document.getElementById("voice-text").innerText = "Speaking...";
    }
  };
  utterance.onend = () => { btnElement.innerHTML = speakerSvg; autoReadResponse = false; if (isVoiceMode) startListening(); };
  utterance.onerror = () => { btnElement.innerHTML = speakerSvg; if (isVoiceMode) startListening(); };

  window.speechSynthesis.speak(utterance);
};

// --- Translate Logic ---
let pendingTranslateMsgId = null;
window.translateMessage = function (msgId, btnElement) {
  const msgNode = document.getElementById(msgId);
  if (!msgNode) return;

  pendingTranslateMsgId = msgId;
  document.getElementById('translate-modal').style.display = 'flex';
};

window.closeTranslateModal = function () {
  document.getElementById('translate-modal').style.display = 'none';
  pendingTranslateMsgId = null;
};

window.confirmTranslation = async function () {
  if (!pendingTranslateMsgId) return;
  const msgId = pendingTranslateMsgId;
  const targetLang = document.getElementById('translate-lang-select').value;
  closeTranslateModal();

  const msgNode = document.getElementById(msgId);
  const clone = msgNode.cloneNode(true);
  clone.querySelectorAll('.code-header, .code-wrapper, .suggestions-container, .translation-box').forEach(el => el.remove());
  const textToTranslate = clone.innerText || clone.textContent;

  const transBox = document.createElement("div");
  transBox.className = "translation-box";
  transBox.style.marginTop = "16px";
  transBox.style.paddingTop = "12px";
  transBox.style.borderTop = "1px dashed rgba(128,128,128,0.4)";

  // 🎨 ADD DEDICATED ACTION BUTTONS TO THE TRANSLATION BOX ITSELF!
  transBox.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; color:#10a37f; font-size:0.85rem; font-weight:bold; margin-bottom:8px; border-bottom: 1px dashed rgba(128,128,128,0.2); padding-bottom: 6px;">
      <span>${targetLang} Translation:</span>
      <div style="display:flex; gap: 14px; align-items:center;">
          <button title="Copy Translation" onclick="copyMessageText(this, encodeURIComponent(this.closest('.translation-box').querySelector('.trans-content').innerText))" style="background:none;border:none;color:#b4b4b4;cursor:pointer;padding:0;display:flex;align-items:center;">${copySvg}</button>
          <button title="Read Translation" onclick="playTextOutLoud(this.closest('.translation-box').querySelector('.trans-content').innerText, this)" style="background:none;border:none;color:#b4b4b4;cursor:pointer;padding:0;display:flex;align-items:center;">${speakerSvg}</button>
          <button title="Close" onclick="this.closest('.translation-box').remove()" style="background:none;border:none;color:#ff4a4a;cursor:pointer;font-size:1.1rem;padding:0;display:flex;align-items:center;line-height:1;">✖</button>
      </div>
    </div><div class="trans-content">Translating <span class="btn-spinner"></span></div>`;

  msgNode.closest('.message-content').appendChild(transBox); // Append BELOW the 4 main action buttons!

  const transContent = transBox.querySelector(".trans-content");
  let rawMarkdown = "";

  try {
    const response = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
      body: JSON.stringify({ text: textToTranslate, target_language: targetLang })
    });

    if (!response.ok) throw new Error("Translation failed");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;
    let buffer = "";

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const message = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          if (message.startsWith("data: ")) {
            const dataStr = message.slice(6);
            try {
              const dataObj = JSON.parse(dataStr);
              if (dataObj.chunk) rawMarkdown += dataObj.chunk;
              transContent.innerHTML = marked.parse(wrapRawMermaidBlocks(rawMarkdown));
            } catch (e) { }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }
    }
    applyCodeBlockFormatting(transBox, true);
  } catch (e) {
    transContent.innerHTML = `<span style="color:#ff4a4a;">Failed to translate.</span>`;
  }
};

// --- Action Button Functions ---
window.copyMessageText = function (btn) {
  const msgWrapper = btn.closest(".message");
  if (!msgWrapper) return;
  const encoded = msgWrapper.getAttribute("data-copy-text") || msgWrapper.getAttribute("data-raw") || "";
  let text = decodeURIComponent(encoded);
  text = text.replace(/\r?\n/g, "\r\n"); // Fix for some editors/OS
  navigator.clipboard.writeText(text).then(() => {
    const originalIcon = btn.innerHTML;
    btn.innerHTML = checkSvg;
    setTimeout(() => {
      btn.innerHTML = originalIcon;
    }, 2000);
  });
};

window.editMessage = function (param1, param2) {
  let messageId;
  let messageElement;
  let originalText = "";

  // Backward compatibility for old chats in localStorage
  if (typeof param1 === 'string') {
    messageId = param1;
    messageElement = document.getElementById(messageId);
    if (!messageElement) return;

    const messageFromHistory = chatHistory.find(m => m.id === messageId);
    if (messageFromHistory) {
      originalText = messageFromHistory.content;
    } else {
      originalText = messageElement.querySelector(".text-body").innerText;
    }
  } else {
    const btn = param1;
    messageElement = btn.closest(".message");
    if (!messageElement) return;
    messageId = messageElement.id || `user-msg-legacy-${Date.now()}`;
    messageElement.id = messageId;
    originalText = decodeURIComponent(param2);
  }

  const messageContent = messageElement.querySelector(".message-content");
  const textBody = messageContent.querySelector(".text-body");
  const actions = messageElement.querySelector(".message-actions");
  const expandBtn = messageContent.querySelector(".expand-toggle-btn");

  // Hide current text and actions
  textBody.style.display = "none";
  if (actions) actions.style.display = "none";
  if (expandBtn) expandBtn.style.display = "none";

  // Add class to expand the message bubble to full width
  messageContent.classList.add("is-editing");

  const editDiv = document.createElement("div");
  editDiv.className = "edit-container";

  const textarea = document.createElement("textarea");
  textarea.className = "edit-textarea";
  textarea.value = originalText;

  textarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
  });
  setTimeout(() => {
    textarea.style.height = 'auto';
    textarea.style.height = (textarea.scrollHeight) + 'px';
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }, 0);

  const btnContainer = document.createElement("div");
  btnContainer.className = "edit-btn-container";

  const saveBtn = document.createElement("button");
  saveBtn.className = "save-edit-btn";
  saveBtn.innerText = "Send";
  saveBtn.disabled = true; // Set to idle by default

  textarea.addEventListener("input", () => {
    saveBtn.disabled = textarea.value.trim() === originalText.trim() || textarea.value.trim() === "";
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "cancel-edit-btn";
  cancelBtn.innerText = "Cancel";

  // --- CORE LOGIC FOR RE-SUBMITTING ---
  saveBtn.onclick = () => {
    const newText = textarea.value.trim();
    if (!newText) return;

    // Show Spinner & Disable UI
    saveBtn.innerHTML = '<span class="btn-spinner"></span>';
    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    textarea.disabled = true;

    setTimeout(() => {
      editDiv.remove();
      textBody.style.display = "block";
      if (actions) actions.style.display = "flex";
      if (expandBtn) expandBtn.style.display = "flex";
      messageContent.classList.remove("is-editing");

      createBranch(messageElement, newText, false);
    }, 400); // Wait 400ms to show the spinner gracefully
  };

  cancelBtn.onclick = () => {
    editDiv.remove();
    textBody.style.display = "block";
    if (actions) actions.style.display = "flex";
    if (expandBtn) expandBtn.style.display = "flex";
    messageContent.classList.remove("is-editing");
  };

  btnContainer.appendChild(cancelBtn);
  btnContainer.appendChild(saveBtn);
  editDiv.appendChild(textarea);
  editDiv.appendChild(btnContainer);

  messageContent.appendChild(editDiv);
};

// --- Regenerate Message Logic ---
window.regenerateMessage = function (botMsgId) {
  const botMsgElement = document.getElementById(botMsgId).closest('.message');
  if (!botMsgElement) return;

  // Find the immediate preceding user message
  let prev = botMsgElement.previousElementSibling;
  while (prev && !prev.classList.contains('user')) {
    prev = prev.previousElementSibling;
  }
  if (!prev) return;

  const userMsgId = prev.id;
  const messageFromHistory = chatHistory.find(m => m.id === userMsgId);
  const textToResend = messageFromHistory ? messageFromHistory.content : prev.querySelector(".text-body").innerText;

  createBranch(botMsgElement, textToResend, true);
};

// 🌍 HELPER: Automatically detect regional scripts for TTS
window.detectLanguageCode = function (text) {
  if (/[\u0C00-\u0C7F]/.test(text)) return 'te-IN'; // Telugu
  if (/[\u0900-\u097F]/.test(text)) return 'hi-IN'; // Hindi / Marathi
  if (/[\u0B80-\u0BFF]/.test(text)) return 'ta-IN'; // Tamil
  if (/[\u0C80-\u0CFF]/.test(text)) return 'kn-IN'; // Kannada
  if (/[\u0D00-\u0D7F]/.test(text)) return 'ml-IN'; // Malayalam
  return null; // Fallback to user's selected default
};
function detectLanguageCode(text) {
  return window.detectLanguageCode(text);
}

// --- Text-to-Speech (Read Aloud) Logic ---
window.currentAudio = null;

window.stopAllAudio = function () {
  if (window.currentAudio) {
    window.currentAudio.pause();
    window.currentAudio.currentTime = 0;
    window.currentAudio = null;
  }
  window.speechSynthesis.cancel();
  document.querySelectorAll('button[title="Read Aloud"], button[title="Read Translation"]').forEach(btn => btn.innerHTML = speakerSvg);
};
