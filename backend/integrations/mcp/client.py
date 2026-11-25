# client.py

import os
import json
import asyncio
import logging
import subprocess
import threading
import shutil
from typing import Dict, List, Any, Optional
from .exceptions import MCPConnectionError, MCPExecutionException
from .schemas import ServerConfig, JSONRPCRequest, JSONRPCResponse

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, name: str, config: ServerConfig):
        self.name = name
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._recent_stderr: List[str] = []
        self._request_counter = 0

    async def connect(self):
        """Spawns the MCP server subprocess and connects stdio streams using subprocess.Popen."""
        try:
            logger.debug("[MCP] Spawning '%s': %s %s", self.name, self.config.command, " ".join(self.config.args))
            
            # Setup environment variables if provided
            env = None
            if self.config.env:
                env = {**os.environ, **self.config.env}

            executable = shutil.which(self.config.command)
            if not executable:
                raise FileNotFoundError(f"Command '{self.config.command}' is not installed or not found in the system PATH.")

            # On Windows, prevent console window popups from subprocesses
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                [executable] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                startupinfo=startupinfo
            )
            
            self._loop = asyncio.get_running_loop()
            
            # Start background reader threads
            self._read_thread = threading.Thread(target=self._stdout_reader_loop, daemon=True)
            self._read_thread.start()
            
            self._stderr_thread = threading.Thread(target=self._stderr_reader_loop, daemon=True)
            self._stderr_thread.start()
            
        except Exception as e:
            raise MCPConnectionError(f"Failed to spawn MCP server '{self.name}': {e}")

    async def disconnect(self):
        """Gracefully shuts down the subprocess and cleans up reader tasks."""
        if self.process:
            try:
                self.process.terminate()
                # Wait for subprocess to exit in a separate thread to avoid blocking loop
                def wait_proc():
                    try:
                        self.process.wait(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        logger.warning("[MCP Client Warning] Server '%s' did not exit within timeout. Killing process.", self.name)
                        self.process.kill()
                await asyncio.to_thread(wait_proc)
            except Exception as e:
                logger.error("[MCP Client Error] Error disconnecting server '%s': %s", self.name, e)
            self.process = None

        # Resolve all remaining futures with error
        for fut in list(self._pending_requests.values()):
            if not fut.done():
                fut.set_exception(MCPConnectionError("Client disconnected."))
        self._pending_requests.clear()

    def _stdout_reader_loop(self):
        """Continuously reads standard output stream of the subprocess in a background thread."""
        try:
            while self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                self._loop.call_soon_threadsafe(self._handle_incoming_line, line)
        except Exception as e:
            logger.error("[MCP Client Error] Error in stdout reader loop for '%s': %s", self.name, e)
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._fail_pending_on_eof)

    def _fail_pending_on_eof(self):
        """Fails any pending RPC requests immediately if the server process exits early."""
        if not self._pending_requests:
            return
        exit_code = self.process.poll() if self.process else None
        stderr_tail = " | ".join(self._recent_stderr[-5:]) if self._recent_stderr else "no stderr output"
        err = MCPConnectionError(
            f"MCP server '{self.name}' closed stdout unexpectedly (exit_code={exit_code}): {stderr_tail}"
        )
        for fut in list(self._pending_requests.values()):
            if not fut.done():
                fut.set_exception(err)
        self._pending_requests.clear()

    def _stderr_reader_loop(self):
        """Continuously reads standard error stream and outputs to python logs for diagnostics."""
        try:
            while self.process and self.process.stderr:
                line = self.process.stderr.readline()
                if not line:
                    break
                msg = line.decode("utf-8", errors="replace").strip()
                if msg:
                    self._recent_stderr.append(msg)
                    if len(self._recent_stderr) > 20:
                        self._recent_stderr.pop(0)
                    logger.debug("[MCP STDERR %s] %s", self.name, msg)
        except Exception as e:
            pass

    def _handle_incoming_line(self, line: bytes):
        """Routes parsed JSON-RPC responses to pending futures."""
        line_str = line.decode("utf-8").strip()
        if not line_str:
            return
            
        try:
            data = json.loads(line_str)
            if "id" in data:
                req_id = str(data["id"])
                future = self._pending_requests.pop(req_id, None)
                if future and not future.done():
                    future.set_result(data)
        except Exception as je:
            logger.warning("[MCP Client Warning] Failed to parse stdout line from '%s': %s", self.name, je)

    async def send_rpc_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Any:
        """Sends a JSON-RPC request to the MCP server and awaits the response."""
        if not self.process or not self.process.stdin:
            raise MCPConnectionError(f"MCP server '{self.name}' is not connected.")
            
        self._request_counter += 1
        req_id = str(self._request_counter)
        
        request = JSONRPCRequest(
            method=method,
            params=params,
            id=req_id
        )
        
        future = self._loop.create_future()
        self._pending_requests[req_id] = future
        
        try:
            req_bytes = (json.dumps(request.model_dump(exclude_none=True)) + "\n").encode("utf-8")
            
            # Write to stdin in a thread pool to avoid blocking the main event loop
            def write_stdin():
                self.process.stdin.write(req_bytes)
                self.process.stdin.flush()
                
            await asyncio.to_thread(write_stdin)
        except Exception as e:
            self._pending_requests.pop(req_id, None)
            raise MCPConnectionError(f"Failed to write payload to subprocess stdin for '{self.name}': {e}")
            
        try:
            # Wait for response with configurable timeout
            response_data = await asyncio.wait_for(future, timeout=timeout)
            
            response = JSONRPCResponse(**response_data)
            if response.error:
                raise MCPExecutionException(f"MCP Server error: {response.error.get('message', 'Unknown error')}")
            return response.result
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise MCPConnectionError(f"JSON-RPC request '{method}' to '{self.name}' timed out.")
        except Exception as e:
            self._pending_requests.pop(req_id, None)
            raise e

    async def send_rpc_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Sends a JSON-RPC notification (no ID) to the MCP server without awaiting a response."""
        if not self.process or not self.process.stdin:
            raise MCPConnectionError(f"MCP server '{self.name}' is not connected.")
            
        request = JSONRPCRequest(
            jsonrpc="2.0",
            method=method,
            params=params,
            id=None
        )
        
        try:
            req_bytes = (json.dumps(request.model_dump(exclude_none=True)) + "\n").encode("utf-8")
            def write_stdin():
                self.process.stdin.write(req_bytes)
                self.process.stdin.flush()
            await asyncio.to_thread(write_stdin)
        except Exception as e:
            raise MCPConnectionError(f"Failed to write notification to subprocess stdin for '{self.name}': {e}")

    async def initialize(self):
        """Sends initialization handshake to client."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "koda-client", "version": "1.0.0"}
        }
        await self.send_rpc_request("initialize", params, timeout=45.0)
        await self.send_rpc_notification("notifications/initialized")
        logger.info("[MCP] Handshake success for '%s'!", self.name)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Queries the server for its list of available tools."""
        res = await self.send_rpc_request("tools/list")
        if isinstance(res, dict):
            return res.get("tools", [])
        return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invokes a specific tool on the server and returns the text output."""
        # Clean null parameters defensively to prevent MCP schema validation crashes
        clean_args = {k: v for k, v in arguments.items() if v is not None}
        params = {
            "name": tool_name,
            "arguments": clean_args
        }
        res = await self.send_rpc_request("tools/call", params)
        
        is_error = False
        if isinstance(res, dict):
            is_error = res.get("isError", False)
            
        if isinstance(res, dict) and "content" in res:
            content_list = res["content"]
            text_blocks = []
            for item in content_list:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_blocks.append(item.get("text", ""))
            result_str = "\n".join(text_blocks)
            if is_error:
                raise MCPExecutionException(f"MCP server execution error: {result_str}")
            return result_str
            
        if is_error or "mcp error" in str(res).lower():
            raise MCPExecutionException(f"MCP server error: {res}")
        return str(res)
