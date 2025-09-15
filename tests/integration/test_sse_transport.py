"""Integration tests for SSE transport."""

import pytest
import json
import sys
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from transport.sse_server import SSETransport
from fastmcp import FastMCP


class TestSSETransport:
    """Integration tests for SSE transport mode."""
    
    @pytest.fixture
    def mock_mcp(self):
        """Create a mock FastMCP instance."""
        mock = Mock(spec=FastMCP)
        return mock
    
    @pytest.fixture
    def mock_tools(self):
        """Create mock tools dictionary."""
        # Create mock tool functions with proper attributes
        test_tool = AsyncMock(return_value={'result': 'test_result'})
        test_tool.__doc__ = "Test tool for testing"
        test_tool.func = test_tool  # Add func attribute for FunctionTool compatibility

        list_tables = AsyncMock(return_value={'tables': ['users', 'products']})
        list_tables.__doc__ = "List database tables"
        list_tables.func = list_tables  # Add func attribute for FunctionTool compatibility

        return {
            'test_tool': test_tool,
            'list_tables': list_tables
        }
    
    def test_sse_transport_initialization(self, mock_mcp, mock_tools):
        """Test SSE transport initializes correctly."""
        transport = SSETransport(mock_mcp, host="127.0.0.1", port=3001, tools_dict=mock_tools)
        
        assert transport.mcp == mock_mcp
        assert transport.host == "127.0.0.1"
        assert transport.port == 3001
        assert transport.app is not None
        assert transport.tools == mock_tools
    
    def test_sse_transport_root_endpoint(self, mock_mcp):
        """Test SSE transport root endpoint."""
        transport = SSETransport(mock_mcp)
        client = TestClient(transport.app)
        
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json() == {
            "status": "MCP SSE Server Running",
            "transport": "sse"
        }
    
    def test_sse_transport_list_tools_endpoint(self, mock_mcp, mock_tools):
        """Test SSE transport list tools endpoint."""
        transport = SSETransport(mock_mcp, tools_dict=mock_tools)
        client = TestClient(transport.app)
        
        response = client.get("/mcp/v1/tools")
        
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 2
        tool_names = [tool["name"] for tool in data["tools"]]
        assert "test_tool" in tool_names
        assert "list_tables" in tool_names
    
    @pytest.mark.asyncio
    async def test_sse_transport_execute_tool(self, mock_mcp, mock_tools):
        """Test SSE transport tool execution."""
        transport = SSETransport(mock_mcp, tools_dict=mock_tools)

        # Test tool execution
        result = await transport._execute_tool("test_tool", {"param": "value"})

        # Result should be wrapped in MCP format
        assert 'content' in result
        assert isinstance(result['content'], list)
        assert result['content'][0]['type'] == 'text'
        assert '"result": "test_result"' in result['content'][0]['text']
        mock_tools['test_tool'].assert_called_once_with(param="value")
    
    @pytest.mark.asyncio
    async def test_sse_transport_execute_tool_with_prefix(self, mock_mcp, mock_tools):
        """Test SSE transport tool execution with tools/ prefix."""
        transport = SSETransport(mock_mcp, tools_dict=mock_tools)

        # Test with tools/ prefix
        result = await transport._execute_tool("tools/list_tables", {})

        # Result should be wrapped in MCP format
        assert 'content' in result
        assert isinstance(result['content'], list)
        assert result['content'][0]['type'] == 'text'
        assert '"tables"' in result['content'][0]['text']
        assert '"users"' in result['content'][0]['text']
        mock_tools['list_tables'].assert_called_once_with()
    
    @pytest.mark.asyncio
    async def test_sse_transport_execute_unknown_tool(self, mock_mcp):
        """Test SSE transport with unknown tool."""
        transport = SSETransport(mock_mcp)
        
        with pytest.raises(ValueError) as exc_info:
            await transport._execute_tool("unknown_tool", {})
        
        assert "Unknown tool: unknown_tool" in str(exc_info.value)
    
    def test_sse_transport_mcp_endpoint(self, mock_mcp):
        """Test SSE transport MCP SSE endpoint."""
        transport = SSETransport(mock_mcp)
        client = TestClient(transport.app)
        
        # Send JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "method": "test_tool",
            "params": {"message": "hello"},
            "id": 1
        }
        
        # Note: TestClient doesn't fully support SSE streaming
        # This tests that the endpoint exists and accepts POST
        response = client.post(
            "/mcp/v1/sse",
            json=request,
            headers={"Accept": "text/event-stream"}
        )
        
        # SSE endpoints return streaming responses
        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/event-stream; charset=utf-8"
    
    def test_sse_transport_error_handling(self, mock_mcp):
        """Test SSE transport error handling."""
        transport = SSETransport(mock_mcp)
        client = TestClient(transport.app)
        
        # Send invalid request
        request = {
            "jsonrpc": "2.0",
            "method": "nonexistent_tool",
            "params": {},
            "id": 2
        }
        
        response = client.post(
            "/mcp/v1/sse",
            json=request,
            headers={"Accept": "text/event-stream"}
        )
        
        assert response.status_code == 200  # SSE always returns 200
        # Error will be in the SSE stream data
    
    def test_sse_transport_with_real_mcp_instance(self):
        """Test SSE transport with a real FastMCP instance."""
        # Create a real FastMCP instance
        mcp = FastMCP("Test MCP")
        
        # Add a test tool
        @mcp.tool()
        async def test_tool(message: str) -> dict:
            return {"response": f"Received: {message}"}
        
        transport = SSETransport(mcp, port=3002)
        
        assert transport.mcp == mcp
        assert hasattr(mcp, 'tool')  # Verify tool decorator exists
        assert transport.port == 3002
    
    @patch('uvicorn.run')
    def test_sse_transport_run(self, mock_uvicorn, mock_mcp):
        """Test SSE transport run method."""
        transport = SSETransport(mock_mcp, host="0.0.0.0", port=3003)
        
        transport.run()
        
        # Verify uvicorn.run was called with correct parameters
        mock_uvicorn.assert_called_once_with(
            transport.app,
            host="0.0.0.0",
            port=3003,
            log_level="info"
        )
    
    @patch('uvicorn.run')
    def test_sse_transport_keyboard_interrupt(self, mock_uvicorn, mock_mcp):
        """Test SSE transport handles keyboard interrupt."""
        transport = SSETransport(mock_mcp)
        
        # Mock uvicorn to raise KeyboardInterrupt
        mock_uvicorn.side_effect = KeyboardInterrupt()
        
        # Should not raise exception
        transport.run()
    
    def test_sse_transport_stop(self, mock_mcp):
        """Test SSE transport stop method."""
        transport = SSETransport(mock_mcp)
        
        # Should not raise exception
        transport.stop()
    
    @pytest.mark.asyncio
    async def test_sse_transport_run_async(self, mock_mcp):
        """Test SSE transport async run method."""
        transport = SSETransport(mock_mcp, port=3004)
        
        # Mock the server to avoid actual startup
        with patch('uvicorn.Server') as mock_server_class:
            mock_server = Mock()
            mock_server.serve = AsyncMock()
            mock_server_class.return_value = mock_server
            
            await transport.run_async()
            
            mock_server.serve.assert_called_once()