// --- KODA Sources Panel UI Module ---

window.extractAndAttachSources = function (textBodyNode, rawMarkdown, actionsDiv) {
  if (!actionsDiv) return;

  let detectedSources = [];

  // 1. Detect all HTTP/HTTPS links
  const urlRegex = /https?:\/\/[^\s\n\)\"\'\<\>]+/g;
  let urlMatches = rawMarkdown.match(urlRegex) || [];
  urlMatches.forEach(url => {
    if (!detectedSources.includes(url)) {
      detectedSources.push(url);
    }
  });

  // 2. Detect if resume or document is mentioned (to add Uploaded Document source)
  const lowerText = rawMarkdown.toLowerCase();
  if (lowerText.includes("resume") || lowerText.includes("document.pdf") || lowerText.includes("uploaded file") || lowerText.includes("resume.pdf")) {
    if (!detectedSources.includes("Uploaded Document")) {
      detectedSources.unshift("Uploaded Document");
    }
  }

  // 3. Fallback support for hidden-sources in the text if present
  const hiddenSources = textBodyNode.querySelector('.hidden-sources');
  if (hiddenSources) {
    const sourcesB64 = hiddenSources.getAttribute('data-sources');
    if (sourcesB64) {
      try {
        const decodedStr = decodeURIComponent(escape(atob(sourcesB64)));
        const sources = JSON.parse(decodedStr);
        sources.forEach(src => {
          if (!detectedSources.includes(src)) {
            detectedSources.push(src);
          }
        });
      } catch (err) { }
    }
  }

  // Attach View Sources button if sources detected
  if (detectedSources.length > 0 && !actionsDiv.querySelector('.sources-action-btn')) {
    const sourcesB64 = btoa(unescape(encodeURIComponent(JSON.stringify(detectedSources))));
    const sourcesActionBtn = document.createElement("button");
    sourcesActionBtn.className = "action-btn sources-action-btn";
    sourcesActionBtn.title = "View Sources";
    sourcesActionBtn.setAttribute("data-sources", sourcesB64);
    sourcesActionBtn.innerHTML = typeof sourcesSvg !== 'undefined' ? sourcesSvg : '📚';
    actionsDiv.appendChild(sourcesActionBtn);
  }
};

window.openSourcesPanel = function (sources) {
  let panel = document.querySelector('.sources-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.className = 'sources-panel';
    panel.innerHTML = `
      <div class="sources-header">
        <h3><span class="source-icon">📚</span> Sources</h3>
        <button class="close-sources-btn" onclick="document.querySelector('.sources-panel').classList.remove('open'); document.body.classList.remove('sources-open');">✖</button>
      </div>
      <div class="sources-list" id="sources-list"></div>
    `;
    document.body.appendChild(panel);
  }

  const list = panel.querySelector('#sources-list');
  list.innerHTML = '';

  if (sources && sources.length > 0) {
    sources.forEach((src, idx) => {
      let title = src; let url = src;
      let icon = "🌐";
      if (src === 'Uploaded Document') { url = '#'; icon = "📄"; }
      else { try { title = new URL(src).hostname.replace('www.', ''); } catch (e) { } }
      list.innerHTML += `
          <a href="${url}" target="_blank" class="source-item">
            <div class="source-icon">${icon}</div>
            <div class="source-info">
              <div class="source-domain">Source ${idx + 1}</div>
              <div class="source-url">${title}</div>
            </div>
          </a>`;
    });
  } else {
    list.innerHTML = '<div style="opacity: 0.7; font-size: 0.9rem; padding: 10px;">No sources available.</div>';
  }

  setTimeout(() => {
    panel.classList.add('open');
    document.body.classList.add('sources-open');
  }, 10);
};

// Event delegation for the View Sources button (bypasses marked.js stripping onclick)
document.addEventListener('click', function (e) {
  const sourcesBtn = e.target.closest('.sources-btn') || e.target.closest('.sources-action-btn');
  if (sourcesBtn) {
    const sourcesData = sourcesBtn.getAttribute('data-sources');
    if (sourcesData) {
      try {
        // Safely decode the Base64 payload from Python
        const decodedStr = decodeURIComponent(escape(atob(sourcesData)));
        const sources = JSON.parse(decodedStr);
        if (typeof window.openSourcesPanel === 'function') {
          window.openSourcesPanel(sources);
        }
      } catch (err) {
        console.error('Failed to parse sources', err);
      }
    }
  }
});
