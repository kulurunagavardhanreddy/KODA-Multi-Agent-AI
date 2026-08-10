// --- KODA Attachments UI Module (Files & Images) ---

window.processImageFile = async function (file) {
  if (file.size > 10 * 1024 * 1024) { // 10MB limit
    alert("Image size must be less than 10MB.");
    return;
  }
  if (isGuest) {
    alert("Please log in to upload images.");
    return;
  }

  const inputWrapper = document.querySelector(".input-wrapper");
  let attachBadge = document.getElementById("attach-badge");
  if (!attachBadge) {
    attachBadge = document.createElement("div");
    attachBadge.id = "attach-badge";
    inputWrapper.appendChild(attachBadge);
  }
  attachBadge.innerHTML = `<span class="btn-spinner" style="border-color:#10a37f; border-top-color:transparent;"></span> <b>Uploading...</b>`;
  toggleSendButtonState();

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/upload-image", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "ngrok-skip-browser-warning": "true"
      },
      body: formData
    });

    const responseText = await response.text();
    let data;
    try {
      data = JSON.parse(responseText);
    } catch (err) {
      throw new Error(`Server Error (${response.status}): Received an HTML error page.`);
    }

    if (!response.ok) throw new Error(data.detail || data.error || "Upload failed");

    // 🚀 PHASE 3: Store the tiny network URL instead of massive Base64
    pendingImage = {
      url: window.location.origin + data.url,
      name: file.name || "Pasted_Image.png"
    };

    attachBadge.innerHTML = `<img src="${data.url}" style="width:20px;height:20px;border-radius:4px;vertical-align:middle;object-fit:cover;"> <b>${pendingImage.name}</b> <span class="remove-attach-btn" title="Remove image" onclick="removeAttachment()">✖</span>`;
    toggleSendButtonState();
  } catch (err) {
    alert("Failed to upload image. " + err.message);
    removeAttachment();
  }
};

window.handleImageUpload = function (event) {
  const file = event.target.files[0];
  if (!file) return;
  processImageFile(file);
  event.target.value = ""; // Reset input
};

window.removeAttachment = function () {
  pendingDocument = null;
  const badge = document.getElementById("attach-badge");
  if (badge) badge.remove();
  pendingImage = null;
  const fileInput = document.getElementById("file-input");
  if (fileInput) fileInput.value = "";
  toggleSendButtonState();
};

window.handleFileUpload = async function (event) {
  const file = event.target.files[0];
  if (!file) return;

  // 🚀 AUTO-REROUTE: If user accidentally clicked Document but uploaded an Image, reroute to Vision!
  if (file.type.startsWith("image/")) {
    processImageFile(file);
    event.target.value = "";
    return;
  }

  const chatbox = document.getElementById("chatbox");
  const attachBtn = document.getElementById("attach-btn");

  // Show loading state
  attachBtn.innerHTML = "⏳";
  attachBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("session_id", currentSessionId || "");

  try {
    const response = await fetch("/upload-pdf", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}` // Pass JWT for multi-tenant security
      },
      body: formData
    });
    if (response.status === 401) {
      if (typeof window.handleUnauthorizedToken === 'function') {
        window.handleUnauthorizedToken();
      } else {
        window.location.href = '/login.html';
      }
      return;
    }
    const data = await response.json();

    if (data.error) throw new Error(data.error);

    // Store extracted text temporarily instead of sending to chat history directly
    pendingDocument = {
      filename: data.filename,
      text: data.text || "",
      b64: data.pdf_image_b64 || null
    };

    // Show attachment badge above the input field
    const inputWrapper = document.querySelector(".input-wrapper");
    let attachBadge = document.getElementById("attach-badge");
    if (!attachBadge) {
      attachBadge = document.createElement("div");
      attachBadge.id = "attach-badge";
      inputWrapper.appendChild(attachBadge);
    }
    attachBadge.innerHTML = `📎 <b>${data.filename}</b> <span class="remove-attach-btn" title="Remove attachment" onclick="removeAttachment()">✖</span>`;
  } catch (error) {
    alert("Failed to process file: " + error.message);
  } finally {
    attachBtn.innerHTML = "📎";
    attachBtn.disabled = false;
    event.target.value = ""; // Reset the input
    toggleSendButtonState();
  }
};
