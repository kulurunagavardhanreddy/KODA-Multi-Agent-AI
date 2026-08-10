// ==============================================
// KODA Theme Configuration
// ==============================================

// Load saved theme
window.currentTheme = storage.getItem("theme") || "dark";

// Apply selected theme
window.applyTheme = function (theme) {
  const body = document.body;

  // Remove existing classes
  body.classList.remove("light-mode", "dark-mode");

  let actualTheme = theme;

  // System theme
  if (theme === "system") {
    actualTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  if (actualTheme === "light") {
    body.classList.add("light-mode");
  } else {
    body.classList.add("dark-mode");
  }

  currentTheme = theme;
};

// ----------------------------
// Theme Modal
// ----------------------------

window.openThemeModal = function () {
  const dropdown =
    document.getElementById("settings-dropdown") ||
    document.querySelector(".settings-dropdown");

  if (dropdown) dropdown.classList.remove("show");

  document.getElementById("theme-input").value = currentTheme;
  document.getElementById("theme-modal").style.display = "flex";
};

window.closeThemeModal = function () {
  document.getElementById("theme-modal").style.display = "none";

  // Restore previous selection
  applyTheme(currentTheme);
};

window.saveTheme = function () {
  currentTheme = document.getElementById("theme-input").value;

  storage.setItem("theme", currentTheme);

  applyTheme(currentTheme);

  closeThemeModal();
};