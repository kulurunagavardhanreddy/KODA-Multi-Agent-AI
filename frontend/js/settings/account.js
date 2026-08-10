// --- KODA Account & Logout UI Module ---
window.openLogoutModal = function () {
  const dropdown = document.getElementById('settings-dropdown') || document.querySelector('.settings-dropdown');
  if (dropdown) dropdown.classList.remove('show');

  // Update Account Modal Details dynamically
  const name = localStorage.getItem('userName') || sessionStorage.getItem('userName') || userName || "User";
  const email = localStorage.getItem('userEmail') || sessionStorage.getItem('userEmail') || userEmail || "";
  
  const displayName = isGuest ? "Guest User" : name;
  const displayEmail = isGuest ? "Guest Access (Session Only)" : (email && email !== "user@example.com" ? email : `${name.toLowerCase().replace(/\s+/g, '')}@account`);

  const avatar = document.getElementById('account-avatar');
  if (avatar) avatar.innerText = displayName.charAt(0).toUpperCase();
  const nameDisp = document.getElementById('account-name-display');
  if (nameDisp) nameDisp.innerText = displayName;
  const emailDisp = document.getElementById('account-email-display');
  if (emailDisp) emailDisp.innerText = displayEmail;

  document.getElementById('logout-modal').style.display = 'flex';
};

window.closeLogoutModal = function () {
  document.getElementById('logout-modal').style.display = 'none';
};

window.confirmLogout = function () {
  console.log("🚪 [Account] Logging out user and clearing all local session storage...");
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch (e) {
    console.warn("Storage clear exception:", e);
  }
  window.location.href = '/login.html';
};
window.logout = window.confirmLogout;

// --- Memory Modal UI Logic ---
window.toggleSettingsDropdown = function (e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const dropdown = document.getElementById('settings-dropdown') || document.querySelector('.settings-dropdown');
  if (dropdown) dropdown.classList.toggle('show');
};
