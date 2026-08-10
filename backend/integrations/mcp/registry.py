# registry.py

import os
import json
import logging
from typing import Dict
from .schemas import ServerConfig

logger = logging.getLogger(__name__)

def load_mcp_servers_config() -> Dict[str, ServerConfig]:
    """Loads and validates the mcp_servers.json configuration file from the project root."""
    config_dir = os.path.dirname(os.path.abspath(__file__))
    integrations_dir = os.path.dirname(config_dir)
    backend_dir = os.path.dirname(integrations_dir)
    root_dir = os.path.dirname(backend_dir)
    
    config_path = os.path.join(root_dir, "mcp_servers.json")
    if not os.path.exists(config_path):
        logger.info("ℹ️ [MCP Registry] mcp_servers.json configuration not found at: %s", config_path)
        return {}
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        mcp_servers = data.get("mcpServers", {})
        validated_configs = {}
        for name, config_dict in mcp_servers.items():
            try:
                validated_configs[name] = ServerConfig(**config_dict)
            except Exception as ve:
                logger.error("⚠️ [MCP Registry] Invalid server config for '%s': %s", name, ve)
                
        return validated_configs
    except Exception as e:
        logger.error("⚠️ [MCP Registry] Failed to read or parse mcp_servers.json: %s", e)
        return {}
