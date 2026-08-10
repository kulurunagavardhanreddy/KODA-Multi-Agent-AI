// --- Message Sender & SSE Streaming UI Module ---

// 🌍 Get REAL-TIME GPS location
async function getLiveLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      userLocation = "";
      resolve();
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        userLocation = `${lat},${lon}`; // 🔥 IMPORTANT FORMAT
        resolve();
      },
      (err) => {
        console.log("Location permission denied or timeout:", err.message);
        userLocation = "";
        resolve();
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 5000 } // ⏱️ Force fresh and accurate location
    );
  });
}
window.getLiveLocation = getLiveLocation;

window.sendMessage = async function (event, isRegenerate = false) {
  const inputField = document.getElementById("input");
  const sendButton = document.getElementById("send-btn");
  const chatbox = document.getElementById("chatbox");

  let message = inputField.value;
  let systemRaw = "";
  let imagePayloadB64 = "";
  let userElem = null;
  let targetUserMsgId = "";

  if (!isRegenerate) {
    // Prevent sending if there is a typed message OR an attached document
    if (!message.trim() && !pendingDocument && !pendingImage) return;

    // --- DYNAMICALLY RESOLVE NUMBERED SHORTCUTS ---
    const trimmedMsg = message.trim();
    if (/^[1-9]$/.test(trimmedMsg) && chatHistory.length > 0) {
      for (let i = chatHistory.length - 1; i >= 0; i--) {
        if (chatHistory[i].role === 'assistant') {
          const lastBotMsg = chatHistory[i].content;
          let followUpRegex = /<followup>([\s\S]*?)<\/followup>/i;
          let match = lastBotMsg.match(followUpRegex);
          if (!match) {
            followUpRegex = /(?:[#\s*-]*)*(?:\*\*|__)?[Ff]ollow-up\s+(?:[Qq]uestions?|[Oo]ptions?):?(?:\*\*|__)?\s*([\s\S]+)$/i;
            match = lastBotMsg.match(followUpRegex);
          }
          if (match) {
            const listBlock = match[1];
            const items = listBlock.split('\n').map(item => {
              return item.replace(/^[ \t]*(?:-\s*|\*\s*|\d+\.\s*)/, '').replace(/^[\[\]*"'`_-]+|[\[\]*"'`_-]+$/g, '').trim();
            }).filter(q => q.length > 0);
            const index = parseInt(trimmedMsg, 10) - 1;
            if (index >= 0 && index < items.length) {
              message = items[index];
            }
          }
          break;
        }
      }
    }

    const finalMessage = message.trim() || (pendingImage ? "Can you describe this image?" : "I have uploaded a document. Please review it.");
    targetUserMsgId = `user-msg-${Date.now()}`; // Unique ID

    // Clear input immediately so text doesn't stick around!
    inputField.value = "";
    inputField.style.height = "auto"; // Reset height back to 1 row
    if (typeof dictationBaseText !== 'undefined') {
      dictationBaseText = "";
    }

    // If the user manually clicks "Send" or hits Enter, reset autoRead so the AI doesn't talk unless asked
    if (typeof event !== 'undefined' && event && (event.type === 'click' || event.type === 'keydown')) {
      autoReadResponse = false;
    }

    let visualMessage = finalMessage;

    // If there's a pending document, add it to history FIRST, and update the visual message
    if (pendingDocument) {
      const sysContent = `The user has uploaded a document named '${pendingDocument.filename}'. Use this to answer their upcoming questions: \n\n--- DOCUMENT CONTENT ---\n${pendingDocument.text || "Document safely processed and stored in the vector database."}\n--- END DOCUMENT ---`;
      systemRaw = encodeURIComponent(sysContent).replace(/'/g, "%27");

      if (pendingDocument.b64) {
        imagePayloadB64 = pendingDocument.b64;
      }

      visualMessage = `<div style="margin-bottom: 8px; padding: 6px 10px; background: rgba(0,0,0,0.2); border-radius: 8px; font-size: 0.85rem; color: #10a37f; display: inline-block;">📎 Attached: <b>${pendingDocument.filename}</b></div><br>` + finalMessage;

      pendingDocument = null;
      const badge = document.getElementById("attach-badge");
      if (badge) badge.remove();
    }

    // If there is an image, append it visually to the UI bubble
    if (pendingImage) {
      imagePayloadB64 = pendingImage.url;
      visualMessage = `<div style="margin-bottom: 12px;"><img src="${pendingImage.url}" style="max-width: 300px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);"></div>` + finalMessage;
      pendingImage = null;
      const badge = document.getElementById("attach-badge");
      if (badge) badge.remove();
    }

    if (visualMessage) {
      const encodedMessage = encodeURIComponent(finalMessage).replace(/'/g, "%27");

      const isCollapsible = visualMessage.length > 5000;
      const collapseClass = isCollapsible ? " collapsible-content collapsed" : "";
      const hasExpandClass = isCollapsible ? " has-expand-btn" : "";
      const expandBtnHtml = isCollapsible ? `
          <button class="expand-text-btn" onclick="toggleExpandMessage(this)">
            <span class="btn-text">Show more</span>
            <svg class="chevron-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </button>
      ` : "";

      // 🚀 Clean User Injection (Margin handles separation smoothly without breaking offset calculations)
      getDropTarget().insertAdjacentHTML("beforeend", `
          <div class="message user" id="${targetUserMsgId}" style="margin-top: 32px; scroll-margin-top: 24px;" data-role="user" data-raw="${encodedMessage}" ${systemRaw ? `data-system="${systemRaw}"` : ""}>
          <div class="user-wrapper">
              <div class="message-content${hasExpandClass}">
              ${expandBtnHtml}
              <div class="message-header">
              <div class="sender-name">${userName || "You"}</div>
              </div>
              <div class="text-body${collapseClass}">${visualMessage}</div>
              </div>
              <div class="message-actions">
              <button class="action-btn" title="Edit" onclick="editMessage('${targetUserMsgId}')">${editSvg}</button>
              <button class="action-btn" title="Copy" onclick="copyMessageText(this)">${copySvg}</button>
              </div>
          </div>
          </div>
      `);

      const dropTarget = getDropTarget();
      if (dropTarget.classList.contains('branch-content')) {
        updateBranchControls(dropTarget.parentElement);
      }

      rebuildChatHistory(); // 🧠 Build history accurately from the visible DOM!
      updateEmptyChatState(); // Shift input box to the bottom instantly!

      saveCurrentSession(); // Save after user input
    }
  } else {
    // If regenerating, track the last user prompt message container
    const userMessages = document.querySelectorAll('.message.user');
    if (userMessages.length > 0) {
      userElem = userMessages[userMessages.length - 1];
    }
  }

  const lastUserMessage = chatHistory.length > 0 ? chatHistory[chatHistory.length - 1].content : "";
  const lowerMsg = lastUserMessage.toLowerCase();
  const isImageRequest = lowerMsg.startsWith("/image") ||
    (lowerMsg.match(/^(generate|create|draw|make)/) && lowerMsg.match(/(image|picture|pic|photo)/));

  // 🛑 Initialize the AbortController
  abortController = new AbortController();
  toggleSendButtonState();

  // Change button to a stop state and make it clickable
  if (isImageRequest) {
    sendButton.innerHTML = "⏹️ Stop";
  } else {
    sendButton.innerHTML = "⏹️";
  }
  sendButton.disabled = false;
  sendButton.onclick = stopGenerating; // Temporarily swap function to STOP

  // 🌍 Check location right before sending just in case it was missed on load
  if (!userLocation) {
    await getLiveLocation();
  }

  let rawMarkdown = "";
  const botMsgId = "bot-msg-" + Date.now();

  // 💭 ADD ADVANCED THINKING BUBBLE IMMEDIATELY
  const isVisionActive = !!imagePayloadB64;
  const thinkingHtml = isVisionActive ? `
    <div class="advanced-thinking thinking-placeholder vision-mode">
      <div class="thinking-dots">
        <span style="background-color: #00d2ff;"></span>
        <span style="background-color: #00d2ff;"></span>
        <span style="background-color: #00d2ff;"></span>
      </div>
      <span class="thinking-status-text" style="color: #00d2ff;">Scanning Vision...</span>
    </div>
  ` : `
    <div class="advanced-thinking thinking-placeholder">
      <div class="thinking-dots">
        <span></span><span></span><span></span>
      </div>
      <span class="thinking-status-text">Thinking...</span>
    </div>
  `;

  // Reset min-height on previous bot messages so only the active prompt maintains height
  document.querySelectorAll('.message.bot').forEach(el => { el.style.minHeight = '0px'; });

  getDropTarget().insertAdjacentHTML("beforeend", `
    <div class="message bot" id="bot-container-${botMsgId}" data-role="assistant" data-raw="" style="min-height: calc(100vh - 200px);">
      <div class="message-content">
        <div class="message-header">
          <div class="bot-avatar">${botLogoSvg}</div>
          <div class="sender-name">${botName || "AI Assistant"}</div>
        </div>
        <div class="text-body" id="${botMsgId}">
          ${thinkingHtml}
        </div>
        <div class="message-actions" id="actions-${botMsgId}" style="display: none;">
          <button class="action-btn" title="Translate" id="translate-btn-${botMsgId}" onclick="translateMessage('${botMsgId}', this)">${translateSvg}</button>
          <button class="action-btn" title="Read Aloud" id="speak-btn-${botMsgId}" onclick="toggleSpeak('${botMsgId}', this)">${speakerSvg}</button>
          <button class="action-btn" title="Copy">${copySvg}</button>
          <button class="action-btn" title="Regenerate" onclick="regenerateMessage('${botMsgId}')">${reloadSvg}</button>
        </div>
      </div>
    </div>
  `);

  const dropTargetBot = getDropTarget();
  if (dropTargetBot.classList.contains('branch-content')) {
    updateBranchControls(dropTargetBot.parentElement);
  }

  // 🎯 ULTRA-SMOOTH SCROLL ANCHOR: Uses requestAnimationFrame + smooth scrollIntoView
  if (targetUserMsgId) {
    userElem = document.getElementById(targetUserMsgId);
  }

  let lockedScrollTop = 0;

  if (userElem && chatbox) {
    isUserScrolledUp = false;
    window.isProgrammaticScrolling = true;

    requestAnimationFrame(() => {
      // Clean smooth scroll anchor that locks prompt neatly at top
      userElem.scrollIntoView({ behavior: 'smooth', block: 'start' });
      lockedScrollTop = chatbox.scrollTop;
      setTimeout(() => { window.isProgrammaticScrolling = false; }, 500);
    });
  }

  let textBodyNode = document.getElementById(botMsgId);
  const actionsDiv = document.getElementById(`actions-${botMsgId}`);
  let copyBtn = actionsDiv.querySelector('button[title="Copy"]');

  // Call backend
  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      // Include the image_b64 payload for Vision Analysis!
      body: JSON.stringify({ messages: chatHistory, session_id: currentSessionId, user_location: userLocation, image_b64: imagePayloadB64, is_temporary: isTemporaryChat }),
      signal: abortController.signal // 🛑 Attach the kill switch signal here
    });
    if (response.status === 401) {
      if (typeof window.handleUnauthorizedToken === 'function') {
        window.handleUnauthorizedToken();
      } else {
        window.location.href = '/login.html';
      }
      return;
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // 🚀 SSE STREAMING READER
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let targetMarkdown = "";
    let typingAnimationId = null;

    // 🚀 PRODUCER-CONSUMER TYPING SCHEDULER:
    // Decouples network packet arrival from UI rendering. Even if SSE delivers
    // bursts of data, this animation loop smoothly feeds chars to the renderer at ~60 FPS.
    const runTypingLoop = () => {
      if (rawMarkdown.length < targetMarkdown.length) {
        const backlog = targetMarkdown.length - rawMarkdown.length;
        // Dynamically scale typing speed based on queue depth (4 to 25 chars per frame)
        const step = Math.max(1, Math.min(backlog, Math.ceil(backlog / 3)));
        rawMarkdown += targetMarkdown.slice(rawMarkdown.length, rawMarkdown.length + step);

        const textOnly = rawMarkdown.replace(/<div class='hidden-sources'[\s\S]*?<\/div>/gi, '').trim();
        if (textOnly !== "") {
          hasVisibleContent = true;
        }

        if (hasVisibleContent) {
          const now = Date.now();

          // 🛡️ DYNAMIC HTML BALANCER: Prevents marked.js from breaking classes or jumping layout!
          let renderText = rawMarkdown;
          const openSpans = (renderText.match(/<span/g) || []).length;
          const closeSpans = (renderText.match(/<\/span>/g) || []).length;
          if (openSpans > closeSpans) {
            renderText += "</span>".repeat(openSpans - closeSpans);
          }
          const openDivs = (renderText.match(/<div/g) || []).length;
          const closeDivs = (renderText.match(/<\/div>/g) || []).length;
          if (openDivs > closeDivs) {
            renderText += "</div>".repeat(openDivs - closeDivs);
          }

          let isFollowupStreaming = renderText.includes("<followup>");
          let placeholderHtml = "";
          if (isFollowupStreaming) {
            renderText = renderText.replace(/<followup>[\s\S]*/i, "");
            placeholderHtml = `
                <div class="suggestions-loading-placeholder">
                  <div class="pill-skeleton"></div>
                  <div class="pill-skeleton"></div>
                  <div class="pill-skeleton"></div>
                </div>
              `;
          }

          // 🧠 STABLE STREAMING SCROLL: Prevents container jitter by locking scroll until response exceeds bottom threshold
          const handleSmartStreamingScroll = () => {
            if (!isUserScrolledUp && textBodyNode && chatbox) {
              const botRect = textBodyNode.getBoundingClientRect();
              const cRect = chatbox.getBoundingClientRect();
              if (botRect.bottom > cRect.bottom - 20) {
                chatbox.scrollTop += (botRect.bottom - cRect.bottom + 20);
              }
            }
          };

          if (now - lastRenderTime > 60) {
            textBodyNode.innerHTML = marked.parse(wrapRawMermaidBlocks(renderText)) + placeholderHtml;
            applyCodeBlockFormatting(textBodyNode);
            handleSmartStreamingScroll();
            lastRenderTime = now;
          }
        }
      }

      if (!done || rawMarkdown.length < targetMarkdown.length) {
        typingAnimationId = requestAnimationFrame(runTypingLoop);
      }
    };

    // Kick off consumer typing animation loop
    typingAnimationId = requestAnimationFrame(runTypingLoop);

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        // Safely extract payloads separated by double-newlines
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const message = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          if (message.startsWith("data: ")) {
            const dataStr = message.slice(6);
            try {
              const dataObj = JSON.parse(dataStr);
              if (dataObj.error) {
                const placeholder = textBodyNode.querySelector(".thinking-placeholder, .advanced-thinking");
                if (placeholder) placeholder.remove();
                targetMarkdown += `\n\n**Error:** ${dataObj.error}`;
                hasVisibleContent = true;
              } else if (dataObj.status) {
                const thinkingText = textBodyNode.querySelector(".thinking-status-text");
                if (thinkingText) {
                  thinkingText.innerText = dataObj.status;
                }
              } else if (dataObj.chunk) {
                targetMarkdown += dataObj.chunk;
              }
            } catch (e) {
              console.error("Error parsing SSE JSON", e, dataStr);
            }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }
    }

    // Flush any remaining characters in the target queue immediately upon stream end
    if (typingAnimationId) cancelAnimationFrame(typingAnimationId);
    rawMarkdown = targetMarkdown;

    // 🛑 Clear any pending render timeout so it doesn't overwrite our final clickable Pills!
    if (renderTimeout) clearTimeout(renderTimeout);

    // Done Streaming: Parse Follow-up Questions into Suggestion Pills
    let displayMarkdown = rawMarkdown;
    const finalOpenSpans = (displayMarkdown.match(/<span/g) || []).length;
    const finalCloseSpans = (displayMarkdown.match(/<\/span>/g) || []).length;
    if (finalOpenSpans > finalCloseSpans) {
      displayMarkdown += "</span>".repeat(finalOpenSpans - finalCloseSpans);
    }
    const finalOpenDivs = (displayMarkdown.match(/<div/g) || []).length;
    const finalCloseDivs = (displayMarkdown.match(/<\/div>/g) || []).length;
    if (finalOpenDivs > finalCloseDivs) {
      displayMarkdown += "</div>".repeat(finalOpenDivs - finalCloseDivs);
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

    textBodyNode.innerHTML = marked.parse(wrapRawMermaidBlocks(displayMarkdown.trim())) + (suggestionsHtml ? `<div class="suggestions-container" style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px;">${suggestionsHtml}</div>` : "");

    // ✅ STABLE SPACER LOCK: Holds smooth height for casual short responses
    const activeBotContainer = document.getElementById(`bot-container-${botMsgId}`);
    if (activeBotContainer && userElem && chatbox) {
      const minSpacer = Math.max(0, chatbox.clientHeight - userElem.offsetHeight - 50);
      activeBotContainer.style.minHeight = `${minSpacer}px`;
    }

    // Done Streaming: Apply code block styling and update states
    applyCodeBlockFormatting(textBodyNode.closest(".message"), true);

    // Extract sources directly from rawMarkdown and attach to actions panel
    extractAndAttachSources(textBodyNode, rawMarkdown, actionsDiv);

    const encodedReply = encodeURIComponent(rawMarkdown).replace(/'/g, "%27");
    const encodedClean = encodeURIComponent(displayMarkdown.trim()).replace(/'/g, "%27");
    const botContainer = document.getElementById(`bot-container-${botMsgId}`);
    botContainer.setAttribute("data-raw", encodedReply);
    botContainer.setAttribute("data-copy-text", encodedClean);
    rebuildChatHistory();

    // Enable the copy button now that the message is complete
    if (actionsDiv) {
      actionsDiv.querySelector('button[title="Copy"]').setAttribute("onclick", "copyMessageText(this)");
      actionsDiv.style.display = "flex";
    }

  } catch (error) {
    console.error("Fetch error:", error);

    if (error.name === 'AbortError') {
      // 🛑 Handle user stopping the stream gracefully
      if (textBodyNode) {
        rawMarkdown += "\n\n*(Stopped by user)*";

        let displayMarkdown = rawMarkdown;
        const abortOpenSpans = (displayMarkdown.match(/<span/g) || []).length;
        const abortCloseSpans = (displayMarkdown.match(/<\/span>/g) || []).length;
        if (abortOpenSpans > abortCloseSpans) {
          displayMarkdown += "</span>".repeat(abortOpenSpans - abortCloseSpans);
        }
        const abortOpenDivs = (displayMarkdown.match(/<div/g) || []).length;
        const abortCloseDivs = (displayMarkdown.match(/<\/div>/g) || []).length;
        if (abortOpenDivs > abortCloseDivs) {
          displayMarkdown += "</div>".repeat(abortOpenDivs - abortCloseDivs);
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

        textBodyNode.innerHTML = marked.parse(wrapRawMermaidBlocks(displayMarkdown.trim())) + (suggestionsHtml ? `<div class="suggestions-container" style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px;">${suggestionsHtml}</div>` : "");

        applyCodeBlockFormatting(textBodyNode.closest(".message"), true);

        const actionsDiv = document.getElementById(`actions-${botMsgId}`);
        extractAndAttachSources(textBodyNode, rawMarkdown, actionsDiv);

        const encodedReply = encodeURIComponent(rawMarkdown).replace(/'/g, "%27");
        const encodedClean = encodeURIComponent(displayMarkdown.trim()).replace(/'/g, "%27");
        const botContainer = document.getElementById(`bot-container-${botMsgId}`);
        botContainer.setAttribute("data-raw", encodedReply);
        botContainer.setAttribute("data-copy-text", encodedClean);
        rebuildChatHistory();

        if (actionsDiv) {
          actionsDiv.querySelector('button[title="Copy"]').setAttribute("onclick", "copyMessageText(this)");
          actionsDiv.style.display = "flex";
        }
      }
    } else {
      if (textBodyNode) {
        // 🛡️ ANTI-WIPEOUT: If the AI already wrote a partial response, don't destroy it! Just append the error.
        if (rawMarkdown.trim() !== "") {
          let errorMarkdown = rawMarkdown;
          const errOpenSpans = (errorMarkdown.match(/<span/g) || []).length;
          const errCloseSpans = (errorMarkdown.match(/<\/span>/g) || []).length;
          if (errOpenSpans > errCloseSpans) {
            errorMarkdown += "</span>".repeat(errOpenSpans - errCloseSpans);
          }
          const errOpenDivs = (errorMarkdown.match(/<div/g) || []).length;
          const errCloseDivs = (errorMarkdown.match(/<\/div>/g) || []).length;
          if (errOpenDivs > errCloseDivs) {
            errorMarkdown += "</div>".repeat(errOpenDivs - errCloseDivs);
          }
          textBodyNode.innerHTML = marked.parse(wrapRawMermaidBlocks(errorMarkdown)) + `<div style="color: #ff6b6b; margin-top: 16px; padding: 10px; background: rgba(255,107,107,0.1); border-radius: 8px; border: 1px solid rgba(255,107,107,0.3);"><b>⚠️ Stream Interrupted</b><br>The network connection dropped, but here is the partial response.</div>`;
          applyCodeBlockFormatting(textBodyNode.closest(".message"), true);

          const actionsDiv = document.getElementById(`actions-${botMsgId}`);
          extractAndAttachSources(textBodyNode, rawMarkdown, actionsDiv);

          const encodedReply = encodeURIComponent(rawMarkdown).replace(/'/g, "%27");
          const encodedClean = encodeURIComponent(errorMarkdown.trim()).replace(/'/g, "%27");
          const botContainer = document.getElementById(`bot-container-${botMsgId}`);
          botContainer.setAttribute("data-raw", encodedReply);
          botContainer.setAttribute("data-copy-text", encodedClean);
          rebuildChatHistory();

          if (actionsDiv) {
            actionsDiv.querySelector('button[title="Copy"]').setAttribute("onclick", "copyMessageText(this)");
            actionsDiv.style.display = "flex";
          }
        } else {
          textBodyNode.innerHTML = `<div style="color: #ff6b6b; padding: 10px; background: rgba(255,107,107,0.1); border-radius: 8px; border: 1px solid rgba(255,107,107,0.3);"><b>⚠️ Error</b><br>${error.message || "Connection failed. Make sure your FastAPI backend is running!"}</div>`;
        }
      }
    }
  } finally {
    // Restore UI buttons regardless of success, error, or manual stop
    sendButton.innerHTML = "➤";
    sendButton.onclick = sendMessage; // Re-bind the send function
    sendButton.disabled = false;

    saveCurrentSession(); // Save error state
    abortController = null;
    toggleSendButtonState();
  }
};