// --- KODA Markdown & Mermaid Diagram Compiler UI Module ---

window.renderedMermaidCache = {};
window.renderingMermaid = new Set();

window.wrapRawMermaidBlocks = function (text) {
  if (!text) return text;
  // Fast pass: If the response doesn't contain any mermaid keyword, skip line-by-line parsing entirely!
  if (!/graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|gitGraph|journey|C4Context|mindmap|timeline/i.test(text)) {
    return text;
  }
  const mermaidKeywords = /^(graph\s+\w+|flowchart\s+\w+|sequenceDiagram|classDiagram|stateDiagram-v2|stateDiagram|erDiagram|gantt|pie|gitGraph|journey|C4Context|mindmap|timeline)/im;

  const lines = text.split('\n');
  let insideCodeBlock = false;
  let insideRawMermaid = false;
  let newLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      insideCodeBlock = !insideCodeBlock;
      newLines.push(line);
      continue;
    }

    if (!insideCodeBlock) {
      if (!insideRawMermaid && mermaidKeywords.test(trimmed)) {
        insideRawMermaid = true;
        newLines.push("```mermaid");
        newLines.push(line);
        continue;
      }

      if (insideRawMermaid) {
        const isEnd = trimmed !== "" &&
          (trimmed.startsWith("#") ||
            trimmed.startsWith("**") ||
            trimmed.endsWith(".") ||
            trimmed.endsWith("?") ||
            trimmed.endsWith("!"));

        if (isEnd) {
          insideRawMermaid = false;
          newLines.push("```");
          newLines.push(line);
        } else {
          newLines.push(line);
        }
        continue;
      }
    }

    newLines.push(line);
  }

  if (insideRawMermaid) {
    newLines.push("```");
  }

  return newLines.join('\n');
};

window.convertMermaidToTextFlow = function (mermaidCode) {
  if (!mermaidCode) return "";
  const lines = mermaidCode.split('\n');
  const nodes = {};
  const connections = [];
  const incomingCount = {};
  const outgoing = {};

  const nodeRegex = /(\w+)\s*(?:\[\"?|(?:\(\"?)|(?:\{\"?))\s*([^\]\)\}\"]+)\s*(?:\"?\]|(?:\"?\))|(?:\"?\}))/g;

  for (let line of lines) {
    line = line.trim();
    if (line.startsWith("%%") || line.startsWith("classDef") || line.startsWith("class ") || line.startsWith("linkStyle")) {
      continue;
    }
    let match;
    while ((match = nodeRegex.exec(line)) !== null) {
      nodes[match[1]] = match[2].trim();
    }
  }

  for (let line of lines) {
    line = line.trim();
    if (line.startsWith("%%") || line.startsWith("classDef") || line.startsWith("class ") || line.startsWith("linkStyle")) {
      continue;
    }
    let cleanLine = line.replace(/\[[^\]]+\]|\([^)]+\)|\{[^}]+\}/g, "");
    const connMatch = cleanLine.match(/(\w+)\s*(-->|---|-.->|-\.-\.>)\s*(?:\|([^|]+)\|)?\s*(\w+)/);
    if (connMatch) {
      const source = connMatch[1];
      const arrow = connMatch[2];
      const connLabel = connMatch[3] ? connMatch[3].trim() : "";
      const target = connMatch[4];

      connections.push({ source, arrow, connLabel, target });

      if (!incomingCount[target]) incomingCount[target] = 0;
      incomingCount[target]++;

      if (!outgoing[source]) outgoing[source] = [];
      outgoing[source].push({ target, connLabel, arrow });
    }
  }

  if (Object.keys(nodes).length === 0 && connections.length === 0) {
    return mermaidCode;
  }

  const roots = [];
  for (const id of Object.keys(nodes)) {
    if (!incomingCount[id]) {
      roots.push(id);
    }
  }
  if (roots.length === 0 && Object.keys(nodes).length > 0) {
    roots.push(Object.keys(nodes)[0]);
  }

  let output = "";
  const visited = new Set();

  function drawNodeBox(label) {
    const padded = " " + label + " ";
    const len = padded.length;
    const top = "┌" + "─".repeat(len) + "┐";
    const mid = "│" + padded + "│";
    const bot = "└" + "─".repeat(len) + "┘";
    return { top, mid, bot, len };
  }

  function renderTree(nodeId, indent = "") {
    if (visited.has(nodeId)) {
      const label = nodes[nodeId] || nodeId;
      return `${indent}  └── [See Component: ${label}]\n`;
    }
    visited.add(nodeId);

    const label = nodes[nodeId] || nodeId;
    const box = drawNodeBox(label);
    let block = "";

    block += `${indent}${box.top}\n`;
    block += `${indent}${box.mid}\n`;
    block += `${indent}${box.bot}\n`;

    const children = outgoing[nodeId] || [];
    if (children.length === 1) {
      const child = children[0];
      const arrowLine = child.arrow.includes(".") ? "╎" : "│";
      const arrowHead = "▼";
      const lbl = child.connLabel ? `  (${child.connLabel})` : "";

      const halfWidth = Math.floor(box.len / 2);
      const space = " ".repeat(halfWidth);

      block += `${indent}${space}${arrowLine}${lbl}\n`;
      block += `${indent}${space}${arrowLine}\n`;
      block += `${indent}${space}${arrowHead}\n`;

      block += renderTree(child.target, indent);
    } else if (children.length > 1) {
      const halfWidth = Math.floor(box.len / 2);
      const space = " ".repeat(halfWidth);
      const arrowLine = "│";
      block += `${indent}${space}${arrowLine}\n`;

      children.forEach((child, idx) => {
        const isLast = idx === children.length - 1;
        const branchSymbol = isLast ? "└──" : "├──";
        const connText = child.connLabel ? ` (${child.connLabel}) ` : "";
        const childLabel = nodes[child.target] || child.target;
        const arrowSymbol = child.arrow.includes(".") ? " ╌╌> " : " ──> ";

        block += `${indent}${space}${branchSymbol}${connText}${arrowSymbol}[${childLabel}]\n`;
        block += renderTree(child.target, indent + space + (isLast ? "   " : "│  "));
      });
    }
    return block;
  }

  for (const root of roots) {
    output += renderTree(root);
    output += "\n";
  }

  return output.trim();
};

window.isMermaidBlockClosed = function (codeText, messageNode) {
  const msgEl = messageNode.closest(".message");
  if (!msgEl) return true;
  const rawEncoded = msgEl.getAttribute("data-raw");
  if (!rawEncoded) return true;
  const rawText = decodeURIComponent(rawEncoded);

  const backtickCount = (rawText.match(/```/g) || []).length;
  if (backtickCount > 0 && backtickCount % 2 === 0) {
    return true;
  }

  const normalizedRaw = rawText.trim();
  const normalizedCode = codeText.trim();

  if (normalizedRaw.endsWith(normalizedCode) || normalizedRaw.endsWith(normalizedCode + "\n")) {
    return false;
  }

  const codeIdx = rawText.indexOf(codeText);
  if (codeIdx !== -1) {
    const afterText = rawText.substring(codeIdx + codeText.length).trim();
    if (afterText.length > 0) {
      return true;
    }
  }

  return false;
};

// Extracted formatting logic so it runs cleanly AFTER typing completes
window.applyCodeBlockFormatting = function (messageNode, isDone = false) {
  if (!isDone) {
    return; // 🚀 fluid streaming: Skip expensive highlights/DOM wrapping until stream is done
  }
  const preTags = messageNode.querySelectorAll("pre");

  preTags.forEach((pre) => {
    if (pre.parentNode && pre.parentNode.classList.contains("code-wrapper")) return;
    if (pre.parentNode && pre.parentNode.classList.contains("mermaid-diagram-container")) return;

    const codeElement = pre.querySelector("code");
    let language = "code";
    if (codeElement && codeElement.className) {
      const match = codeElement.className.match(/language-(\w+)/);
      if (match) {
        language = match[1].toLowerCase();
      }
    }

    let codeText = codeElement ? codeElement.textContent : pre.textContent;

    // --- RENDER MERMAID DIAGRAMS DIRECTLY IN CHAT ---
    if (language === "mermaid") {
      const codeHash = codeText.trim();
      const isClosed = isMermaidBlockClosed(codeText, messageNode);

      // If the block is already rendered and stored in our cache
      if (window.renderedMermaidCache[codeHash]) {
        const cachedContainer = document.createElement("div");
        cachedContainer.innerHTML = window.renderedMermaidCache[codeHash];
        // Replace pre with the fully rendered cached container
        pre.parentNode.replaceChild(cachedContainer.firstElementChild, pre);
        return;
      }

      // If the block is NOT closed yet (still streaming the diagram lines)
      if (!isClosed) {
        pre.style.display = "none";
        const loadingPlaceholder = document.createElement("div");
        loadingPlaceholder.className = "mermaid-loading-container";
        loadingPlaceholder.innerHTML = `
          <div class="pill-skeleton" style="width: 100%; height: 120px; border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 0.95rem; color: #caa64b; gap: 12px; border: 1px dashed rgba(202, 166, 75, 0.3); background: rgba(202, 166, 75, 0.02); margin: 14px 0;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="spinner-icon"></span>
              <span style="font-weight: 500; letter-spacing: 0.5px;">Generating visual flowchart...</span>
            </div>
            <span style="font-size: 0.75rem; color: #888;">(Hiding code markup during stream)</span>
          </div>
        `;
        pre.parentNode.insertBefore(loadingPlaceholder, pre);
        return;
      }

      // If the block is closed and not in cache, render it immediately using window.mermaid.run
      const uniqueId = "mermaid-diagram-" + Date.now() + "-" + Math.floor(Math.random() * 10000);
      const diagramDiv = document.createElement("div");
      diagramDiv.className = "mermaid-diagram-container";
      diagramDiv.style.background = "#18181b";
      diagramDiv.style.border = "1px solid #2f2f2f";
      diagramDiv.style.borderRadius = "12px";
      diagramDiv.style.padding = "24px 20px 20px 20px";
      diagramDiv.style.margin = "14px 0";
      diagramDiv.style.display = "flex";
      diagramDiv.style.flexDirection = "column";
      diagramDiv.style.alignItems = "center";
      diagramDiv.style.overflowX = "auto";
      diagramDiv.style.position = "relative";
      diagramDiv.style.boxShadow = "0 8px 30px rgba(0,0,0,0.3)";

      // Control overlay
      const overlayHeader = document.createElement("div");
      overlayHeader.style.position = "absolute";
      overlayHeader.style.top = "8px";
      overlayHeader.style.right = "8px";
      overlayHeader.style.display = "flex";
      overlayHeader.style.gap = "8px";
      overlayHeader.style.zIndex = "10";

      // Copy Code as Clean Text Flowchart
      const copyCodeBtn = document.createElement("button");
      copyCodeBtn.className = "copy-btn";
      copyCodeBtn.innerHTML = typeof copySvg !== 'undefined' ? copySvg : '📋';
      copyCodeBtn.title = "Copy Text Flowchart";
      copyCodeBtn.onclick = (e) => {
        e.stopPropagation();
        const textFlow = convertMermaidToTextFlow(codeText);
        navigator.clipboard.writeText(textFlow);
        copyCodeBtn.innerHTML = "✓";
        setTimeout(() => { copyCodeBtn.innerHTML = typeof copySvg !== 'undefined' ? copySvg : '📋'; }, 2000);
      };
      overlayHeader.appendChild(copyCodeBtn);

      // Download SVG Diagram
      const downloadBtn = document.createElement("button");
      downloadBtn.className = "copy-btn";
      downloadBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`;
      downloadBtn.title = "Download SVG Diagram";
      downloadBtn.onclick = (e) => {
        e.stopPropagation();
        const svgContent = diagramDiv.querySelector("svg");
        if (svgContent) {
          try {
            const svgData = new XMLSerializer().serializeToString(svgContent);
            const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
            const svgUrl = URL.createObjectURL(svgBlob);
            const downloadLink = document.createElement("a");
            downloadLink.href = svgUrl;
            downloadLink.download = "mermaid-diagram.svg";
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
            URL.revokeObjectURL(svgUrl);
          } catch (dlErr) {
            console.error("Failed to download SVG diagram", dlErr);
          }
        }
      };
      overlayHeader.appendChild(downloadBtn);

      // Zoom
      const zoomBtn = document.createElement("button");
      zoomBtn.className = "copy-btn";
      zoomBtn.innerHTML = `🔍`;
      zoomBtn.title = "View Fullscreen Diagram";
      zoomBtn.onclick = (e) => {
        e.stopPropagation();
        const svgContent = diagramDiv.querySelector("svg");
        if (svgContent && typeof window.openFullscreenSVG === 'function') {
          window.openFullscreenSVG(svgContent.outerHTML);
        }
      };
      overlayHeader.appendChild(zoomBtn);

      diagramDiv.appendChild(overlayHeader);

      const rawEl = document.createElement("div");
      rawEl.className = "mermaid";
      rawEl.id = uniqueId;
      rawEl.textContent = codeText.trim();
      diagramDiv.appendChild(rawEl);

      pre.parentNode.replaceChild(diagramDiv, pre);

      try {
        window.mermaid.run({ nodes: [rawEl] });
        // The render completed successfully, store in cache!
        window.renderedMermaidCache[codeHash] = diagramDiv.outerHTML;
      } catch (err) {
        console.error("Mermaid run failed", err);
        rawEl.innerHTML = `
          <div style="color: #ff6b6b; padding: 14px; background: rgba(255,107,107,0.05); border-radius: 8px; border: 1px solid rgba(255,107,107,0.2); font-size: 0.9rem;">
            <b>⚠️ Failed to render diagram</b><br>
            Syntax error in Mermaid flowchart code. Copy as text is still available.
          </div>
        `;
      }
      return;
    }

    let isSVG = codeText.trim().toLowerCase().startsWith("<svg");

    const wrapper = document.createElement("div");
    wrapper.className = "code-wrapper";

    // Dynamic top-left label logic
    let displayLang = language;
    if (isSVG && (language === "xml" || language === "html" || language === "code")) {
      displayLang = "svg";
    }

    const header = document.createElement("div");
    header.className = "code-header";

    const langSpan = document.createElement("span");
    langSpan.className = "code-lang";
    langSpan.innerText = displayLang;

    const actionsDiv = document.createElement("div");
    actionsDiv.style.display = "flex";
    actionsDiv.style.gap = "8px";

    const downloadIconHtml = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v14"></path><polyline points="5 10 12 17 19 10"></polyline><line x1="3" y1="21" x2="21" y2="21"></line></svg>`;

    let editBtn = null;
    if (isSVG) {
      editBtn = document.createElement("button");
      editBtn.className = "copy-btn";
      editBtn.innerHTML = typeof sidebarEditSvg !== 'undefined' ? sidebarEditSvg : '✏️';
      editBtn.title = "Edit code";
      actionsDiv.appendChild(editBtn);

      // Dynamic Image Download Button (Auto-Canvas Conversion)
      const downloadImgBtn = document.createElement("button");
      downloadImgBtn.className = "copy-btn";

      let isPng = displayLang === 'png';
      let isJpg = displayLang === 'jpg' || displayLang === 'jpeg';
      let formatText = isPng ? 'PNG' : (isJpg ? 'JPG' : 'SVG');

      downloadImgBtn.innerHTML = downloadIconHtml;
      downloadImgBtn.title = `Download ${formatText}`;
      downloadImgBtn.onclick = () => {
        const currentCode = codeElement ? codeElement.textContent : pre.textContent;
        const blob = new Blob([currentCode], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(blob);

        if (formatText === 'SVG') {
          const a = document.createElement("a");
          a.href = url;
          a.download = "koda-image.svg";
          a.click();
          URL.revokeObjectURL(url);
        } else {
          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d");
          const img = new Image();
          img.onload = () => {
            canvas.width = img.width || 800;
            canvas.height = img.height || 800;
            if (isJpg) {
              ctx.fillStyle = "#FFFFFF";
              ctx.fillRect(0, 0, canvas.width, canvas.height);
            }
            ctx.drawImage(img, 0, 0);
            const mimeType = isJpg ? "image/jpeg" : "image/png";
            const dataUrl = canvas.toDataURL(mimeType);
            const a = document.createElement("a");
            a.href = dataUrl;
            a.download = `koda-image.${formatText.toLowerCase()}`;
            a.click();
            URL.revokeObjectURL(url);
          };
          img.src = url;
        }
      };
      actionsDiv.appendChild(downloadImgBtn);
    } else {
      const universalDownloadBtn = document.createElement("button");
      universalDownloadBtn.className = "copy-btn";

      let formatName = language.toUpperCase();
      if (language === 'python') formatName = 'Python';
      else if (language === 'javascript') formatName = 'JS';
      else if (language === 'markdown') formatName = 'Markdown';
      else if (language === 'code' || !language) formatName = 'File';

      universalDownloadBtn.innerHTML = downloadIconHtml;
      universalDownloadBtn.title = `Download ${formatName}`;
      universalDownloadBtn.onclick = () => {
        const currentCode = codeElement ? codeElement.textContent : pre.textContent;

        // ✨ NATIVE PDF GENERATION FROM AI MARKDOWN ✨
        if (language === 'pdf') {
          if (!window.jspdf) {
            alert("PDF library is still loading. Please try again in a moment.");
            return;
          }
          const { jsPDF } = window.jspdf;
          const doc = new jsPDF();
          let y = 20;
          const margin = 15;
          const pageHeight = doc.internal.pageSize.height;
          const pageWidth = doc.internal.pageSize.width;
          const maxLineWidth = pageWidth - margin * 2;

          doc.setFontSize(12);
          doc.setFont("helvetica", "normal");

          let cleanText = currentCode
             .replace(/\*\*(.*?)\*\*/g, '$1') // Bold
             .replace(/\*(.*?)\*/g, '$1')      // Italic
             .replace(/__(.*?)__/g, '$1')      // Underline
             .replace(/#{1,6}\s/g, '') // Remove headers
             .replace(/[\u2018\u2019]/g, "'") // Smart single quotes
             .replace(/[\u201C\u201D]/g, '"') // Smart double quotes
             .replace(/[\u2013\u2014]/g, '-') // Dashes
             .replace(/[^\x00-\x7F]/g, ''); // Strip non-ASCII

          const textLines = doc.splitTextToSize(cleanText, maxLineWidth);
          for (let i = 0; i < textLines.length; i++) {
            if (y > pageHeight - 15) {
              doc.addPage();
              y = 20;
            }
            doc.text(textLines[i], margin, y);
            y += 6;
          }
          doc.save(`koda-document.pdf`);
          return;
        }

        // ✨ NATIVE DOC EXPORT ✨
        if (language === 'doc' || language === 'docx') {
          let htmlContent = `<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'><head><meta charset='utf-8'><title>Document</title></head><body>`;
          const formattedText = typeof marked !== 'undefined' ? marked.parse(currentCode) : `<p>${currentCode}</p>`;
          htmlContent += `<div>${formattedText}</div></body></html>`;
          const blob = new Blob([htmlContent], { type: 'application/msword' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `koda-document.doc`;
          a.click();
          URL.revokeObjectURL(url);
          return;
        }

        let mimeType = language === "csv" ? "text/csv" : "text/plain";
        const blob = new Blob([currentCode], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const extMap = { python: 'py', javascript: 'js', html: 'html', css: 'css', json: 'json', markdown: 'md', bash: 'sh', xml: 'xml', csv: 'csv' };
        const ext = extMap[language] || 'txt';
        a.download = `koda-snippet.${ext}`;
        a.click();
        URL.revokeObjectURL(url);
      };
      actionsDiv.appendChild(universalDownloadBtn);
    }

    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.innerHTML = copySvg;
    copyBtn.title = "Copy code";
    copyBtn.onclick = () => {
      let codeToCopy = codeElement ? codeElement.textContent : pre.textContent;
      codeToCopy = codeToCopy.replace(/\r?\n/g, "\r\n");
      navigator.clipboard.writeText(codeToCopy).then(() => {
        copyBtn.innerHTML = checkSvg;
        setTimeout(() => copyBtn.innerHTML = copySvg, 2000);
      });
    };
    actionsDiv.appendChild(copyBtn);

    header.appendChild(langSpan);
    header.appendChild(actionsDiv);
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);

    if (isSVG) {
      pre.style.display = "none";

      const previewBox = document.createElement("div");
      previewBox.className = "svg-preview-box";
      previewBox.style.background = "#ffffff";
      previewBox.style.padding = "24px";
      previewBox.style.display = "flex";
      previewBox.style.justifyContent = "center";
      previewBox.style.alignItems = "center";
      previewBox.style.position = "relative";
      previewBox.style.borderBottomLeftRadius = "6px";
      previewBox.style.borderBottomRightRadius = "6px";
      previewBox.style.minHeight = "250px";
      previewBox.style.boxShadow = "inset 0 0 0 1px rgba(0,0,0,0.1)";
      previewBox.style.overflow = "hidden";

      // 🔍 FULL-SCREEN EXPAND BUTTON
      const expandBtn = document.createElement("button");
      expandBtn.className = "copy-btn";
      expandBtn.style.position = "absolute";
      expandBtn.style.top = "12px";
      expandBtn.style.right = "12px";
      expandBtn.style.background = "rgba(0,0,0,0.6)";
      expandBtn.style.color = "white";
      expandBtn.style.backdropFilter = "blur(4px)";
      expandBtn.style.padding = "6px";
      expandBtn.style.zIndex = "5";
      expandBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>`;
      expandBtn.title = "Full Screen";

      const parser = new DOMParser();
      const svgContainer = document.createElement("div");
      svgContainer.style.width = "100%";
      svgContainer.style.display = "flex";
      svgContainer.style.justifyContent = "center";
      svgContainer.style.alignItems = "center";

      expandBtn.onclick = () => {
        if (typeof window.openFullscreenSVG === "function") {
          window.openFullscreenSVG(svgContainer.innerHTML);
        }
      };
      previewBox.appendChild(expandBtn);

      const renderSVG = (code) => {
        const svgDoc = parser.parseFromString(code, "image/svg+xml");
        const svgEl = svgDoc.querySelector("svg");
        svgContainer.innerHTML = "";
        if (svgEl && !svgEl.querySelector("parsererror")) {
          svgEl.style.width = "100%";
          svgEl.style.height = "auto";
          svgEl.style.maxHeight = "350px";
          svgEl.style.display = "block";
          svgContainer.appendChild(svgEl);
        } else {
          svgContainer.innerHTML = "<span style='color:#ff4a4a; background:rgba(255,74,74,0.1); padding:4px 8px; border-radius:4px;'>Invalid SVG / Creating...</span>";
        }
      };
      renderSVG(codeText);

      previewBox.appendChild(svgContainer);
      wrapper.appendChild(previewBox);

      const editBox = document.createElement("div");
      editBox.style.display = "none";
      editBox.style.flexDirection = "column";

      const editArea = document.createElement("textarea");
      editArea.className = "edit-textarea";
      editArea.style.border = "none";
      editArea.style.borderRadius = "0";
      editArea.style.borderBottomLeftRadius = "6px";
      editArea.style.borderBottomRightRadius = "6px";
      editArea.style.fontFamily = "monospace";
      editArea.style.fontSize = "0.85rem";
      editArea.style.minHeight = "300px";
      editArea.style.width = "100%";
      editArea.style.resize = "vertical";
      editArea.style.outline = "none";
      editArea.style.boxShadow = "none";
      editArea.value = codeText;

      editBox.appendChild(editArea);

      wrapper.appendChild(editBox);
      wrapper.appendChild(pre);

      let isEditing = false;
      editBtn.onclick = () => {
        if (!isEditing) {
          isEditing = true;
          previewBox.style.display = "none";
          editBox.style.display = "flex";
          editArea.value = codeElement ? codeElement.textContent : pre.textContent;
          editBtn.innerHTML = `✅`;
          editBtn.title = "Save changes";
          editBtn.style.color = "#10a37f";
        } else {
          isEditing = false;
          const newCode = editArea.value;
          if (codeElement) {
            codeElement.textContent = newCode;
            if (typeof hljs !== 'undefined') hljs.highlightElement(codeElement);
          } else {
            pre.textContent = newCode;
          }
          renderSVG(newCode);
          editBox.style.display = "none";
          previewBox.style.display = "flex";
          editBtn.innerHTML = typeof sidebarEditSvg !== 'undefined' ? sidebarEditSvg : '✏️';
          editBtn.title = "Edit code";
          editBtn.style.color = "";
        }
      };
    } else {
      wrapper.appendChild(pre);
      if (codeElement && typeof hljs !== 'undefined') {
        hljs.highlightElement(codeElement);
      }
    }
  });
};

// --- Fullscreen SVG Modal Logic ---
window.openFullscreenSVG = function (svgHtml) {
  let modal = document.getElementById('svg-fullscreen-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'svg-fullscreen-modal';
    modal.style.position = 'fixed';
    modal.style.top = '0';
    modal.style.left = '0';
    modal.style.width = '100vw';
    modal.style.height = '100vh';
    modal.style.backgroundColor = 'rgba(0,0,0,0.85)';
    modal.style.zIndex = '10000';
    modal.style.display = 'flex';
    modal.style.justifyContent = 'center';
    modal.style.alignItems = 'center';
    modal.style.backdropFilter = 'blur(8px)';

    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✖';
    closeBtn.style.position = 'absolute';
    closeBtn.style.top = '24px';
    closeBtn.style.right = '24px';
    closeBtn.style.background = 'rgba(255,255,255,0.15)';
    closeBtn.style.border = 'none';
    closeBtn.style.color = 'white';
    closeBtn.style.fontSize = '20px';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.width = '48px';
    closeBtn.style.height = '48px';
    closeBtn.style.borderRadius = '50%';
    closeBtn.style.transition = 'background 0.2s';
    closeBtn.onmouseover = () => { closeBtn.style.background = 'rgba(255,255,255,0.3)'; };
    closeBtn.onmouseout = () => { closeBtn.style.background = 'rgba(255,255,255,0.15)'; };
    closeBtn.onclick = () => { modal.style.display = 'none'; };
    modal.appendChild(closeBtn);

    const contentDiv = document.createElement('div');
    contentDiv.id = 'svg-fullscreen-content';
    contentDiv.style.width = '85%';
    contentDiv.style.height = '85%';
    contentDiv.style.display = 'flex';
    contentDiv.style.justifyContent = 'center';
    contentDiv.style.alignItems = 'center';
    contentDiv.style.background = '#ffffff';
    contentDiv.style.borderRadius = '16px';
    contentDiv.style.padding = '32px';
    contentDiv.style.boxShadow = '0 10px 40px rgba(0,0,0,0.5)';
    modal.appendChild(contentDiv);

    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });
  }

  const contentDiv = modal.querySelector('#svg-fullscreen-content');
  contentDiv.innerHTML = svgHtml;

  const svgEl = contentDiv.querySelector('svg');
  if (svgEl) {
    svgEl.style.width = '100%';
    svgEl.style.height = '100%';
    svgEl.style.maxHeight = '100%';
  }

  modal.style.display = 'flex';
};
