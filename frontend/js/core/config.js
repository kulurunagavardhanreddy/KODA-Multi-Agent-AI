/**
 * frontend/js/config.js
 * Central environment configuration & dynamic routing detection
 */

// 🎯 ACTIVE SERVER ENVIRONMENT CONFIGURATION
let BASE_URL = "http://127.0.0.1:8000";     // 💻 Local central server (8000)

// 🎯 DYNAMIC LOCAL NETWORK DETECTION
if (window.location.hostname !== "127.0.0.1" && window.location.hostname !== "localhost" && !window.location.hostname.includes('ngrok') && !window.location.hostname.includes('ngrok-free') && window.location.hostname !== "") {
    BASE_URL = `http://${window.location.hostname}:8000`;
} else if (window.location.hostname.includes('ngrok') || window.location.hostname.includes('ngrok-free')) {
    BASE_URL = window.location.origin;
}

// Expose globally to window
window.BASE_URL = BASE_URL;
