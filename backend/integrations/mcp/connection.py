# connection.py

import logging
from typing import Dict
from .client import MCPClient

logger = logging.getLogger(__name__)

class ConnectionPool:
    def __init__(self):
        self._connections: Dict[str, MCPClient] = {}

    def register_client(self, name: str, client: MCPClient):
        self._connections[name] = client

    def get_client(self, name: str) -> MCPClient:
        return self._connections.get(name)

    def remove_client(self, name: str) -> MCPClient:
        return self._connections.pop(name, None)

    def list_clients(self) -> Dict[str, MCPClient]:
        return self._connections

    async def disconnect_all(self):
        """Cleanly disconnects all active client sessions in parallel."""
        import asyncio
        if not self._connections:
            return
            
        logger.info("[MCP Connection Pool] Shutting down all active sessions...")
        clients = list(self._connections.values())
        await asyncio.gather(*[client.disconnect() for client in clients], return_exceptions=True)
        self._connections.clear()
