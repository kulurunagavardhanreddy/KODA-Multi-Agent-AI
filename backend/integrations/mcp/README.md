# MCP Integration Layer: Technical Reference

This integration module implements a standard **MCP (Model Context Protocol) Client** inside KODA, allowing the supervisor agent to dynamically discover and execute tools exposed by external MCP servers over Stdio transports.

---

## 🛠️ How to Add a New MCP Server

To add a new server, simply configure its command and args inside [mcp_servers.json](../../../mcp_servers.json) located at the workspace root:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uv",
      "args": ["run", "mcp-server-sqlite", "--db-path", "chat_history.db"]
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    }
  }
}
```

When KODA boots up:
1. The `mcp_manager` spawns the server as a background subprocess.
2. Performs the initialize/initialized handshake.
3. Retrieves the list of available tools.
4. Dynamically wraps them into LangChain-compatible `BaseTool` models and injects them into the supervisor's active registry.

---

## 🧭 Troubleshooting Connections & Subprocesses

If KODA fails to spawn a server, verify the following:

1. **Path Configurations:** Ensure the `command` (like `npx` or `python`) is globally available in your environment path.
2. **Standard Output Pollution:** MCP servers must strictly use standard output (`stdout`) **only** for JSON-RPC message payloads. If the server prints raw text or debug prints directly to `stdout`, the JSON parser will fail. Redirect any standard logs to standard error (`stderr`) instead.
3. **Subprocess Lifetimes:** KODA terminates all background subprocesses cleanly on server shutdown. If a process does not exit within 1.5 seconds, KODA issues a `SIGKILL` to prevent leaving zombie processes.
