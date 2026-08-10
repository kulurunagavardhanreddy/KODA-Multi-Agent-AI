// frontend/js/ui/styles_inject.js

// --- KODA Dynamic Styles Injector ---
// Injects runtime CSS for agent execution steps and the sources panel.
// Kept separate so styles can be updated without touching index.html or style.css.

const agentStyles = document.createElement('style');
agentStyles.innerHTML = `
  .agent-execution-block { margin-bottom: 10px; font-size: 0.9rem; }
  .agent-step { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; color: #555; }
  .light-mode .agent-step { color: #888; }
  .agent-step-running { display: inline-flex; align-items: center; gap: 8px; animation: pulse 1.5s infinite; background: rgba(128,128,128,0.05); border: 1px solid rgba(255,255,255,0.08); padding: 6px 14px; border-radius: 20px; color: #b4b4b4;}
  .agent-step-success { display: inline-flex; align-items: center; gap: 8px; color: #10a37f; border: 1px solid rgba(16,163,127,0.2); background: rgba(16,163,127,0.05); padding: 6px 14px; border-radius: 20px;}
  .agent-step-failed { display: inline-flex; align-items: center; gap: 8px; color: #ff4a4a; border: 1px solid rgba(255,74,74,0.2); background: rgba(255,74,74,0.05); padding: 6px 14px; border-radius: 20px;}

  .agent-step:has(.agent-step-success) .agent-step-running,
  .agent-step:has(.agent-step-failed) .agent-step-running { display: none; }

  .agent-execution-block:has(.agent-execution-done) { display: none !important; }
  .agent-steps-wrapper .agent-step:not(:last-child) { display: none; }
  .agent-summary { background: rgba(58,123,213,0.1); color: #3a7bd5; border: 1px solid rgba(58,123,213,0.3); padding: 6px 12px; border-radius: 16px; cursor: pointer; transition: all 0.2s; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 6px;}
  .agent-summary:hover { background: rgba(58,123,213,0.2); }

  @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }

  .sources-panel {
    position: fixed; top: 0; right: -350px; width: 300px; height: 100vh;
    background-color: #1e1e1e; color: #ececec;
    box-shadow: -4px 0 15px rgba(0,0,0,0.5); z-index: 9999;
    transition: right 0.3s ease; padding: 20px; overflow-y: auto;
    border-left: 1px solid rgba(255,255,255,0.1);
  }
  body.light-mode .sources-panel {
    background-color: #ffffff; color: #333333;
    box-shadow: -4px 0 15px rgba(0,0,0,0.1);
    border-left: 1px solid rgba(0,0,0,0.1);
  }
  .sources-panel.open { right: 0 !important; }
  .sources-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(128,128,128,0.2); padding-bottom: 10px; margin-bottom: 15px; }
  .sources-header h3 { margin: 0; font-size: 1.1rem; display: flex; align-items: center; gap: 6px;}
  .close-sources-btn { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: inherit; }
  .sources-list { display: flex; flex-direction: column; gap: 10px; }
  .source-item { padding: 10px; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; text-decoration: none; color: inherit; display: flex; align-items: center; gap: 10px; transition: background 0.2s; word-break: break-all; }
  .source-item:hover { background: rgba(128,128,128,0.05); }
  .source-icon { font-size: 1.2rem; }
  .source-info { display: flex; flex-direction: column; }
  .source-domain { font-weight: bold; margin-bottom: 4px; color: #3a7bd5; }
  .source-url { font-size: 0.85rem; opacity: 0.8; }
`;
document.head.appendChild(agentStyles);
