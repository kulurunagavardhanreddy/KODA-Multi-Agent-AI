// --- KODA Customize AI UI Module ---
window.openCustomizeModal = function () {
  const dropdown = document.getElementById('settings-dropdown') || document.querySelector('.settings-dropdown');
  if (dropdown) dropdown.classList.remove('show');
  document.getElementById('user-name-input').value = userName;
  document.getElementById('bot-name-input').value = botName;
  document.getElementById('mic-lang-select').value = micLang;
  if (selectedVoiceURI) document.getElementById('voice-select').value = selectedVoiceURI;
  document.getElementById('settings-modal').style.display = 'flex';
};

window.closeSettings = function () {
  document.getElementById('settings-modal').style.display = 'none';
};

window.saveSettings = function () {
  userName = document.getElementById('user-name-input').value.trim();
  botName = document.getElementById('bot-name-input').value.trim();
  micLang = document.getElementById('mic-lang-select').value;
  selectedVoiceURI = document.getElementById('voice-select').value;
  storage.setItem('userName', userName);
  storage.setItem('botName', botName);
  storage.setItem('micLang', micLang);
  storage.setItem('ttsVoice', selectedVoiceURI);
  pushSyncData();
  closeSettings();

  // Update UI elements dynamically
  if (!isGuest) {
    const authBtn = document.getElementById('auth-menu-btn');
    const initial = userName ? userName.charAt(0).toUpperCase() : 'U';
    if (authBtn) authBtn.innerHTML = `<div id="dropdown-avatar" style="width: 24px; height: 24px; background: #10a37f; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: bold;">${initial}</div> Account`;
  }
};

// --- Voice Population Logic ---
function populateVoiceList() {
  const availableVoices = window.speechSynthesis.getVoices();
  const voiceSelect = document.getElementById('voice-select');
  if (!voiceSelect) return;
  voiceSelect.innerHTML = '';

  const voicesToShow = availableVoices; // 🌍 UNLOCK ALL LANGUAGES!

  voicesToShow.forEach(voice => {
    const option = document.createElement('option');
    option.textContent = `${voice.name} (${voice.lang})`;
    option.value = voice.voiceURI;
    voiceSelect.appendChild(option);
  });

  // Default to Indian English if no custom voice is selected yet!
  if (!selectedVoiceURI) {
    const indianVoice = voicesToShow.find(v => v.lang === 'en-IN');
    if (indianVoice) selectedVoiceURI = indianVoice.voiceURI;
  }
  voiceSelect.value = selectedVoiceURI;
}

populateVoiceList();
if (speechSynthesis.onvoiceschanged !== undefined) {
  speechSynthesis.onvoiceschanged = populateVoiceList;
}
