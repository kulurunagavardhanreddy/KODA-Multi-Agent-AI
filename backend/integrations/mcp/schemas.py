# schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    id: Optional[Union[int, str]] = None

class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[int, str]] = None

class ServerConfig(BaseModel):
    command: str
    args: List[str] = Field(default_factory=list)
    env: Optional[Dict[str, str]] = None
