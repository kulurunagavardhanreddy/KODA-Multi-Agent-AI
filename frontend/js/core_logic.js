// frontend/js/core_logic.js

// ==========================================
// KODA CENTRAL MODULE LOADER (core_logic.js)
// ==========================================
// All feature modules are registered here in strict dependency order.
// To add a new module: just append its path to the correct section below.
// No need to touch index.html.

(function loadKodaModules() {
  const version = '6.2';

  const modules = [
    // ── CORE BOOTSTRAP & CONFIGURATION ─────────────────────
    '/js/core/bootstrap.js',      // Viewport setup, fetch wrapper, ngrok bypass
    '/js/core/config.js',         // BASE_URL client configuration
    '/js/core/state.js',          // Global variables & auth check
    '/js/core/sync.js',           // Cloud sync (push/pull settings & sessions)


    // ── UI: Icon & Style Foundation ───────────────────────
    '/js/ui/icons.js',            // SVG icon string library
    '/js/ui/styles_inject.js',    // Runtime CSS for agent steps & sources panel

    // ── SETTINGS ──────────────────────────────────────────
    '/js/settings/email_intelligence.js',
    '/js/settings/custom_ai.js',
    '/js/settings/theme.js',
    '/js/settings/account.js',
    '/js/settings/clear_all_chats.js',

    // ── UI: Feature Panels & Renderers ────────────────────
    '/js/ui/sidebar.js',           // Sidebar session list, chat history, share, toggleSidebar
    '/js/ui/sources_panel.js',     // RAG source attribution panel
    '/js/ui/dictation_visualizer.js', // Voice dictation visualizer
    '/js/ui/workspace.js',         // Workspace/directory selection

    // ── UI: Input & Toolbar ───────────────────────────────
    '/js/ui/input_controls.js',    // Send button state, greeting, clearInput, handleEnter
    '/js/ui/dropdown_dismiss.js',  // Close dropdowns/sidebar on outside click
    '/js/ui/toolbar.js',           // Attach menu, temp chat toggle, export menu toggle

    // ── UI chat: Message Rendering & Actions ──────────────────
    '/js/chat/chat_renderer.js',     // Message render, edit, TTS, translate, copy
    '/js/chat/message_sender.js',    // sendMessage, SSE streaming, getLiveLocation
    '/js/chat/chat_sessions.js',     // Session switching, pagination, save/load
    '/js/chat/branching.js',         // Conversation branch & tree logic
    '/js/chat/attachments.js',       // File & image upload & preview
    '/js/chat/shared_chat.js',       // Import shared conversation via link
    '/js/chat/markdown_mermaid.js',  // Markdown + Mermaid diagram rendering
    '/js/chat/export_chat.js',       // Export as TXT / DOC / PDF


    // ── CORE: App Boot (must be LAST) ─────────────────────
    '/js/core/app_init.js',        // DOMContentLoaded: session init, swipe, location
  ];

  if (document.readyState === 'loading') {
    // Synchronous write during HTML parsing: guarantees exact load order
    // and blocks DOMContentLoaded until all modules are ready.
    modules.forEach(src => {
      document.write(`<script src="${src}?v=${version}"><\/script>`);
    });
  } else {
    // Sequential script loader fallback to prevent out-of-order execution and race conditions
    let promise = Promise.resolve();
    modules.forEach(src => {
      promise = promise.then(() => new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = `${src}?v=${version}`;
        script.onload = resolve;
        script.onerror = () => { console.warn(`[ModuleLoader] Failed to load: ${src}`); resolve(); };
        document.head.appendChild(script);
      }));
    });
  }
})();