"""Base MCP Test Client

Provides common functionality for all MCP test clients including:
- Connection management (stdio and SSE transports)
- Session management
- Result parsing
- Tool discovery and categorization
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters


class TestStatus(Enum):
    """Test execution status"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Result of a test execution"""
    name: str
    status: TestStatus
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    tool_calls: Optional[List[str]] = None


class BaseTestMCP:
    """Base class for MCP test clients"""

    def __init__(self, transport: str = "sse", port: int = 3000, max_tool_calls: int = 10):
        """Initialize base test client.

        Args:
            transport: Transport type ('sse' or 'stdio')
            port: Port for SSE transport (default: 3000)
            max_tool_calls: Maximum tool calls allowed per session (default: 10)
        """
        self.transport = transport
        self.port = port
        self.max_tool_calls = max_tool_calls

        # Session management
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        self._streams_context = None
        self._session_context = None

        # Connection state
        self.connected = False

        # Tool call tracking and limiting
        self.tool_call_count = 0
        self.tool_call_history: List[Tuple[str, Dict[str, Any]]] = []
        self.tool_call_limit_exceeded = False

        if transport == "sse":
            self.mcp_url = f"http://localhost:{port}/sse"

    async def connect(self) -> bool:
        """Connect to MCP server.

        Returns:
            True if connection successful, False otherwise
        """
        if self.transport == "sse":
            try:
                self._streams_context = sse_client(url=self.mcp_url)
                streams = await self._streams_context.__aenter__()
            except Exception as e:
                print(f"❌ SSE connection failed: {e}")
                return False
        else:  # stdio
            try:
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "src.cli.mcp_server", "--transport", "stdio"]
                )
                self._streams_context = stdio_client(server_params)
                streams = await self._streams_context.__aenter__()
            except Exception as e:
                print(f"❌ Stdio connection failed: {e}")
                return False

        try:
            self._session_context = ClientSession(*streams)
            self.session = await self._session_context.__aenter__()

            await self.session.initialize()

            # Get available tools
            response = await self.session.list_tools()
            tools = response.tools

            # Convert to standardized format
            self.available_tools = []
            for tool in tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description or f"Tool: {tool.name}",
                    "input_schema": tool.inputSchema if tool.inputSchema else {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
                self.available_tools.append(tool_info)

            self.connected = True
            return True

        except Exception as e:
            print(f"❌ Session initialization failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from MCP server"""
        if hasattr(self, '_session_context') and self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if hasattr(self, '_streams_context') and self._streams_context:
            await self._streams_context.__aexit__(None, None, None)
        self.connected = False
        self.session = None

    def parse_result(self, result) -> Dict[str, Any]:
        """Parse MCP tool result into standardized format.

        Args:
            result: Raw MCP tool result

        Returns:
            Parsed result as dictionary
        """
        if hasattr(result, 'content'):
            content = result.content
            if isinstance(content, list):
                for item in content:
                    if hasattr(item, 'text'):
                        try:
                            return json.loads(item.text)
                        except json.JSONDecodeError:
                            return {"raw": item.text}
            elif hasattr(content, 'text'):
                try:
                    return json.loads(content.text)
                except json.JSONDecodeError:
                    return {"raw": content.text}
            else:
                return {"raw": content}
        return {"raw": result}

    async def call_tool(self, tool_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call an MCP tool with tracking and limiting.

        Args:
            tool_name: Name of the tool to call
            params: Tool parameters

        Returns:
            Parsed tool result

        Raises:
            RuntimeError: If not connected or tool call limit exceeded
        """
        if not self.connected or not self.session:
            raise RuntimeError("Not connected to MCP server")

        # Use shared runner's counter if available, otherwise use own counter
        if hasattr(self, '_shared_runner') and self._shared_runner:
            current_count = self._shared_runner.tool_call_count
            max_calls = self._shared_runner.max_tool_calls
        else:
            current_count = self.tool_call_count
            max_calls = self.max_tool_calls

        # Check tool call limit
        if current_count >= max_calls:
            self.tool_call_limit_exceeded = True
            raise RuntimeError(f"Tool call limit exceeded ({max_calls} calls). Preventing infinite loops.")

        # Track tool call (update shared runner if available)
        if hasattr(self, '_shared_runner') and self._shared_runner:
            self._shared_runner.tool_call_count += 1
        else:
            self.tool_call_count += 1
        self.tool_call_history.append((tool_name, params or {}))

        try:
            # Call tool
            result = await self.session.call_tool(tool_name, params or {})

            # Parse and return result
            return self.parse_result(result)
        except Exception as e:
            # Log the failed call but don't decrement counter
            print(f"⚠️  Tool call failed for {tool_name}: {e}")
            raise

    def reset_tracking(self):
        """Reset tool call tracking and limits"""
        self.tool_call_count = 0
        self.tool_call_history = []
        self.tool_call_limit_exceeded = False

    def get_tool_call_summary(self) -> Dict[str, Any]:
        """Get summary of tool calls made in this session"""
        return {
            "total_calls": self.tool_call_count,
            "limit": self.max_tool_calls,
            "limit_exceeded": self.tool_call_limit_exceeded,
            "calls_remaining": max(0, self.max_tool_calls - self.tool_call_count),
            "call_history": [{"tool": name, "params": params} for name, params in self.tool_call_history]
        }

    def get_tool_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get tool information by name.

        Args:
            name: Tool name

        Returns:
            Tool information or None if not found
        """
        for tool in self.available_tools:
            if tool["name"] == name:
                return tool
        return None

    def has_tool(self, name: str) -> bool:
        """Check if a tool is available.

        Args:
            name: Tool name

        Returns:
            True if tool is available
        """
        return self.get_tool_by_name(name) is not None

    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all tools in a category.

        Loads tool categories from src/lib/tools/tool_categories.yaml

        Args:
            category: Tool category

        Returns:
            List of tools in the category
        """
        # Load tool categories from YAML file
        yaml_path = Path(__file__).parent.parent.parent / "src/lib/tools/tool_categories.yaml"

        try:
            with open(yaml_path, 'r') as f:
                categories_data = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️  Tool categories file not found at {yaml_path}")
            return []
        except Exception as e:
            print(f"⚠️  Error loading tool categories: {e}")
            return []

        # Get tools for the requested category
        tool_categories = categories_data.get('tool_categories', {})
        if category not in tool_categories:
            return []

        category_tools = tool_categories[category].get('tools', [])

        # Find matching available tools
        tools = []
        for tool in self.available_tools:
            tool_name = tool["name"]
            if tool_name in category_tools:
                tools.append(tool)

        return tools

    async def validate_connection(self) -> TestResult:
        """Validate server connection and tool availability.

        Returns:
            TestResult indicating connection status
        """
        if not self.connected:
            return TestResult(
                name="connection_validation",
                status=TestStatus.FAILED,
                message="Not connected to MCP server"
            )

        if not self.available_tools:
            return TestResult(
                name="connection_validation",
                status=TestStatus.FAILED,
                message="No tools available from server"
            )

        return TestResult(
            name="connection_validation",
            status=TestStatus.PASSED,
            message=f"Connected with {len(self.available_tools)} tools available",
            data={
                "transport": self.transport,
                "tool_count": len(self.available_tools),
                "tools": [t["name"] for t in self.available_tools]
            }
        )

    @staticmethod
    def format_test_result(result: TestResult, verbose: bool = False) -> str:
        """Format test result for display.

        Args:
            result: Test result to format
            verbose: Include detailed information

        Returns:
            Formatted string
        """
        status_emoji = {
            TestStatus.PASSED: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.SKIPPED: "⚠️",
            TestStatus.ERROR: "🔥"
        }

        output = f"{status_emoji[result.status]} {result.name}"

        if result.message:
            output += f": {result.message}"

        if verbose and result.data:
            output += f"\n   Data: {json.dumps(result.data, indent=2)}"

        if result.duration_ms:
            output += f"\n   Duration: {result.duration_ms:.2f}ms"

        if result.tool_calls:
            output += f"\n   Tool calls: {', '.join(result.tool_calls)}"

        return output