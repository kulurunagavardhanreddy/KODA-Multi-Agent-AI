// --- KODA Email Intelligence UI Module ---
let activeEmailTab = 'Critical';
let emailDashboardData = null;

function showEmailError(msg) {
  const errContainer = document.getElementById('email-modal-error');
  const errText = document.getElementById('email-error-text');
  if (errContainer && errText) {
    errText.innerText = msg;
    errContainer.style.display = 'flex';
  }
}

function hideEmailError() {
  const errContainer = document.getElementById('email-modal-error');
  if (errContainer) {
    errContainer.style.display = 'none';
  }
}

window.openEmailIntelligenceModal = async function () {
  const dropdown = document.getElementById('settings-dropdown') || document.querySelector('.settings-dropdown');
  if (dropdown) dropdown.classList.remove('show');

  // Hide any previous error banner
  hideEmailError();

  // Open modal structure first to show user setup environment
  document.getElementById('email-intelligence-modal').style.display = 'flex';

  // Fetch settings from API
  try {
    const res = await fetch('/api/email/settings', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 403) {
      showEmailError("Guests cannot access Inbox Intelligence. Please register or log in.");
      // Fallback: show disabled setup screen
      updateEmailModalUI({ enabled: 0 });
      return;
    }
    if (!res.ok) throw new Error("Failed to load settings.");

    const settings = await res.json();
    updateEmailModalUI(settings);
  } catch (err) {
    console.error(err);
    showEmailError("Error loading Email Intelligence settings: " + err.message);
    // Fallback: show disabled setup screen
    updateEmailModalUI({ enabled: 0 });
  }
};

window.closeEmailIntelligenceModal = function () {
  document.getElementById('email-intelligence-modal').style.display = 'none';
};

function updateEmailModalUI(settings) {
  hideEmailError();
  const statusContainer = document.getElementById('email-status-container');
  const onboardingPanel = document.getElementById('email-onboarding');
  const dashboardPanel = document.getElementById('email-dashboard');

  if (settings.enabled) {
    statusContainer.innerHTML = `
      <div class="email-status-badge status-active">
        <span class="status-pulse"></span>
        Active: ${settings.connected_email}
      </div>
    `;
    onboardingPanel.style.display = 'none';
    dashboardPanel.style.display = 'flex';

    // Fetch and populate dashboard metrics & list
    refreshEmailDashboard();
  } else {
    statusContainer.innerHTML = `
      <div class="email-status-badge status-disabled">
        Disabled
      </div>
    `;
    onboardingPanel.style.display = 'flex';
    dashboardPanel.style.display = 'none';

    // Set onboarding display text and configure checkboxes
    const onboardingDisplay = document.getElementById('email-onboarding-display');
    if (onboardingDisplay) {
      onboardingDisplay.innerText = userEmail || 'user@example.com';
    }

    // Safely restore permission toggles (app-password field no longer exists)
    const permRead = document.getElementById('email-perm-read');
    if (permRead) permRead.checked = !!settings.can_read;
    const permSum = document.getElementById('email-perm-summarize');
    if (permSum) permSum.checked = (settings.can_summarize !== 0);
    const permPri = document.getElementById('email-perm-prioritize');
    if (permPri) permPri.checked = (settings.can_prioritize !== 0);
    const permNot = document.getElementById('email-perm-notify');
    if (permNot) permNot.checked = (settings.can_notify !== 0);
    const permArc = document.getElementById('email-perm-archive');
    if (permArc) permArc.checked = !!settings.can_archive;
  }
}

// Gmail OAuth — uses the SAME Google token client as login (no redirect URI, no popup URL needed)
window.connectGoogleOAuth = async function () {
  hideEmailError();
  try {
    // Fetch the Google Client ID from backend config (already used for login)
    const cfgRes = await fetch('/api/config', {
      headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    if (!cfgRes.ok) throw new Error("Could not load app config.");
    const cfg = await cfgRes.json();
    const clientId = cfg.google_client_id;
    if (!clientId) throw new Error("Google Client ID not configured.");

    // Use Google's OAuth2 Code Client to retrieve a refresh-token eligible authorization code
    const tokenClient = google.accounts.oauth2.initCodeClient({
      client_id: clientId,
      scope: 'https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email',
      ux_mode: 'popup',
      callback: async (tokenResponse) => {
        if (tokenResponse.error) {
          showEmailError("Google authorisation failed: " + tokenResponse.error);
          return;
        }
        // Send authorization code to backend to store and generate access + refresh tokens
        try {
          const connectRes = await fetch('/api/email/connect-token', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ code: tokenResponse.code })
          });
          if (!connectRes.ok) {
            const err = await connectRes.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to save Gmail connection.");
          }
          // Reload settings and show dashboard
          const settingsRes = await fetch('/api/email/settings', {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          const settings = await settingsRes.json();
          updateEmailModalUI(settings);
        } catch (e) {
          showEmailError("Error saving Gmail token: " + e.message);
        }
      }
    });
    tokenClient.requestCode();

  } catch (err) {
    console.error(err);
    showEmailError("Error connecting Google account: " + err.message);
  }
};

window.refreshEmailDashboard = async function () {
  try {
    const res = await fetch('/api/email/dashboard', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error("Failed to fetch dashboard data.");

    emailDashboardData = await res.json();

    // Update metrics top banner
    document.getElementById('metric-unread-count').innerText = emailDashboardData.metrics.total_unread;
    document.getElementById('metric-time-saved').innerText = `${emailDashboardData.metrics.estimated_time_saved_minutes} mins`;

    // Update Sync status metrics
    const statusEl = document.getElementById('metric-sync-status');
    const timeEl = document.getElementById('metric-sync-time');
    const nextScanEl = document.getElementById('metric-next-scan');
    const syncModeEl = document.getElementById('metric-sync-mode');

    if (statusEl) {
      if (emailDashboardData.metrics.last_sync_error) {
        statusEl.innerText = "⚠️ Sync Error";
        statusEl.style.color = "#ef4444";
        statusEl.title = emailDashboardData.metrics.last_sync_error;
        if (timeEl) timeEl.innerText = "Check settings configuration.";
        if (nextScanEl) nextScanEl.style.display = 'none';
        if (syncModeEl) syncModeEl.style.display = 'none';
      } else {
        statusEl.innerText = "🟢 Connected";
        statusEl.style.color = "#10a37f";
        statusEl.removeAttribute("title");

        // Mode badge update
        if (syncModeEl) {
          syncModeEl.style.display = 'inline-block';
          if (emailDashboardData.metrics.watch_active === 1) {
            syncModeEl.innerText = "Mode: Webhook";
            syncModeEl.style.background = "rgba(16, 163, 127, 0.15)";
            syncModeEl.style.color = "#10a37f";
          } else {
            syncModeEl.innerText = "Mode: Polling";
            syncModeEl.style.background = "rgba(245, 158, 11, 0.15)";
            syncModeEl.style.color = "#f59e0b";
          }
        }

        // Last Scan & Next Scan update
        if (emailDashboardData.metrics.last_synced_at) {
          try {
            const lastScan = new Date(emailDashboardData.metrics.last_synced_at);
            if (timeEl) {
              timeEl.innerText = "Last AI Scan: " + lastScan.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            }
            if (nextScanEl) {
              nextScanEl.style.display = 'block';
              if (emailDashboardData.metrics.watch_active === 1) {
                nextScanEl.innerText = "Next Scan: Instant Push";
                nextScanEl.style.color = "#10a37f";
              } else {
                const intervalSec = emailDashboardData.metrics.polling_interval_seconds || 20;
                const nextScan = new Date(lastScan.getTime() + intervalSec * 1000);
                nextScanEl.innerText = "Next Scan: " + nextScan.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                nextScanEl.style.color = "#6e6e80";
              }
            }
          } catch (e) {
            if (timeEl) timeEl.innerText = "Last AI Scan: Just now";
            if (nextScanEl) nextScanEl.style.display = 'none';
          }
        } else {
          if (timeEl) timeEl.innerText = "Last AI Scan: Just now";
          if (nextScanEl) {
            nextScanEl.style.display = 'block';
            if (emailDashboardData.metrics.watch_active === 1) {
              nextScanEl.innerText = "Next Scan: Instant Push";
              nextScanEl.style.color = "#10a37f";
            } else {
              nextScanEl.innerText = "Next Scan: Pending...";
              nextScanEl.style.color = "#6e6e80";
            }
          }
        }
      }
    }

    // Update sidebar counts
    document.getElementById('count-Critical').innerText = emailDashboardData.metrics.critical_count;
    document.getElementById('count-High').innerText = emailDashboardData.metrics.high_count;
    document.getElementById('count-Medium').innerText = emailDashboardData.metrics.medium_count;
    document.getElementById('count-Low').innerText = emailDashboardData.metrics.low_count;

    // Render current active tab content
    renderEmailList();
  } catch (err) {
  }
};

window.switchEmailTab = function (tabName, element) {
  activeEmailTab = tabName;

  // Reset active classes
  const items = document.querySelectorAll('.email-dashboard-sidebar .email-sidebar-item');
  items.forEach(el => el.classList.remove('active'));
  element.classList.add('active');

  renderEmailList();
};

function getStatusBg(status) {
  if (status === 'Open') return 'rgba(239, 68, 68, 0.15)';
  if (status === 'Waiting for Internal Action') return 'rgba(249, 115, 22, 0.15)';
  if (status === 'Waiting for Customer') return 'rgba(59, 130, 246, 0.15)';
  if (status === 'Resolved') return 'rgba(16, 163, 127, 0.15)';
  if (status === 'Closed') return 'rgba(107, 114, 128, 0.15)';
  return 'rgba(239, 68, 68, 0.15)';
}

function getStatusColor(status) {
  if (status === 'Open') return '#ef4444';
  if (status === 'Waiting for Internal Action') return '#f97316';
  if (status === 'Waiting for Customer') return '#3b82f6';
  if (status === 'Resolved') return '#10a37f';
  if (status === 'Closed') return '#9ca3af';
  return '#ef4444';
}

function getHealthColor(health) {
  if (health === 'Healthy') return '#10a37f';
  if (health === 'At Risk') return '#f97316';
  if (health === 'Escalating') return '#ef4444';
  return '#10a37f';
}

function getHealthEmoji(health) {
  if (health === 'Healthy') return '🟢';
  if (health === 'At Risk') return '🟡';
  if (health === 'Escalating') return '🔴';
  return '🟢';
}

function renderEmailList() {
  const container = document.getElementById('email-list');
  container.innerHTML = '';

  if (!emailDashboardData || !emailDashboardData.digest || !emailDashboardData.digest[activeEmailTab] || emailDashboardData.digest[activeEmailTab].length === 0) {
    container.innerHTML = `
      <div class="email-list-empty">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="8" y1="12" x2="16" y2="12"></line>
        </svg>
        No ${activeEmailTab} priority emails found today.
      </div>
    `;
    return;
  }

  const emails = emailDashboardData.digest[activeEmailTab];
  emails.forEach(mail => {
    // Build star rating display
    let starHtml = '';
    for (let i = 0; i < 5; i++) {
      starHtml += i < mail.stars ? '★' : '☆';
    }

    // Format timestamp
    let formattedDate = 'Just now';
    if (mail.last_activity_at || mail.received_at) {
      try {
        const d = new Date(mail.last_activity_at || mail.received_at);
        formattedDate = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      } catch (e) { }
    }

    const card = document.createElement('div');
    card.className = 'email-card';
    card.style.cursor = 'pointer';
    card.onclick = () => openEmailDetailModal(mail.gmail_message_id);
    card.innerHTML = `
      <div class="email-card-header" style="display:flex; justify-content:space-between; align-items:center;">
        <span class="email-card-sender" style="font-weight:600; color:white;">${escapeHtml(mail.latest_message_sender || mail.sender)}</span>
        <span class="email-card-time" style="font-size:0.75rem; color:#8e8e93;">${formattedDate}</span>
      </div>
      <div class="email-card-subject" style="margin-top:6px; font-weight:600; font-size:0.95rem; color:white; display:flex; justify-content:space-between; align-items:center; gap:8px;">
        <span>${escapeHtml(mail.subject)}</span>
        <span style="font-size:0.65rem; font-weight:700; text-transform:uppercase; padding:2px 8px; border-radius:10px; background:${getStatusBg(mail.status)}; color:${getStatusColor(mail.status)}; border: 1px solid rgba(255,255,255,0.02);">${escapeHtml(mail.status || 'Open')}</span>
      </div>
      <div class="email-card-summary" style="margin-top:8px; line-height:1.4; background:rgba(255,255,255,0.01); border-left:2px solid #a78bfa; padding:4px 10px; border-radius:0 4px 4px 0; font-size:0.85rem; color:#b4b4b4;">
        <span style="color:#8e8e93; font-size:0.7rem; font-weight:700; text-transform:uppercase; display:block; margin-bottom:2px; letter-spacing:0.02em;">Latest Message:</span>
        <span style="font-style:italic;">"${escapeHtml(mail.latest_message_body || mail.summary)}"</span>
      </div>
      <div class="email-card-summary" style="margin-top:8px; font-size:0.85rem; color:#c4c4c4; line-height:1.45;">
        <span style="color:#8e8e93; font-size:0.7rem; font-weight:700; text-transform:uppercase; display:block; margin-bottom:2px; letter-spacing:0.02em;">Conversation Summary:</span>
        <span>${escapeHtml(mail.thread_summary || mail.summary)}</span>
      </div>
      <div class="email-card-footer" style="margin-top:10px; border-top:1px solid rgba(255,255,255,0.04); padding-top:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="display:flex; align-items:center; gap:10px; font-size:0.72rem; font-weight:600;">
          <span style="color:${getHealthColor(mail.thread_health)}; display:inline-flex; align-items:center; gap:4px;">${getHealthEmoji(mail.thread_health)} ${escapeHtml(mail.thread_health || 'Healthy')}</span>
          <span style="color:#8e8e93;">•</span>
          <span style="color:#a78bfa">Stage: ${escapeHtml(mail.conversation_stage || 'New')}</span>
          ${mail.needs_response === 1 ? `
            <span style="color:#8e8e93;">•</span>
            <span style="background:rgba(249, 115, 22, 0.12); color:#f97316; font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:4px; border:1px solid rgba(249, 115, 22, 0.2); display:inline-flex; align-items:center; gap:3px;">🟠 Response Required</span>
          ` : ''}
        </div>
        <div style="display:flex; align-items:center;">
          <span style="font-size:0.65rem; font-weight:600; color:#8e8e93; background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px; border:1px solid rgba(255,255,255,0.02);">${(mail.confidence_score || 100.0).toFixed(1)}% confidence</span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

window.manualRefreshEmailDashboard = async function () {
  const btn = document.getElementById('email-refresh-btn');
  if (btn) {
    btn.style.pointerEvents = 'none';
    btn.style.animation = 'spin 0.8s linear infinite';
    if (!document.getElementById('spin-keyframe')) {
      const style = document.createElement('style');
      style.id = 'spin-keyframe';
      style.textContent = '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }';
      document.head.appendChild(style);
    }
  }
  try {
    await refreshEmailDashboard();
  } finally {
    if (btn) {
      btn.style.animation = '';
      btn.style.pointerEvents = '';
    }
  }
};

window.openDisconnectConfirm = function () {
  document.getElementById('email-disconnect-modal').style.display = 'flex';
};

window.closeDisconnectConfirm = function () {
  document.getElementById('email-disconnect-modal').style.display = 'none';
};

window.confirmDisconnectEmail = async function () {
  hideEmailError();
  const wipeData = document.getElementById('email-wipe-data').checked;

  try {
    const res = await fetch('/api/email/disconnect', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ delete_data: wipeData })
    });
    if (!res.ok) throw new Error("Disconnect API error.");

    closeDisconnectConfirm();

    // Refresh settings view
    const settingsRes = await fetch('/api/email/settings', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const settings = await settingsRes.json();
    updateEmailModalUI(settings);
  } catch (err) {
    console.error(err);
    showEmailError("Error disconnecting email intelligence: " + err.message);
  }
};

window.openEmailDetailModal = function (msgId) {
  if (!emailDashboardData || !emailDashboardData.digest) return;

  // Search for the email object matching msgId across all priority lists
  let targetMail = null;
  const categories = ["Critical", "High", "Medium", "Low"];
  for (const cat of categories) {
    const list = emailDashboardData.digest[cat] || [];
    targetMail = list.find(m => m.gmail_message_id === msgId);
    if (targetMail) break;
  }

  if (!targetMail) return;

  // Mark the email as read if it needs response to clear notification badges instantly
  if (targetMail.needs_response === 1) {
    fetch('/api/email/mark-read', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ gmail_message_id: msgId })
    }).catch(err => console.error("Error marking email as read:", err));
  }

  // Populate detail modal elements
  const priorityBadge = document.getElementById('detail-priority-badge');
  priorityBadge.innerText = targetMail.priority;
  // Apply visual colors for priority levels
  priorityBadge.className = 'email-sidebar-count';
  if (targetMail.priority === 'Critical') {
    priorityBadge.style.background = '#ef4444';
    priorityBadge.style.color = 'white';
  } else if (targetMail.priority === 'High') {
    priorityBadge.style.background = '#f97316';
    priorityBadge.style.color = 'white';
  } else if (targetMail.priority === 'Medium') {
    priorityBadge.style.background = '#fbbf24';
    priorityBadge.style.color = '#171717';
  } else {
    priorityBadge.style.background = '#6b7280';
    priorityBadge.style.color = 'white';
  }

  document.getElementById('detail-subject').innerText = targetMail.subject || '(No Subject)';

  const senderVal = targetMail.original_sender || targetMail.sender || 'unknown';
  document.getElementById('detail-sender').innerText = senderVal;

  // Set first character of sender as avatar initials
  const initial = senderVal.replace(/[^a-zA-Z]/g, '').substring(0, 1).toUpperCase() || '✉️';
  document.getElementById('detail-sender-avatar').innerText = initial;

  // Format Date
  let formattedDate = 'Just now';
  if (targetMail.last_activity_at || targetMail.received_at) {
    try {
      const d = new Date(targetMail.last_activity_at || targetMail.received_at);
      formattedDate = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch (e) { }
  }
  document.getElementById('detail-time').innerText = formattedDate;

  const msgCount = targetMail.gmail_message_count || 1;
  document.getElementById('detail-duration').innerText = `${msgCount} message${msgCount > 1 ? 's' : ''}`;

  // Render thread summary & latest message preview blockquote
  document.getElementById('detail-summary').innerHTML = `
    <div style="margin-bottom: 12px; line-height: 1.5;">
      ${escapeHtml(targetMail.thread_summary || targetMail.summary || 'No summary generated.')}
    </div>
    
    <div style="font-size: 0.72rem; color: #8e8e93; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.05em; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px; display: flex; justify-content: space-between; align-items: center;">
      <span>Latest Message (From ${escapeHtml(targetMail.latest_message_sender || senderVal)})</span>
      <span style="font-size: 0.62rem; background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 4px;">${escapeHtml(targetMail.last_sender_type || 'Customer')}</span>
    </div>
    <blockquote style="margin: 0; padding: 10px 14px; background: rgba(255,255,255,0.02); border-left: 3px solid #a78bfa; font-style: italic; font-size: 0.85rem; color: #b4b4b4; border-radius: 0 6px 6px 0; max-height: 150px; overflow-y: auto;">
      "${escapeHtml(targetMail.latest_message_body || targetMail.original_body || '')}"
    </blockquote>
  `;

  // Suggested Action & Thread Metadata rendering inside detail-reason
  const reasonEl = document.getElementById('detail-reason');
  if (reasonEl) {
    reasonEl.innerHTML = `
      <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; font-size: 0.75rem; font-weight: 600; align-items: center;">
        <span style="color: ${getStatusColor(targetMail.status)}">Status: ${escapeHtml(targetMail.status || 'Open')}</span>
        <span style="color: #8e8e93;">|</span>
        <span style="color: ${getHealthColor(targetMail.thread_health)}; display:inline-flex; align-items:center; gap:4px;">${getHealthEmoji(targetMail.thread_health)} ${escapeHtml(targetMail.thread_health || 'Healthy')}</span>
        <span style="color: #8e8e93;">|</span>
        <span>Stage: ${escapeHtml(targetMail.conversation_stage || 'New')}</span>
        ${targetMail.needs_response === 1 ? `
          <span style="color: #8e8e93;">|</span>
          <span style="color: #f97316; font-weight: 700; background: rgba(249,115,22,0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(249,115,22,0.2); display:inline-flex; align-items:center; gap:3px;">🟠 Response Required</span>
        ` : ''}
      </div>
      <div style="border-top: 1px dashed rgba(167, 139, 250, 0.2); padding-top: 8px; font-size: 0.85rem; color: #e3e3e3;">
        <strong>Suggested Action [${escapeHtml(targetMail.suggested_action_type || 'Monitor')}]:</strong> 
        ${escapeHtml(targetMail.suggested_action || 'Standard review.')}
      </div>
    `;
  }

  // Stars builder with Confidence Score
  let starHtml = '';
  for (let i = 0; i < 5; i++) {
    starHtml += i < targetMail.stars ? '★' : '☆';
  }
  const starContainer = document.getElementById('detail-stars');
  if (starContainer) {
    starContainer.innerHTML = `
      <span style="font-size:0.65rem; font-weight:600; color:#8e8e93; background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px; border:1px solid rgba(255,255,255,0.02); margin-right:8px;">${(targetMail.confidence_score || 100.0).toFixed(1)}% confidence</span>
      ${starHtml}
    `;
  }

  // Open the detail modal overlay
  document.getElementById('email-detail-modal').style.display = 'flex';
};

window.closeEmailDetailModal = function () {
  document.getElementById('email-detail-modal').style.display = 'none';
};

// --- WebSocket Realtime Inbox & Notification Sync ---
let notificationWs = null;

function initNotificationWebSocket() {
  // Guard: skip if a connection is already open or being established
  if (notificationWs && (notificationWs.readyState === WebSocket.OPEN || notificationWs.readyState === WebSocket.CONNECTING)) {
    console.log("ℹ️ [WS] Connection already active, skipping duplicate init.");
    return;
  }

  // Grab the global token from script.js scope
  if (typeof token === 'undefined' || !token || (typeof isGuest !== 'undefined' && isGuest)) {
    console.log("ℹ️ [WS Info] User is guest or token is missing. Skipping WebSocket connection.");
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/ws`;

  console.log("🔌 [WS Connecting] to " + wsUrl);
  notificationWs = new WebSocket(wsUrl);

  notificationWs.onopen = () => {
    console.log("🟢 [WS Connected] Authenticating...");
    notificationWs.send(JSON.stringify({
      action: "auth",
      token: token
    }));
  };

  notificationWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log("📡 [WS Message Received]", data);

      if (data.event === "unread_count" || data.event === "dashboard_updated") {
        const count = data.count || 0;
        updateNotificationBadges(count);

        // If the email intelligence modal is open and we got a dashboard_updated event, refresh it
        if (data.event === "dashboard_updated") {
          const emailModal = document.getElementById('email-intelligence-modal');
          if (emailModal && emailModal.style.display === 'flex') {
            console.log("🔄 Real-time dashboard update triggered via WebSocket...");
            refreshEmailDashboard();
          }
        }
      }
    } catch (e) {
      console.error("Error parsing WS message:", e);
    }
  };

  notificationWs.onerror = (err) => {
    console.error("⚠️ [WS Error]", err);
  };

  notificationWs.onclose = () => {
    console.log("🔴 [WS Closed] Reconnecting in 5 seconds...");
    notificationWs = null; // Clear reference so the guard check works correctly
    setTimeout(initNotificationWebSocket, 5000);
  };
}

function updateNotificationBadges(count) {
  // Update footer settings badge
  const footerBadge = document.getElementById('settings-badge');
  if (footerBadge) {
    if (count > 0) {
      footerBadge.innerText = count;
      footerBadge.style.display = 'flex';
    } else {
      footerBadge.style.display = 'none';
    }
  }

  // Update header settings badge
  const headerBadge = document.getElementById('settings-badge-header');
  if (headerBadge) {
    if (count > 0) {
      headerBadge.innerText = count;
      headerBadge.style.display = 'flex';
    } else {
      headerBadge.style.display = 'none';
    }
  }

  // Update dropdown popover badge
  const dropdownBadge = document.getElementById('dropdown-email-badge');
  if (dropdownBadge) {
    if (count > 0) {
      dropdownBadge.innerText = count;
      dropdownBadge.style.display = 'inline-block';
    } else {
      dropdownBadge.style.display = 'none';
    }
  }
}

// Call initNotificationWebSocket on document ready
document.addEventListener("DOMContentLoaded", () => {
  // Wait a small bit to ensure script.js variables like 'token' are fully populated
  setTimeout(initNotificationWebSocket, 1000);
});
