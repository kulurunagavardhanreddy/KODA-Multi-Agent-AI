// --- KODA Workspace Management UI Module ---

window.openWorkspaceModal = function () {
  const modal = document.getElementById('workspace-modal');
  if (modal) {
    modal.style.display = 'flex';
    loadWorkspacesList();
  }
};

window.closeWorkspaceModal = function () {
  const modal = document.getElementById('workspace-modal');
  if (modal) modal.style.display = 'none';
};

async function loadWorkspacesList() {
  const activeNameSpan = document.getElementById('active-workspace-name');
  const activeDot = document.getElementById('workspace-indicator-dot');
  const modalList = document.getElementById('workspace-list-container');
  if (!activeNameSpan || !modalList) return;

  try {
    const res = await fetch('/api/workspaces', {
      headers: { "Authorization": `Bearer ${token}` }
    });
    const data = await res.json();
    const workspaces = data.workspaces || [];

    // 1. Update active workspace name and indicator dot
    let activePath = "uploads";
    let activeDisplayName = "uploads/ (Sandbox)";
    let hasCustomActive = false;

    workspaces.forEach(ws => {
      if (ws.is_active) {
        activePath = ws.path;
        const folderName = ws.path.split(/[/\\]/).pop() || ws.path;
        activeDisplayName = `${folderName}/ (${ws.path})`;
        hasCustomActive = true;
      }
    });

    activeNameSpan.innerText = activeDisplayName;
    activeNameSpan.title = activePath;
    if (activeDot) {
      if (hasCustomActive) {
        activeDot.classList.add('active');
      } else {
        activeDot.classList.remove('active');
      }
    }

    // 2. Populate modal management list
    modalList.innerHTML = '';

    // Append default Sandbox item in list
    const defaultItem = document.createElement('div');
    defaultItem.style.display = 'flex';
    defaultItem.style.justifyContent = 'space-between';
    defaultItem.style.alignItems = 'center';
    defaultItem.style.padding = '8px';
    defaultItem.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
    defaultItem.style.cursor = 'pointer';
    if (!hasCustomActive) {
      defaultItem.style.background = 'rgba(16, 163, 127, 0.1)';
      defaultItem.style.borderRadius = '4px';
    }

    const defaultSpan = document.createElement('span');
    defaultSpan.style.wordBreak = 'break-all';
    defaultSpan.style.color = !hasCustomActive ? '#10a37f' : '#fff';
    defaultSpan.innerText = !hasCustomActive ? `✓ Default Sandbox (uploads/)` : `Default Sandbox (uploads/)`;
    defaultSpan.style.flex = '1';
    defaultSpan.onclick = () => handleWorkspaceSelectionChange('uploads');

    defaultItem.appendChild(defaultSpan);
    modalList.appendChild(defaultItem);

    workspaces.forEach(ws => {
      const item = document.createElement('div');
      item.style.display = 'flex';
      item.style.justifyContent = 'space-between';
      item.style.alignItems = 'center';
      item.style.padding = '8px';
      item.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
      if (ws.is_active) {
        item.style.background = 'rgba(16, 163, 127, 0.1)';
        item.style.borderRadius = '4px';
      }

      const pathSpan = document.createElement('span');
      pathSpan.style.wordBreak = 'break-all';
      pathSpan.style.marginRight = '8px';
      pathSpan.style.color = ws.is_active ? '#10a37f' : '#fff';
      pathSpan.innerText = ws.is_active ? `✓ ${ws.path}` : ws.path;
      pathSpan.style.flex = '1';
      pathSpan.style.cursor = 'pointer';
      pathSpan.onclick = () => handleWorkspaceSelectionChange(ws.path);

      const deleteBtn = document.createElement('button');
      deleteBtn.innerText = '🗑️';
      deleteBtn.style.background = 'none';
      deleteBtn.style.border = 'none';
      deleteBtn.style.cursor = 'pointer';
      deleteBtn.onclick = (e) => {
        e.stopPropagation();
        deleteWorkspace(ws.path);
      };

      item.appendChild(pathSpan);
      item.appendChild(deleteBtn);
      modalList.appendChild(item);
    });
  } catch (err) {
    console.error("Failed to load workspaces list: ", err);
  }
}

window.triggerNativeFolderPicker = async function () {
  try {
    const res = await fetch('/api/utils/select-directory', {
      method: 'POST',
      headers: { "Authorization": `Bearer ${token}` }
    });
    const data = await res.json();
    if (data.path) {
      await addWorkspacePath(data.path);
    } else if (data.message) {
      alert(data.message);
    }
  } catch (err) {
    console.error("Native folder selection error: ", err);
    alert("Folder selector is not supported in this server environment. Please enter path manually.");
  }
};

window.addManualWorkspace = async function () {
  const input = document.getElementById('manual-workspace-path');
  if (!input) return;
  const path = input.value.trim();
  if (!path) return;

  await addWorkspacePath(path);
  input.value = '';
};

async function addWorkspacePath(path) {
  try {
    const res = await fetch('/api/workspaces', {
      method: 'POST',
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ path: path })
    });
    if (res.status === 200) {
      await handleWorkspaceSelectionChange(path);
    } else {
      const errorData = await res.json();
      alert(errorData.detail || "Failed to add project workspace.");
    }
  } catch (err) {
    console.error("Add workspace error: ", err);
  }
}

async function deleteWorkspace(path) {
  try {
    const res = await fetch(`/api/workspaces?path=${encodeURIComponent(path)}`, {
      method: 'DELETE',
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (res.status === 200) {
      loadWorkspacesList();
    }
  } catch (err) {
    console.error("Delete workspace error: ", err);
  }
}

window.handleWorkspaceSelectionChange = async function (path) {
  try {
    const res = await fetch('/api/workspaces/activate', {
      method: 'POST',
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ path: path })
    });
    if (res.status === 200) {
      loadWorkspacesList();
      console.log(`Active project workspace successfully switched to: ${path}`);
    } else {
      const errorData = await res.json();
      alert(errorData.detail || "Failed to activate workspace.");
    }
  } catch (err) {
    console.error("Activate workspace error: ", err);
  }
};

// Auto-load workspaces dropdown on page startup
setTimeout(() => {
  if (window.token) {
    loadWorkspacesList();
  }
}, 1000);
