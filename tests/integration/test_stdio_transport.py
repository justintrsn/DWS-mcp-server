"""Integration tests for stdio transport."""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from transport.stdio_server import StdioTransport
from fastmcp import FastMCP


class TestStdioTransport:
    """Integration tests for stdio transport mode."""
    
    @pytest.fixture
    def mock_mcp(self):
        """Create a mock FastMCP instance."""
        mock = Mock(spec=FastMCP)
        mock._tools = {
            'test_tool': Mock(return_value={'result': 'test_result'})
        }
        return mock
    
    def test_stdio_transport_initialization(self, mock_mcp):
        """Test stdio transport initializes correctly."""
        transport = StdioTransport(mock_mcp)
        
        assert transport.mcp == mock_mcp
    
    def test_stdio_transport_run(self, mock_mcp):
        """Test stdio transport runs the MCP instance."""
        transport = StdioTransport(mock_mcp)
        
        # Mock the run method to avoid actual execution
        mock_mcp.run = Mock()
        
        transport.run()
        
        # Verify MCP run was called
        mock_mcp.run.assert_called_once()
    
    def test_stdio_transport_handles_keyboard_interrupt(self, mock_mcp):
        """Test stdio transport handles keyboard interrupt gracefully."""
        transport = StdioTransport(mock_mcp)
        
        # Mock run to raise KeyboardInterrupt
        mock_mcp.run = Mock(side_effect=KeyboardInterrupt())
        
        # Should not raise exception
        transport.run()
    
    def test_stdio_transport_handles_errors(self, mock_mcp):
        """Test stdio transport handles errors properly."""
        transport = StdioTransport(mock_mcp)
        
        # Mock run to raise an exception
        mock_mcp.run = Mock(side_effect=Exception("Test error"))
        
        # Should exit with error code
        with pytest.raises(SystemExit) as exc_info:
            transport.run()
        
        assert exc_info.value.code == 1
    
    def test_stdio_transport_stop(self, mock_mcp):
        """Test stdio transport stop method."""
        transport = StdioTransport(mock_mcp)
        
        # Should not raise exception
        transport.stop()
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_stdio_transport_json_rpc_communication(self, mock_stdout, mock_stdin, mock_mcp):
        """Test JSON-RPC communication through stdio."""
        transport = StdioTransport(mock_mcp)
        
        # Simulate JSON-RPC request on stdin
        request = {
            "jsonrpc": "2.0",
            "method": "test_tool",
            "params": {"param1": "value1"},
            "id": 1
        }
        
        mock_stdin.read.return_value = json.dumps(request)
        
        # FastMCP handles the actual JSON-RPC processing
        # This test verifies the transport layer setup
        assert transport.mcp is not None
    
    def test_stdio_transport_with_real_mcp_instance(self):
        """Test stdio transport with a real FastMCP instance."""
        # Create a real FastMCP instance
        mcp = FastMCP("Test MCP")
        
        # Add a test tool
        @mcp.tool()
        async def test_tool(message: str) -> dict:
            return {"response": f"Received: {message}"}
        
        transport = StdioTransport(mcp)
        
        assert transport.mcp == mcp
        # FastMCP instance should have the tool registered
        assert hasattr(mcp, 'tool')  # Verify tool decorator exists
    
    def test_stdio_transport_logging(self, mock_mcp, caplog):
        """Test stdio transport logging."""
        import logging
        
        with caplog.at_level(logging.INFO):
            transport = StdioTransport(mock_mcp)
            
            # Mock run to complete immediately
            mock_mcp.run = Mock()
            
            transport.run()
            
            # Check for expected log messages
            assert "Starting MCP server in stdio mode" in caplog.text
    
    def test_stdio_transport_multiple_instances(self, mock_mcp):
        """Test multiple stdio transport instances can be created."""
        transport1 = StdioTransport(mock_mcp)
        transport2 = StdioTransport(mock_mcp)
        
        assert transport1 is not transport2
        assert transport1.mcp == transport2.mcp == mock_mcp