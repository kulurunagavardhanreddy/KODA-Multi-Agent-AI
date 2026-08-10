// frontend/js/ui/dropdown_dismiss.js

// --- KODA Dropdown Dismissal ---
// Global click listener that closes any open dropdown, attach menu,
// search modal, or sidebar when the user clicks outside of them.

document.addEventListener('click', function (e) {
  // Close settings dropdown
  const dropdown = document.getElementById('settings-dropdown') || document.querySelector('.settings-dropdown');
  if (dropdown && dropdown.classList.contains('show')) {
    if (!e.target.closest('.sidebar-footer')) {
      dropdown.classList.remove('show');
    }
  }

  // Close chat options (rename / delete) dropdown
  const chatOptionsDropdown = document.getElementById('chat-options-dropdown');
  if (chatOptionsDropdown && chatOptionsDropdown.classList.contains('show')) {
    if (!e.target.closest('.options-btn') && !e.target.closest('.chat-options-dropdown')) {
      chatOptionsDropdown.classList.remove('show');
    }
  }

  // Close export format dropdown
  const exportDropdown = document.getElementById('export-dropdown');
  if (exportDropdown && exportDropdown.classList.contains('show')) {
    if (!e.target.closest('.export-dropdown') && !e.target.closest('button[title="Export Chat"]')) {
      exportDropdown.classList.remove('show');
    }
  }

  // Close attach file dropdown
  const attachDropdown = document.getElementById('attach-dropdown');
  if (attachDropdown && attachDropdown.classList.contains('show')) {
    if (!e.target.closest('.attach-dropdown') && !e.target.closest('#attach-btn')) {
      attachDropdown.classList.remove('show');
    }
  }

  // Close chat search modal
  const searchModal = document.getElementById('search-modal');
  if (searchModal && searchModal.style.display === 'flex') {
    if (!e.target.closest('.modal-content') && !e.target.closest('.sidebar-search')) {
      closeSearchModal();
    }
  }

  // Auto-close sidebar on mobile when tapping outside
  if (window.innerWidth <= 1024) {
    const sidebar = document.querySelector('.sidebar');
    const openBtn = document.getElementById('open-sidebar-btn');
    if (sidebar && !sidebar.classList.contains('collapsed')) {
      if (!sidebar.contains(e.target) && (!openBtn || !openBtn.contains(e.target))) {
        window.toggleSidebar();
      }
    }
  }
});
