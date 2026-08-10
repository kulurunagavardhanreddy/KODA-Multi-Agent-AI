# exceptions.py

class MCPError(Exception):
    """Base exception for all MCP-related errors."""
    pass

class MCPConnectionError(MCPError):
    """Raised when connecting or writing/reading from an MCP server subprocess fails."""
    pass

class MCPValidationError(MCPError):
    """Raised when JSON-RPC messaging format violates protocol specifications."""
    pass

class MCPExecutionException(MCPError):
    """Raised when an MCP tool execution fails on the server side."""
    pass
