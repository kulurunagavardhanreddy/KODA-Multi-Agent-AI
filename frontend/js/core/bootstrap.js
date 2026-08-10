// script.js — KODA Bootstrap Entry Point
// Minimal setup that must run synchronously before all other scripts.

// --- Mobile Viewport Injection ---
// Guarantees correct scaling on phones (prevents "desktop-zoomed-out" look).
if (!document.querySelector('meta[name="viewport"]')) {
  const meta = document.createElement('meta');
  meta.name = "viewport";
  meta.content = "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no";
  document.head.appendChild(meta);
}

// --- Standard Fetch Wrapper for NGROK & BASE_URL ---
// Automatically skips ngrok warnings and appends base URL for relative paths.
const originalFetch = window.fetch;
window.fetch = function (url, options = {}) {
  // If URL is relative (starts with /) and we have window.BASE_URL configured
  if (url.startsWith("/") && window.BASE_URL) {
    url = window.BASE_URL + url;
  }
  options.headers = options.headers || {};
  options.headers["ngrok-skip-browser-warning"] = "69420";
  return originalFetch(url, options);
};

// --- Global 401 Unauthorized Token Handler ---
// Purges expired or invalid tokens from both localStorage & sessionStorage, then redirects cleanly.
window.handleUnauthorizedToken = function () {
  console.warn("⚠️ Token expired or unauthorized! Purging session and redirecting to login.");
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch (e) {
    console.warn("Storage clear exception:", e);
  }
  if (!window.location.pathname.includes('login')) {
    window.location.href = '/login.html';
  }
};