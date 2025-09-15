"""Server-Sent Events (SSE) transport for MCP server."""

import json
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastmcp import FastMCP
import uvicorn

logger = logging.getLogger(__name__)


class SSETransport:
    """MCP server transport using Server-Sent Events over HTTP."""
    
    def __init__(self, mcp_instance: FastMCP, host: str = "0.0.0.0", port: int = 3000, tools_dict: Dict = None):
        """Initialize SSE transport.
        
        Args:
            mcp_instance: FastMCP server instance with registered tools
            host: Host to bind the server to
            port: Port to bind the server to
            tools_dict: Dictionary of tool functions
        """
        self.mcp = mcp_instance
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP SSE Server")
        # Store tool functions passed from the MCP server
        self.tools = tools_dict or {}
        self._setup_routes()
        
    def _setup_routes(self):
        """Set up FastAPI routes for SSE transport."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint for health check."""
            return {"status": "MCP SSE Server Running", "transport": "sse"}
        
        @self.app.post("/mcp/v1/sse")
        async def mcp_sse_endpoint(request: Request):
            """SSE endpoint for MCP protocol.
            
            Accepts JSON-RPC requests and returns responses via SSE stream.
            """
            # Read request body before creating generator
            try:
                body = await request.json()
            except Exception as e:
                logger.error(f"Failed to parse request body: {e}")
                body = {}
            
            async def event_generator():
                try:
                    # Process through MCP
                    if "method" in body:
                        # Handle MCP tool invocation
                        method = body.get("method")
                        params = body.get("params", {})
                        id = body.get("id")
                        
                        # Find and execute the tool
                        tool_response = await self._execute_tool(method, params)
                        
                        # Format as JSON-RPC response
                        response = {
                            "jsonrpc": "2.0",
                            "id": id,
                            "result": tool_response
                        }
                        
                        # Send as SSE event
                        yield f"data: {json.dumps(response)}\n\n"
                    else:
                        # No method specified
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {
                                "code": -32600,
                                "message": "Invalid Request",
                                "data": "No method specified"
                            }
                        }
                        yield f"data: {json.dumps(error_response)}\n\n"
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"SSE request error: {str(e)}\nTraceback: {error_details}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": body.get("id") if body else None,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    }
                    yield f"data: {json.dumps(error_response)}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        @self.app.get("/mcp/v1/tools")
        async def list_tools():
            """List available MCP tools."""
            tools = []
            for tool_name, tool_func in self.tools.items():
                # Get description from various sources
                description = ""
                short_desc = "No description available"

                # Try to get description from different attributes
                if hasattr(tool_func, '__doc__') and tool_func.__doc__:
                    description = tool_func.__doc__
                    short_desc = description.strip().split('\n')[0]
                elif hasattr(tool_func, 'description') and isinstance(tool_func.description, str):
                    description = tool_func.description
                    short_desc = description.strip().split('\n')[0] if description else "No description available"

                tools.append({
                    "name": tool_name,
                    "description": short_desc,
                    "full_doc": description  # Include full documentation if needed
                })
            return {"tools": tools}
    
    async def _execute_tool(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool.
        
        Args:
            method: Tool method name
            params: Tool parameters
            
        Returns:
            Tool execution result formatted for MCP protocol
        """
        # Remove 'tools/' prefix if present
        if method.startswith("tools/"):
            method = method[6:]
        
        # Find the tool in our tools dict
        if method in self.tools:
            tool_func = self.tools[method]
            # Execute the tool with parameters
            # Handle both FunctionTool objects and raw functions
            if hasattr(tool_func, 'func'):
                # FunctionTool object - get the actual function
                actual_func = tool_func.func
            elif callable(tool_func):
                # Already a callable function
                actual_func = tool_func
            else:
                raise ValueError(f"Tool {method} is not callable")
            
            result = await actual_func(**params)
            
            # Format result for MCP protocol
            if isinstance(result, dict):
                if 'error' in result:
                    # Return errors as-is
                    return result
                else:
                    # Wrap successful results in content field for MCP protocol
                    return {
                        "content": [{
                            "type": "text",
                            "text": json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                        }]
                    }
            else:
                # Wrap non-dict results
                return {
                    "content": [{
                        "type": "text", 
                        "text": str(result)
                    }]
                }
        else:
            raise ValueError(f"Unknown tool: {method}")
    
    def run(self):
        """Run the SSE transport server."""
        logger.info(f"Starting MCP server in SSE mode on {self.host}:{self.port}")
        
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
        except KeyboardInterrupt:
            logger.info("SSE server shutdown requested")
        except Exception as e:
            logger.error(f"SSE server error: {e}")
            raise
    
    async def run_async(self):
        """Run the SSE transport server asynchronously."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def stop(self):
        """Stop the SSE transport server."""
        logger.info("Stopping SSE transport")
        # Uvicorn handles shutdown via signal handlers