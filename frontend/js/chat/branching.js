// --- KODA Branching Memory & History Rebuilder UI Module ---

window.getDropTarget = function () {
  const activeBranches = Array.from(document.querySelectorAll('.branch-content.active'));
  if (activeBranches.length > 0) {
    return activeBranches[activeBranches.length - 1]; // Insert into the deepest active branch!
  }
  return document.getElementById('chatbox');
};

window.rebuildChatHistory = function () {
  chatHistory = [];
  const allMessages = document.querySelectorAll('.message');

  allMessages.forEach(msg => {
    let isVisible = true;
    let parent = msg.parentElement;
    while (parent && parent.id !== 'chatbox') {
      if (parent.classList.contains('branch-content') && !parent.classList.contains('active')) {
        isVisible = false; break;
      }
      parent = parent.parentElement;
    }

    if (isVisible) {
      const role = msg.getAttribute('data-role') || (msg.classList.contains('user') ? 'user' : 'assistant');
      let raw = msg.getAttribute('data-raw');

      if (!raw) {
        const textBody = msg.querySelector('.text-body');
        raw = encodeURIComponent(textBody ? (textBody.innerText || textBody.textContent) : "");
        msg.setAttribute('data-role', role); msg.setAttribute('data-raw', raw);
      }

      const sys = msg.getAttribute('data-system');
      if (sys) chatHistory.push({ role: 'system', content: decodeURIComponent(sys) });
      chatHistory.push({ id: msg.id, role: role, content: decodeURIComponent(raw) });
    }
  });
};

window.createBranch = function (startElement, newText, isRegenerate = false) {
  let container; let totalBranches = 0;

  if (startElement.parentElement.classList.contains('branch-content') && startElement.parentElement.firstElementChild === startElement) {
    container = startElement.parentElement.parentElement;
    container.querySelectorAll(':scope > .branch-content.active').forEach(b => b.classList.remove('active'));
    totalBranches = container.querySelectorAll(':scope > .branch-content').length;
  } else {
    container = document.createElement('div'); container.className = 'branch-container';
    container.id = 'branch-' + Date.now();

    const branch1 = document.createElement('div'); branch1.className = 'branch-content'; branch1.dataset.branch = '1';
    startElement.parentNode.insertBefore(container, startElement);

    let sibling = startElement;
    while (sibling) {
      let next = sibling.nextElementSibling; branch1.appendChild(sibling); sibling = next;
    }

    container.appendChild(branch1);
  }

  totalBranches = container.querySelectorAll(':scope > .branch-content').length + 1;
  const newBranch = document.createElement('div'); newBranch.className = 'branch-content active'; newBranch.dataset.branch = totalBranches.toString();
  container.appendChild(newBranch);

  updateBranchControls(container);

  rebuildChatHistory();

  if (isRegenerate) {
    sendMessage(null, true);
  } else {
    document.getElementById('input').value = newText;
    sendMessage();
  }
};

window.updateBranchControls = function (container) {
  if (!container) return;
  const branches = container.querySelectorAll(':scope > .branch-content');
  const total = branches.length;
  branches.forEach((branch, index) => {
    const current = index + 1;
    const firstMsg = branch.querySelector('.message');
    if (!firstMsg) return;

    const actions = firstMsg.querySelector('.message-actions');
    if (!actions) return;

    let controls = actions.querySelector('.branch-controls');
    if (controls) controls.remove();

    if (total > 1) {
      controls = document.createElement('div');
      controls.className = 'branch-controls';
      controls.innerHTML = `<button class="branch-btn" onclick="switchBranch('${container.id}', -1)" ${current === 1 ? 'disabled' : ''}>❮</button><span class="branch-label" data-total="${total}" data-current="${current}">${current} / ${total}</span><button class="branch-btn" onclick="switchBranch('${container.id}', 1)" ${current === total ? 'disabled' : ''}>❯</button>`;
      actions.insertBefore(controls, actions.firstChild);
    }
  });
};

window.switchBranch = function (containerId, direction) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const activeBranch = container.querySelector(':scope > .branch-content.active');
  let current = parseInt(activeBranch.dataset.branch);
  const total = container.querySelectorAll(':scope > .branch-content').length;
  let next = current + direction; if (next < 1 || next > total) return;

  activeBranch.classList.remove('active');
  container.querySelector(`:scope > .branch-content[data-branch="${next}"]`).classList.add('active');

  rebuildChatHistory();
  saveCurrentSession();
};
