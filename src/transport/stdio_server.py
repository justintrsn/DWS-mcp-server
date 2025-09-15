"""Standard I/O transport for MCP server."""

import sys
import logging
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


class StdioTransport:
    """MCP server transport using standard input/output."""
    
    def __init__(self, mcp_instance: FastMCP):
        """Initialize stdio transport.
        
        Args:
            mcp_instance: FastMCP server instance with registered tools
        """
        self.mcp = mcp_instance
        
    def run(self):
        """Run the stdio transport server.
        
        Reads JSON-RPC requests from stdin and writes responses to stdout.
        """
        logger.info("Starting MCP server in stdio mode")
        
        try:
            # FastMCP handles stdio transport natively
            self.mcp.run()
        except KeyboardInterrupt:
            logger.info("Stdio server shutdown requested")
        except Exception as e:
            logger.error(f"Stdio server error: {e}")
            sys.exit(1)
    
    def stop(self):
        """Stop the stdio transport server."""
        logger.info("Stopping stdio transport")
        # FastMCP handles cleanup internally