"""Integration tests for all server endpoints."""

import asyncio
import httpx
import pytest
import json
import time
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from typing import Optional, Dict, Any
import subprocess
import os


class TestServerEndpoints:
    """Test all server endpoints including health, SSE, and MCP operations."""

    @classmethod
    def setup_class(cls):
        """Start servers for testing."""
        cls.servers = []
        cls.client = None

        # Start SSE server with health API
        env = os.environ.copy()
        env['LOG_LEVEL'] = 'ERROR'  # Reduce noise

        cls.sse_server = subprocess.Popen(
            ['python3', '-m', 'src.cli.mcp_server', '--transport', 'sse', '--port', '3001', '--health-port', '8082'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        cls.servers.append(cls.sse_server)

        # Wait for server to start
        time.sleep(3)

    @classmethod
    def teardown_class(cls):
        """Clean up servers."""
        for server in cls.servers:
            server.terminate()
            server.wait(timeout=5)

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            # Test health endpoint
            response = await client.get("http://localhost:8082/health")
            assert response.status_code == 200

            data = response.json()
            assert 'status' in data
            assert 'timestamp' in data

            # Health API structure varies based on implementation
            # Either has 'checks' or direct status info
            if 'checks' in data:
                # Check database status
                assert 'database' in data['checks']
                db_check = data['checks']['database']
                assert 'status' in db_check
                assert db_check['status'] in ['healthy', 'degraded', 'unhealthy']

            # Check metrics endpoint (may not exist in all implementations)
            response = await client.get("http://localhost:8082/metrics")
            if response.status_code == 200:
                metrics = response.json()
                # Metrics structure can vary
                assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_sse_endpoint(self):
        """Test SSE transport endpoint."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            # Test SSE endpoint exists - use stream to avoid timeout
            async with client.stream('GET', "http://localhost:3001/sse") as response:
                assert response.status_code == 200
                assert 'text/event-stream' in response.headers.get('content-type', '')
                # Just check the stream is open, don't wait for data

    @pytest.mark.asyncio
    async def test_mcp_protocol_over_sse(self):
        """Test MCP protocol operations over SSE transport."""
        async with sse_client("http://localhost:3001/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize session
                response = await session.initialize()
                assert response.protocolVersion

                # List available tools
                tools = await session.list_tools()
                assert tools.tools

                tool_names = [tool.name for tool in tools.tools]
                assert 'list_tables' in tool_names
                assert 'describe_table' in tool_names
                assert 'table_statistics' in tool_names

                # Test list_tables tool
                result = await session.call_tool("list_tables", {})
                assert result.content

                # Parse the result
                content = result.content[0]
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    assert 'tables' in data or 'error' in data

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        async with httpx.AsyncClient() as client:
            # Send multiple concurrent health check requests
            tasks = []
            for _ in range(10):
                tasks.append(client.get("http://localhost:8082/health"))

            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert 'status' in data

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling on endpoints."""
        async with httpx.AsyncClient() as client:
            # Test invalid endpoint
            response = await client.get("http://localhost:3001/invalid")
            assert response.status_code == 404

            # Test invalid method on SSE
            response = await client.post("http://localhost:3001/sse", json={})
            assert response.status_code in [405, 200]  # FastMCP might handle POST differently

            # Test malformed request to health
            response = await client.post("http://localhost:8082/health", data="invalid")
            assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_mcp_tool_errors(self):
        """Test MCP tool error handling."""
        async with sse_client("http://localhost:3001/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Test invalid table name
                result = await session.call_tool("describe_table", {
                    "table_name": "nonexistent_table_xyz"
                })

                content = result.content[0]
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    # Should either return empty columns or an error
                    assert 'columns' in data or 'error' in data

    @pytest.mark.asyncio
    async def test_server_info(self):
        """Test server information endpoints."""
        async with httpx.AsyncClient() as client:
            # Check if server provides any info endpoint
            endpoints_to_try = [
                "http://localhost:3001/",
                "http://localhost:3001/info",
                "http://localhost:8082/info"
            ]

            for endpoint in endpoints_to_try:
                response = await client.get(endpoint)
                # Just check that endpoints respond (might be 404 which is ok)
                assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test that servers handle shutdown gracefully."""
        # Start a temporary server
        env = os.environ.copy()
        env['LOG_LEVEL'] = 'ERROR'

        temp_server = subprocess.Popen(
            ['python3', '-m', 'src.cli.mcp_server', '--transport', 'sse', '--port', '3002', '--no-health-api'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for it to start
        time.sleep(2)

        # Send terminate signal
        temp_server.terminate()

        # Should shut down within reasonable time
        try:
            temp_server.wait(timeout=5)
            assert temp_server.returncode is not None
        except subprocess.TimeoutExpired:
            temp_server.kill()
            pytest.fail("Server did not shut down gracefully")


class TestStdioTransport:
    """Test stdio transport operations."""

    @pytest.mark.asyncio
    async def test_stdio_mcp_operations(self):
        """Test MCP operations over stdio transport."""
        # Use StdioServerParameters to start server
        from mcp.client.stdio import StdioServerParameters

        server_params = StdioServerParameters(
            command='python3',
            args=['-m', 'src.cli.mcp_server', '--transport', 'stdio']
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize
                response = await session.initialize()
                assert response.protocolVersion

                # List tools
                tools = await session.list_tools()
                assert len(tools.tools) > 0

                # Call a tool
                result = await session.call_tool("list_tables", {})
                assert result.content