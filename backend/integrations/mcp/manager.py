# manager.py

import logging
from typing import List, Dict, Any
from .registry import load_mcp_servers_config
from .connection import ConnectionPool
from .client import MCPClient
from .converter import convert_mcp_tools_to_langchain

logger = logging.getLogger(__name__)

class MCPManager:
    def __init__(self):
        self.pool = ConnectionPool()
        self._converted_tools = []

    async def start_all_servers(self):
        """Discovers, spawns, and registers all MCP servers defined in mcp_servers.json."""
        configs = load_mcp_servers_config()
        if not configs:
            logger.info("🔌  MCP              │ No servers configured")
            return

        # Override filesystem allowed directory with active user workspace from SQLite
        if "filesystem" in configs:
            from backend.database.chat_database import DB_PATH
            import sqlite3
            conn = sqlite3.connect(DB_PATH, timeout=15.0)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT path FROM user_workspaces WHERE is_active = 1 LIMIT 1")
                row = cursor.fetchone()
                if row:
                    configs["filesystem"].args[-1] = row[0]
            except Exception as dbe:
                logger.warning("⚠️  MCP filesystem   │ Could not load workspace path: %s", dbe)
            finally:
                conn.close()

        import asyncio
        start_tasks = []
        for name, config in configs.items():
            client = MCPClient(name, config)
            self.pool.register_client(name, client)
            
            async def connect_and_init(n=name, c=client):
                try:
                    await c.connect()
                    await c.initialize()
                except Exception as ex:
                    logger.error("❌  MCP %-12s │ Failed to start: %s", n, ex)
                    self.pool.remove_client(n)
                    
            start_tasks.append(connect_and_init())
            
        if start_tasks:
            await asyncio.gather(*start_tasks)
            await self._reload_tools()

    async def restart_server(self, name: str, new_args: List[str] = None):
        """Restarts a specific MCP server process with updated execution arguments."""
        client = self.pool.get_client(name)
        if not client:
            logger.warning("[MCP Manager Warning] Server '%s' is not registered. Cannot restart.", name)
            return
            
        logger.info("[MCP Manager] Restarting server '%s' with updated configurations...", name)
        
        # 1. Disconnect the client
        await client.disconnect()
        
        # 2. Update config parameters
        if new_args is not None:
            client.config.args = new_args
            
        # 3. Reconnect and handshake
        try:
            await client.connect()
            await client.initialize()
        except Exception as e:
            logger.error("[MCP Manager Error] Failed to restart server '%s': %s", name, e)
            self.pool.remove_client(name)
            
        # 4. Reload tool bindings
        await self._reload_tools()

    async def _reload_tools(self):
        """Pulls raw tool lists from all active servers and wraps them into LangChain tools."""
        self._converted_tools.clear()
        
        clients = self.pool.list_clients()
        for name, client in clients.items():
            try:
                raw_tools = await client.list_tools()
                logger.info("[MCP Manager] Discovered %d tools on server '%s'", len(raw_tools), name)
                
                langchain_tools = convert_mcp_tools_to_langchain(client, raw_tools)
                self._converted_tools.extend(langchain_tools)
            except Exception as e:
                logger.error("[MCP Manager Error] Failed to load tools from '%s': %s", name, e)

    def get_tools(self) -> list:
        """Returns the compiled list of active LangChain-wrapped MCP tools."""
        return self._converted_tools

    async def stop_all_servers(self):
        """Cleanly disconnects and shuts down all spawned MCP subprocesses."""
        await self.pool.disconnect_all()
        self._converted_tools.clear()

# Global single instance representing the system's process registry manager
mcp_manager = MCPManager()
