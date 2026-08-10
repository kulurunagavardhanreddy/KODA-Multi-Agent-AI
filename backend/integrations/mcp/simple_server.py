# simple_server.py

import sys
import json
import traceback

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
            
        try:
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            response = {
                "jsonrpc": "2.0",
                "id": req_id
            }
            
            if method == "initialize":
                response["result"] = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "koda-mock-server",
                        "version": "1.0.0"
                    }
                }
            elif method == "notifications/initialized":
                # Notifications do not receive a response
                continue
            elif method == "tools/list":
                response["result"] = {
                    "tools": [
                        {
                            "name": "echo_message",
                            "description": "Echoes back the message provided. Useful for testing tool connections.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {
                                        "type": "string",
                                        "description": "Message to send to the echo tool"
                                    }
                                },
                                "required": ["message"]
                            }
                        }
                    ]
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "echo_message":
                    msg = arguments.get("message", "")
                    response["result"] = {
                        "content": [
                            {
                                "type": "text",
                                "text": f"📣 Mock MCP Server Echo: {msg}"
                            }
                        ]
                    }
                else:
                    response["error"] = {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found."
                    }
            else:
                response["error"] = {
                    "code": -32601,
                    "message": f"Method '{method}' not found."
                }
                
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except Exception as e:
            # Output error diagnostic to stderr
            sys.stderr.write(f"Error in mock server: {e}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
