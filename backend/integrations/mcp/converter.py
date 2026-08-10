# converter.py

import logging
from typing import List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import Field
from .client import MCPClient

logger = logging.getLogger(__name__)

class MCPDynamicTool(BaseTool):
    """Custom dynamic wrapper exposing an MCP tool to LangChain agents."""
    client: MCPClient = Field(exclude=True)
    mcp_name: str
    
    def __init__(self, client: MCPClient, mcp_name: str, name: str, description: str, args_schema: Any = None):
        super().__init__(
            client=client,
            mcp_name=mcp_name,
            name=name,
            description=description,
            args_schema=args_schema
        )

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """Synchronous run fallback (calls the async run helper synchronously)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(*args, **kwargs))

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Asynchronous execution mapping arguments to JSON-RPC stdin/stdout streams."""
        try:
            # Remove None values so optional parameters are not passed as null
            clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            # MCP tools expect dictionary keyword args
            logger.info("[MCP Tool] Invoking '%s' on server '%s' with args: %s", self.mcp_name, self.client.name, clean_kwargs)
            res = await self.client.call_tool(self.mcp_name, clean_kwargs)
            return res
        except Exception as e:
            logger.error("[MCP Tool Error] Failed to execute '%s': %s", self.mcp_name, e)
            return f"Error executing tool '{self.name}': {e}"

def convert_mcp_tools_to_langchain(client: MCPClient, raw_tools: List[Dict[str, Any]]) -> List[BaseTool]:
    """Converts raw list of MCP tool definitions to LangChain-compatible BaseTool instances."""
    converted_tools = []
    
    for tool_dict in raw_tools:
        name = tool_dict.get("name")
        description = tool_dict.get("description", "")
        input_schema = tool_dict.get("inputSchema", {})
        
        if not name:
            continue
            
        # Standardize name for LangChain compatibility (must be alphanumeric or underscores/hyphens)
        clean_name = f"mcp_{client.name}_{name}"
        clean_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in clean_name)
        
        # We can dynamically construct a Pydantic schema model for args validation
        from pydantic import create_model
        
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        fields = {}
        for prop_name, prop_info in properties.items():
            prop_type = Any
            p_type = prop_info.get("type")
            if p_type == "string":
                prop_type = str
            elif p_type == "integer":
                prop_type = int
            elif p_type == "number":
                prop_type = float
            elif p_type == "boolean":
                prop_type = bool
            elif p_type == "array":
                prop_type = list
            elif p_type == "object":
                prop_type = dict
                
            default_val = ... if prop_name in required else None
            fields[prop_name] = (prop_type, Field(default=default_val, description=prop_info.get("description", "")))
            
        schema_model = None
        if fields:
            try:
                schema_model = create_model(f"{clean_name}_schema", **fields)
            except Exception as se:
                logger.warning("⚠️ [MCP Converter] Failed to generate dynamic argument schema for '%s': %s", name, se)
                
        # Expose the tool wrapper
        mcp_tool = MCPDynamicTool(
            client=client,
            mcp_name=name,
            name=clean_name,
            description=f"[MCP Server: {client.name}] {description}",
            args_schema=schema_model
        )
        converted_tools.append(mcp_tool)
        
    return converted_tools
