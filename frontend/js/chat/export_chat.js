// --- KODA Export Chat ---
// Exports the current chat session as TXT, DOC, or high-quality PDF (with SVG/image rendering).

window.exportChat = async function (format) {
  document.getElementById('export-dropdown').classList.remove('show');

  if (!chatHistory || chatHistory.length === 0) {
    alert("No chat history to export.");
    return;
  }

  const session = chatSessions.find(s => s.id === currentSessionId);
  const title = session && session.title !== "New Chat" ? session.title.replace(/[^a-z0-9]/gi, '_').toLowerCase() : "chat_history";
  const filename = `${title}_${new Date().toISOString().split('T')[0]}`;

  // --- TXT Format ---
  if (format === 'txt') {
    let textContent = `Chat History: ${title}\nDate: ${new Date().toLocaleString()}\n\n`;
    chatHistory.forEach(msg => {
      const role = msg.role === 'user' ? (userName || 'User') : (botName || 'AI Assistant');
      textContent += `[${role}]\n${msg.content}\n\n`;
    });
    downloadFile(textContent, `${filename}.txt`, 'text/plain');
  }

  // --- DOC Format ---
  else if (format === 'doc') {
    let htmlContent = `<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'><head><meta charset='utf-8'><title>Chat History</title><style>body { color: #000000; background-color: #ffffff; }</style></head><body>`;
    htmlContent += `<h1>Chat History: ${title}</h1><p>Date: ${new Date().toLocaleString()}</p><hr>`;
    chatHistory.forEach(msg => {
      const role = msg.role === 'user' ? (userName || 'User') : (botName || 'AI Assistant');
      const color = msg.role === 'user' ? '#10a37f' : '#3a7bd5';
      htmlContent += `<h3 style="color: ${color};">${role}</h3>`;
      const formattedText = typeof marked !== 'undefined' ? marked.parse(msg.content) : `<p>${msg.content}</p>`;
      htmlContent += `<div>${formattedText}</div><br>`;
    });
    htmlContent += `</body></html>`;
    downloadFile(htmlContent, `${filename}.doc`, 'application/msword');
  }

  // --- PDF Format ---
  else if (format === 'pdf') {
    if (!window.jspdf) {
      alert("PDF library is still loading. Please try again in a moment.");
      return;
    }

    const exportBtn = document.querySelector('button[onclick="exportChat(\'pdf\')"]');
    const originalBtnText = exportBtn ? exportBtn.innerHTML : "";
    if (exportBtn) exportBtn.innerHTML = "⏳ Exporting...";

    try {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();

      let y = 20;
      const margin = 15;
      const pageHeight = doc.internal.pageSize.height;
      const pageWidth = doc.internal.pageSize.width;
      const maxLineWidth = pageWidth - margin * 2;

      doc.setFontSize(16);
      doc.setFont("helvetica", "bold");
      doc.text(`Chat History: ${title}`, margin, y);
      y += 8;

      doc.setFontSize(10);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(128, 128, 128);
      doc.text(`Date: ${new Date().toLocaleString()}`, margin, y);
      y += 10;

      doc.setDrawColor(200, 200, 200);
      doc.line(margin, y, pageWidth - margin, y);
      y += 10;

      for (const msg of chatHistory) {
        const role = msg.role === 'user' ? (userName || 'User') : (botName || 'AI Assistant');
        const isUser = msg.role === 'user';

        if (y > pageHeight - 20) { doc.addPage(); y = 20; }

        doc.setFontSize(12);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(isUser ? 16 : 58, isUser ? 163 : 123, isUser ? 127 : 213);
        doc.text(role, margin, y);
        y += 6;

        let mediaItems = [];

        // Extract SVGs from code blocks
        const codeRegex = /```(?:[a-z]*\n)?([\s\S]*?)```/gi;
        let match;
        while ((match = codeRegex.exec(msg.content)) !== null) {
          const codeText = match[1].trim();
          if (codeText.toLowerCase().startsWith("<svg")) {
            mediaItems.push({ type: 'svg', data: codeText });
          }
        }

        // Extract Markdown images
        const imgRegex = /!\[.*?\]\((.*?)\)/g;
        let imgMatch;
        while ((imgMatch = imgRegex.exec(msg.content)) !== null) {
          let imgUrl = imgMatch[1];
          if (imgUrl.startsWith('/uploads/')) imgUrl = window.location.origin + imgUrl;
          mediaItems.push({ type: 'image', url: imgUrl });
        }

        let textToParse = msg.content
          .replace(/```(?:[a-z]*\n)?([\s\S]*?)```/gi, '$1')
          .replace(/!\[.*?\]\(.*?\)/g, '');

        const lines = textToParse.split('\n');
        for (let i = 0; i < lines.length; i++) {
          let line = lines[i];
          let isHeader = false;
          let indent = 0;

          if (line.match(/^#\s/)) { doc.setFontSize(18); doc.setFont("helvetica", "bold"); line = line.replace(/^#\s/, ''); isHeader = true; }
          else if (line.match(/^##\s/)) { doc.setFontSize(16); doc.setFont("helvetica", "bold"); line = line.replace(/^##\s/, ''); isHeader = true; }
          else if (line.match(/^###+\s/)) { doc.setFontSize(13); doc.setFont("helvetica", "bold"); line = line.replace(/^###+\s/, ''); isHeader = true; }
          else if (line.match(/^[-*]\s/)) { doc.setFontSize(11); doc.setFont("helvetica", "normal"); line = '• ' + line.replace(/^[-*]\s/, ''); indent = 5; }
          else if (line.match(/^\d+\.\s/)) { doc.setFontSize(11); doc.setFont("helvetica", "normal"); indent = 5; }
          else { doc.setFontSize(11); doc.setFont("helvetica", "normal"); }

          line = line.replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1').replace(/__(.*?)__/g, '$1').replace(/`(.*?)`/g, '$1');
          line = line.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"').replace(/[\u2013\u2014]/g, '-');
          line = line.replace(/[^\x00-\x7F]/g, '');

          if (!line.trim()) { y += 3; continue; }

          doc.setTextColor(0, 0, 0);
          const splitLines = doc.splitTextToSize(line, maxLineWidth - indent);
          for (let j = 0; j < splitLines.length; j++) {
            if (y > pageHeight - 15) { doc.addPage(); y = 20; }
            doc.text(splitLines[j], margin + indent, y);
            y += (isHeader ? 7 : 5);
          }
          if (isHeader) y += 2;
        }

        // Render SVGs and images into PDF
        for (const item of mediaItems) {
          let imgObj = null;

          if (item.type === 'svg') {
            imgObj = await new Promise((resolve) => {
              const blob = new Blob([item.data], { type: 'image/svg+xml;charset=utf-8' });
              const url = URL.createObjectURL(blob);
              const img = new Image();
              img.onload = () => {
                const canvas = document.createElement('canvas');
                const scale = 4;
                canvas.width = (img.width || 500) * scale;
                canvas.height = (img.height || 500) * scale;
                const maxDim = 4000;
                if (canvas.width > maxDim || canvas.height > maxDim) {
                  const ratio = Math.min(maxDim / canvas.width, maxDim / canvas.height);
                  canvas.width *= ratio;
                  canvas.height *= ratio;
                }
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
                URL.revokeObjectURL(url);
                resolve({ dataUrl, w: canvas.width, h: canvas.height, link: null });
              };
              img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
              img.src = url;
            });
          } else if (item.type === 'image') {
            imgObj = await new Promise((resolve) => {
              const img = new Image();
              img.crossOrigin = "Anonymous";
              img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0);
                try {
                  const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
                  resolve({ dataUrl, w: canvas.width, h: canvas.height, link: item.url });
                } catch (e) {
                  resolve({ dataUrl: null, w: 0, h: 0, link: item.url, corsError: true });
                }
              };
              img.onerror = () => { resolve({ dataUrl: null, w: 0, h: 0, link: item.url, error: true }); };
              img.src = item.url;
            });
          }

          if (imgObj) {
            if (imgObj.dataUrl) {
              let pdfImgW = maxLineWidth * 0.85;
              let pdfImgH = (imgObj.h / imgObj.w) * pdfImgW;
              if (pdfImgH > (pageHeight * 0.5)) {
                pdfImgH = pageHeight * 0.5;
                pdfImgW = (imgObj.w / imgObj.h) * pdfImgH;
              }
              let xPos = margin + (maxLineWidth - pdfImgW) / 2;
              if (y + pdfImgH + 10 > pageHeight - 15) { doc.addPage(); y = 20; }
              doc.addImage(imgObj.dataUrl, 'JPEG', xPos, y, pdfImgW, pdfImgH);
              y += pdfImgH + 4;
            }
            if (imgObj.link) {
              if (y + 10 > pageHeight - 15) { doc.addPage(); y = 20; }
              doc.setFontSize(9);
              doc.setTextColor(16, 163, 127);
              let linkText = "🔗 View / Download Original Image";
              if (imgObj.corsError) linkText = "🔗 View Original Image (Direct PDF render blocked by server)";
              if (imgObj.error) linkText = "🔗 View Original Image (Failed to load preview)";
              doc.textWithLink(linkText, margin, y, { url: imgObj.link });
              y += 6;
              doc.setTextColor(0, 0, 0);
            }
          }
        }

        y += 6; // Spacing between messages
      }

      doc.save(`${filename}.pdf`);
    } finally {
      if (exportBtn) exportBtn.innerHTML = originalBtnText;
    }
  }
};

function downloadFile(content, fileName, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
