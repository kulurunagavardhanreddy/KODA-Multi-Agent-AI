// frontend/js/core/app_init.js

// --- KODA App Initialization ---
// DOMContentLoaded boot sequence: cloud sync, sessions, sidebar state,
// input listeners, theme, location tracking, and mobile swipe gestures.
// This file must load LAST in the module chain.

async function initKodaApp() {
  // 🌍 CLOUD SYNC: Load user data across devices before rendering (non-blocking with 2s timeout)
  try {
    await Promise.race([
      loadSyncData(),
      new Promise((_, reject) => setTimeout(() => reject("Sync timeout"), 2000))
    ]);
  } catch (e) {
    console.warn("loadSyncData notice on init:", e);
  }

  // Ensure currentSessionId is valid if missing without aggressively overriding the active chat
  if (!currentSessionId && chatSessions.length > 0) {
    currentSessionId = chatSessions[0].id;
    storage.setItem('currentSessionId', currentSessionId);
  }

  // Check for shared chat via URL path
  if (window.location.pathname.startsWith('/shared/')) {
    const shareId = window.location.pathname.split('/')[2];
    await importSharedChat(shareId);
  }

  // 🎨 Apply saved theme on load and listen for OS-level changes
  applyTheme(currentTheme);
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
    if ((storage.getItem('theme') || 'dark') === 'system') applyTheme('system');
  });

  // Dynamic Auth Button (Guest vs Logged In)
  if (isGuest) {
    const authBtn = document.getElementById('auth-menu-btn');
    if (authBtn) {
      authBtn.innerHTML = '🚪 Log In / Sign Up';
      authBtn.onclick = () => { window.location.href = '/login.html'; };
    }
  } else {
    const authBtn = document.getElementById('auth-menu-btn');
    if (authBtn) {
      const initial = userName ? userName.charAt(0).toUpperCase() : 'U';
      authBtn.innerHTML = `<div id="dropdown-avatar" style="width: 24px; height: 24px; background: #10a37f; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: bold;">${initial}</div> Account`;
    }
  }

  // Inject Disclaimer text below input if it doesn't exist
  const inputArea = document.querySelector('.input-area');
  if (inputArea && !document.querySelector('.disclaimer-text')) {
    const disclaimer = document.createElement('div');
    disclaimer.className = 'disclaimer-text';
    disclaimer.innerHTML = 'Ｋ Ⓞ Ɖ 𐌡 can make mistakes. Check important info.';
    inputArea.appendChild(disclaimer);
  }

  const inputField = document.getElementById("input");

  // Inject Custom Tooltip for Attach Button
  const attachBtn = document.getElementById("attach-btn");
  if (attachBtn) {
    attachBtn.removeAttribute("title");
    if (!attachBtn.querySelector('.custom-tooltip')) {
      const tooltip = document.createElement("div");
      tooltip.className = "custom-tooltip";
      tooltip.innerHTML = `Attach files and more <span class="shortcut-key">/</span>`;
      attachBtn.appendChild(tooltip);
    }
  }

  // Auto-resize textarea as user types; also open attach dropdown on '/' shortcut
  if (inputField) {
    inputField.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = (this.scrollHeight) + "px";
      toggleSendButtonState();

      const attachDropdown = document.getElementById('attach-dropdown');
      if (attachDropdown) {
        if (this.value === '/' || this.value.endsWith(' /') || this.value.endsWith('\n/')) {
          attachDropdown.classList.add('show');
        } else {
          attachDropdown.classList.remove('show');
        }
      }
    });

    // Allow pasting images directly into the input field
    inputField.addEventListener("paste", function (e) {
      const clipboardData = e.clipboardData || window.clipboardData;
      if (!clipboardData) return;
      for (let i = 0; i < clipboardData.items.length; i++) {
        if (clipboardData.items[i].type.indexOf("image") !== -1) {
          e.preventDefault();
          const blob = clipboardData.items[i].getAsFile();
          processImageFile(blob);
          break;
        }
      }
    });
  }

  // 🛡️ Hide broken images instantly
  document.addEventListener('error', function (e) {
    if (e.target && e.target.tagName === 'IMG') {
      e.target.style.display = 'none';
    }
  }, true);

  // 🧠 SMART TAB SESSION RESTORE (ChatGPT-style session persistence):
  // F5 / Refresh in an active tab restores the current chat session.
  // Opening a new tab or closing the tab opens a fresh New Chat.
  const isTabReload = sessionStorage.getItem('activeTabSession') === 'true';
  sessionStorage.setItem('activeTabSession', 'true');

  const savedSessionId = storage.getItem('currentSessionId');
  const validSessionExists = savedSessionId && Array.isArray(chatSessions) && chatSessions.some(s => s.id === savedSessionId);

  if (isTabReload && validSessionExists) {
    console.log("🔄 Tab reload detected — restoring active chat session:", savedSessionId);
    await loadSession(savedSessionId);
  } else {
    console.log("✨ New tab session — starting fresh chat");
    startNewChat(false);
  }

  if (typeof window.renderSidebar === 'function') window.renderSidebar();

  // --- Sidebar initial state ---
  const openBtn = document.getElementById('open-sidebar-btn');
  const storedSidebarState = localStorage.getItem('sidebarCollapsed');
  let shouldCollapse = storedSidebarState === null ? true : storedSidebarState === 'true';

  // Always start collapsed on mobile (<= 768px)
  if (window.innerWidth <= 768) shouldCollapse = true;

  const sidebarElement = document.querySelector('.sidebar');
  if (sidebarElement) {
    if (shouldCollapse) {
      sidebarElement.classList.add('collapsed');
      document.body.classList.add('sidebar-closed');
    } else {
      sidebarElement.classList.remove('collapsed');
      document.body.classList.remove('sidebar-closed');
    }
  }
  if (openBtn) openBtn.setAttribute('title', shouldCollapse ? 'Expand menu' : 'Collapse menu');

  // Auto-focus input on load
  if (inputField) inputField.focus();

  // Keep focus on input when clicking anywhere in the chat area
  const mainContent = document.getElementById('main-content') || document.querySelector('.main-content');
  if (mainContent) {
    mainContent.addEventListener('click', function (e) {
      if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'TEXTAREA' && window.getSelection().toString() === '') {
        if (inputField) inputField.focus();
      }
    });
  }

  // Fetch user location on page load
  try {
    await getLiveLocation();
  } catch (_) {}

  // Track location continuously in the background
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      (pos) => { userLocation = `${pos.coords.latitude},${pos.coords.longitude}`; },
      (err) => { console.log("Live tracking error:", err.message); },
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 10000 }
    );
  }

  // Scroll-to-bottom floating button + infinite scroll trigger
  const chatbox = document.getElementById("chatbox");
  const scrollBtn = document.getElementById("scroll-bottom-btn");
  if (chatbox) {
    chatbox.addEventListener("scroll", () => {
      const distanceToBottom = chatbox.scrollHeight - chatbox.scrollTop - chatbox.clientHeight;
      if (!window.isProgrammaticScrolling) {
        isUserScrolledUp = distanceToBottom > 50;
      }
      if (scrollBtn) {
        if (distanceToBottom > 150) {
          scrollBtn.classList.add("show");
        } else {
          scrollBtn.classList.remove("show");
        }
      }
      if (chatbox.scrollTop === 0 && typeof window.loadOlderMessages === 'function') {
        window.loadOlderMessages();
      }
    });
  }

  updateEmptyChatState();

  // --- Mobile Swipe Gestures (open/close sidebar) ---
  let touchStartX = 0;
  let touchStartY = 0;
  document.addEventListener('touchstart', e => {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  });
  document.addEventListener('touchend', e => {
    if (window.innerWidth > 1024) return;
    const touchEndX = e.changedTouches[0].screenX;
    const touchEndY = e.changedTouches[0].screenY;
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    if (Math.abs(touchEndY - touchStartY) > 50) return;
    if (touchEndX - touchStartX > 60 && touchStartX < 150 && sidebar.classList.contains('collapsed')) {
      window.toggleSidebar();
    }
    if (touchStartX - touchEndX > 60 && !sidebar.classList.contains('collapsed')) {
      window.toggleSidebar();
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener("DOMContentLoaded", initKodaApp);
} else {
  initKodaApp();
}
