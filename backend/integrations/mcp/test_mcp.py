# test_mcp.py

import pytest
import os
import json
from backend.integrations.mcp.schemas import ServerConfig
from backend.integrations.mcp.registry import load_mcp_servers_config
from backend.integrations.mcp.client import MCPClient
from backend.integrations.mcp.converter import convert_mcp_tools_to_langchain

def test_mcp_registry(tmp_path, monkeypatch):
    """Verifies that the registry reads and parses config files correctly."""
    # Write a temporary mcp_servers.json file
    temp_config = tmp_path / "mcp_servers.json"
    config_data = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "uploads"]
            }
        }
    }
    temp_config.write_text(json.dumps(config_data))
    
    # Mock path check to retrieve our temp file
    monkeypatch.setattr("backend.integrations.mcp.registry.os.path.exists", lambda path: True if "mcp_servers.json" in path else False)
    
    original_open = open
    def mock_open(file, *args, **kwargs):
        if "mcp_servers.json" in str(file):
            return original_open(temp_config, *args, **kwargs)
        return original_open(file, *args, **kwargs)
        
    monkeypatch.setattr("builtins.open", mock_open)
    
    configs = load_mcp_servers_config()
    assert "filesystem" in configs
    assert configs["filesystem"].command == "npx"
    assert "uploads" in configs["filesystem"].args

def test_tool_conversion():
    """Verifies that raw MCP tools are dynamically mapped to LangChain BaseTool models with correct schemas."""
    # Mock client and config
    config = ServerConfig(command="python")
    client = MCPClient("mock_server", config)
    
    raw_tools = [
        {
            "name": "read_notes",
            "description": "Reads local notes file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to target file"
                    }
                },
                "required": ["path"]
            }
        }
    ]
    
    langchain_tools = convert_mcp_tools_to_langchain(client, raw_tools)
    assert len(langchain_tools) == 1
    
    tool = langchain_tools[0]
    assert tool.name == "mcp_mock_server_read_notes"
    assert "[MCP Server: mock_server]" in tool.description
    assert tool.args_schema is not None
    assert "path" in tool.args_schema.model_fields
