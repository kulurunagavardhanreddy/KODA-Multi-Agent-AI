import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import asyncio
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)

async def test_connection():
    from backend.integrations.mcp import mcp_manager
    
    print("\n[MCP Test] Starting MCP connection test...")
    await mcp_manager.start_all_servers()
    
    print("\n[MCP Test] Active tools loaded in KODA:")
    tools = mcp_manager.get_tools()
    for t in tools:
        print(f"   * {t.name}: {t.description}")
        
    print("\n[MCP Test] Shutting down MCP servers...")
    await mcp_manager.stop_all_servers()
    print("[MCP Test] Connection test completed.\n")

if __name__ == "__main__":
    asyncio.run(test_connection())
