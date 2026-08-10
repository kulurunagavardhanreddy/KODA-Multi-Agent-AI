// login.js

let isLogin = true;

function switchTab(tab) {
    isLogin = tab === 'login';
    document.getElementById('tab-login').classList.toggle('active', isLogin);
    document.getElementById('tab-signup').classList.toggle('active', !isLogin);
    document.getElementById('username-group').style.display = isLogin ? 'none' : 'block';
    document.getElementById('error-msg').innerText = '';
}

async function handleAuth() {
    const email = document.getElementById('email').value.trim();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const errorMsg = document.getElementById('error-msg');

    if (!email || !password || (!isLogin && !username)) {
        return errorMsg.innerText = "Please fill in all fields.";
    }
    
    if (!email.includes('@')) {
        return errorMsg.innerText = "Please enter a valid email address.";
    }

    const endpoint = isLogin ? '/api/login' : '/api/signup';
    const bodyData = isLogin ? { email, password } : { email, username, password };
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyData)
        });
        const data = await response.json();

        if (!response.ok) {
            errorMsg.style.color = '#ff4a4a';
            if (data.detail && Array.isArray(data.detail)) {
                const field = data.detail[0].loc[1] || 'input';
                errorMsg.innerText = `Invalid ${field}: ${data.detail[0].msg}`;
            } else {
                errorMsg.innerText = data.detail || data.error || "Authentication failed.";
            }
            return;
        }

        if (!isLogin) {
            errorMsg.style.color = '#10a37f';
            errorMsg.innerText = "Account created! Please log in.";
            setTimeout(() => switchTab('login'), 1500);
        } else {
            setAuthSession(data, false);
        }
    } catch (err) {
        errorMsg.innerText = "Connection error. Check backend server.";
    }
}

async function handleGuestAuth(e) {
    e.preventDefault();
    const errorMsg = document.getElementById('error-msg');
    errorMsg.style.color = '#8e8ea0';
    errorMsg.innerText = "Connecting as guest...";
    try {
        const response = await fetch('/api/guest-login', { method: 'POST' });
        const data = await response.json();
        if (data.access_token) {
            setAuthSession(data, true);
        } else {
            errorMsg.style.color = '#ff4a4a';
            errorMsg.innerText = "Guest login failed.";
        }
    } catch (err) {
        errorMsg.style.color = '#ff4a4a';
        errorMsg.innerText = "Connection error.";
    }
}

let isGoogleInitialized = false;

async function initGoogleAuth() {
    if (isGoogleInitialized) return;
    try {
        const res = await fetch('/api/config', {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const configData = await res.json();
        
        if (!configData.google_client_id || configData.google_client_id === 'your_google_client_id_here') {
            return;
        }

        if (window.google && window.google.accounts && window.google.accounts.id) {
            google.accounts.id.initialize({
                client_id: configData.google_client_id,
                callback: handleCredentialResponse,
                auto_select: false
            });
            isGoogleInitialized = true;
        }
    } catch (err) {
        console.warn("Google Auth Init warning:", err);
    }
}

async function handleGoogleAuth(e) {
    if (e) e.preventDefault();
    const errorMsg = document.getElementById('error-msg');
    
    try {
        if (!isGoogleInitialized) {
            await initGoogleAuth();
        }

        if (window.google && window.google.accounts && window.google.accounts.id) {
            google.accounts.id.prompt((notification) => {
                if (notification.isNotDisplayed()) {
                    const reason = notification.getNotDisplayedReason();
                    console.warn("Google One-Tap not displayed:", reason);
                    errorMsg.style.color = '#ff4a4a';
                    errorMsg.innerText = "Google Sign-In 403 Forbidden: Add 'http://127.0.0.1:8000' & domain to Authorized JavaScript Origins in Google Cloud Console.";
                } else if (notification.isSkippedMoment()) {
                    console.warn("Google One-Tap skipped:", notification.getSkippedReason());
                }
            });
        } else {
            errorMsg.innerText = "Google Sign-In library loading...";
        }
    } catch (err) {
        errorMsg.innerText = "Google auth connection error.";
    }
}

async function handleCredentialResponse(response) {
    const errorMsg = document.getElementById('error-msg');
    try {
        const res = await fetch('/api/google-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: response.credential })
        });
        const data = await res.json();
        
        if (res.ok && data.access_token) {
            setAuthSession(data, false);
        } else {
            errorMsg.innerText = data.detail || "Google auth failed.";
        }
    } catch (err) {
        errorMsg.innerText = "Connection error.";
    }
}

function setAuthSession(data, isGuest) {
    const prevEmail = localStorage.getItem('userEmail');
    const newEmail = data.email || (isGuest ? 'Guest Session' : '');

    // Purge legacy session state if switching user accounts
    if (prevEmail && prevEmail !== newEmail) {
        localStorage.removeItem('chatSessions');
        localStorage.removeItem('currentSessionId');
    }

    localStorage.setItem('isGuest', isGuest ? 'true' : 'false');
    
    if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        sessionStorage.setItem('token', data.access_token);
    }
    if (data.username) {
        localStorage.setItem('userName', data.username);
    }
    if (data.email) {
        localStorage.setItem('userEmail', data.email);
    }
    
    window.location.href = '/';
}