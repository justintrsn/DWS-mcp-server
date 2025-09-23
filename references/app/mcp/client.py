import asyncio
from typing import Optional, Any, Dict, List, Tuple
import logging
import time
import random

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

load_dotenv()

# Default timeout configuration
DEFAULT_CONNECT_TIMEOUT = 30.0  # seconds
DEFAULT_OPERATION_TIMEOUT = 60.0  # seconds
MAX_RETRIES = 3  # Maximum number of retries for operations
TOOLS_CACHE_TIMEOUT = 1800  # 30 minutes cache timeout for tools list

# Configure logging
logger = logging.getLogger(__name__)

class Tool:
    def __init__(
        self, name: str, description: str, input_schema: dict[str, Any]
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: dict[str, Any] = input_schema

    def format_for_llm(self) -> str | None:
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = f"{param_name}: {param_info.get('description', 'No description')}"
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

            return f"Tool: {self.name} | Description: {self.description} | Args: {', '.join(args_desc)}"

class MCPClient:
    def __init__(
        self,
        server_name: str,
        server_url: str,
        headers: Optional[Dict[str, str]],
        server_type: str = "sse",
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        operation_timeout: float = DEFAULT_OPERATION_TIMEOUT,
        tools_cache_timeout: float = TOOLS_CACHE_TIMEOUT
    ) -> None:
        self.server_name = server_name
        self.server_url = server_url
        self._headers = headers or {}
        self.server_type = server_type
        self._sse_context: Optional[Any] = None
        self._session: Optional[ClientSession] = None
        self._is_connected = False
        self._tools_cache: Optional[Tuple[List[Tool], float]] = None  # (tools, timestamp)
        self.connect_timeout = connect_timeout
        self.operation_timeout = operation_timeout
        self.tools_cache_timeout = tools_cache_timeout
        self._reconnect_lock = asyncio.Lock()  # Lock to prevent multiple simultaneous reconnection attempts
        self._validation_task: Optional[asyncio.Task] = None
        self._last_validation_time: float = 0
        self._validation_interval: float = 30.0  # Validate connection every 30 seconds

    @classmethod
    async def create(
        cls,
        server_name: str,
        server_url: str,
        headers: Optional[Dict[str, str]] = None,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        operation_timeout: float = DEFAULT_OPERATION_TIMEOUT
    ) -> "MCPClient":
        instance = cls(server_name, server_url, headers, connect_timeout=connect_timeout, operation_timeout=operation_timeout)
        await instance.__aenter__()
        return instance

    async def __aenter__(self) -> "MCPClient":
        if self._is_connected:
            raise RuntimeError("Client is already connected")

        try:
            self._sse_context = sse_client(self.server_url, headers=self._headers)
            self.read, self.write = await asyncio.wait_for(
                self._sse_context.__aenter__(),
                timeout=self.connect_timeout
            )

            self._session = ClientSession(self.read, self.write)
            await asyncio.wait_for(
                self._session.__aenter__(),
                timeout=self.connect_timeout
            )
            await asyncio.wait_for(
                self._session.initialize(),
                timeout=self.connect_timeout
            )

            self._is_connected = True
            return self

        except asyncio.TimeoutError:
            await self._cleanup_resources()
            raise ConnectionError(f"Connection to MCP server timed out after {self.connect_timeout} seconds")
        except Exception as e:
            await self._cleanup_resources()
            raise ConnectionError(f"Failed to connect to MCP server: {str(e)}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up resources when exiting the context."""
        await self._cleanup_resources()

    async def _cleanup_resources(self) -> None:
        """Clean up all resources and reset state."""
        # First cancel any pending validation task
        if self._validation_task is not None and not self._validation_task.done():
            self._validation_task.cancel()
            try:
                await self._validation_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling validation task: {str(e)}")
            self._validation_task = None

        # Then cleanup session
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error cleaning up session: {str(e)}")
            self._session = None

        # Finally cleanup SSE context
        if self._sse_context is not None:
            try:
                await self._sse_context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error cleaning up SSE context: {str(e)}")
            self._sse_context = None

        # Reset state
        self._tools_cache = None
        self._is_connected = False

    def _check_connected(self) -> None:
        if not self._is_connected or self._session is None:
            raise RuntimeError("Client is not connected to the server")

    async def _ensure_connection(self) -> None:
        """Ensure the client is connected, attempt to reconnect if not."""
        if not self._is_connected or self._session is None:
            await self._reconnect()
            return

        async with self._reconnect_lock:
            # Double check after acquiring lock
            if not self._is_connected or self._session is None:
                await self._reconnect()
                return

            # Start connection validation in background if needed
            current_time = time.time()
            if (self._validation_task is None or self._validation_task.done()) and \
               (current_time - self._last_validation_time) >= self._validation_interval:
                self._last_validation_time = current_time
                self._validation_task = asyncio.create_task(self._validate_connection())

    async def _validate_connection(self) -> None:
        logger.info("Validating MCP connection")
        """Validate connection in background."""
        try:
            await asyncio.wait_for(
                self._session.list_tools(),
                timeout=5.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Connection validation failed: {str(e)}")
            self._is_connected = False
            # Don't await reconnect here to avoid blocking
            asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the server."""
        logger.info(f"Attempting to reconnect to MCP server {self.server_name}")
        
        # Ensure we're not already in a reconnection process
        if not self._reconnect_lock.locked():
            async with self._reconnect_lock:
                await self._cleanup_resources()
                try:
                    # Create new SSE context
                    self._sse_context = sse_client(self.server_url, headers=self._headers)
                    self.read, self.write = await asyncio.wait_for(
                        self._sse_context.__aenter__(),
                        timeout=self.connect_timeout
                    )

                    # Create new session
                    self._session = ClientSession(self.read, self.write)
                    await asyncio.wait_for(
                        self._session.__aenter__(),
                        timeout=self.connect_timeout
                    )
                    await asyncio.wait_for(
                        self._session.initialize(),
                        timeout=self.connect_timeout
                    )

                    self._is_connected = True
                    logger.info(f"Successfully reconnected to MCP server {self.server_name}")
                except Exception as e:
                    await self._cleanup_resources()
                    logger.error(f"Failed to reconnect to MCP server {self.server_name}: {str(e)}")
                    raise ConnectionError(f"Failed to reconnect to MCP server: {str(e)}") from e
        else:
            logger.warning(f"Reconnection already in progress for MCP server {self.server_name}")

    async def _retry_operation(self, operation, *args, **kwargs) -> Any:
        """Retry an operation with reconnection if needed."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                await self._ensure_connection()
                return await operation(*args, **kwargs)
            except (RuntimeError, ConnectionError) as e:
                last_error = e
                logger.warning(f"Operation failed (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    # Exponential backoff with jitter
                    wait_time = min(2 ** attempt + random.uniform(0, 1), 10)
                    logger.info(f"Waiting {wait_time:.2f} seconds before retry...")
                    await asyncio.sleep(wait_time)
                continue
            except asyncio.CancelledError:
                # Propagate cancellation to caller
                raise
            except Exception as e:
                logger.error(f"Unexpected error during operation: {str(e)}")
                raise

        raise last_error or RuntimeError("Operation failed after all retries")

    async def list_tools(self) -> List[Tool]:
        """List available tools with caching."""
        async def _list_tools():
            if not self._session:
                raise RuntimeError(f"Server {self.server_name} not initialized")

            current_time = time.time()
            
            # Check if cache is valid
            if self._tools_cache is not None:
                cached_tools, cache_timestamp = self._tools_cache
                if current_time - cache_timestamp < self.tools_cache_timeout:
                    logger.debug(f"Using cached tools list for {self.server_name}")
                    return cached_tools
                else:
                    logger.debug(f"Tools cache expired for {self.server_name}")

            try:
                tools_response = await asyncio.wait_for(
                    self._session.list_tools(),
                    timeout=self.operation_timeout
                )
                tools = []

                for item in tools_response:
                    if isinstance(item, tuple) and item[0] == "tools":
                        tools.extend(
                            Tool(tool.name, tool.description, tool.inputSchema)
                            for tool in item[1]
                        )

                # Cache the tools with current timestamp
                self._tools_cache = (tools, current_time)
                logger.debug(f"Updated tools cache for {self.server_name}")
                return tools
            except asyncio.TimeoutError:
                logger.error(f"Timeout while listing tools for {self.server_name}")
                raise
            except Exception as e:
                logger.error(f"Error listing tools for {self.server_name}: {str(e)}")
                raise

        return await self._retry_operation(_list_tools)

    async def list_resources(self) -> Any:
        """List available resources."""
        async def _list_resources():
            try:
                return await asyncio.wait_for(
                    self._session.list_resources(),
                    timeout=self.operation_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout while listing resources for {self.server_name}")
                raise
            except Exception as e:
                logger.error(f"Error listing resources for {self.server_name}: {str(e)}")
                raise

        return await self._retry_operation(_list_resources)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with the given arguments."""
        async def _call_tool():
            try:
                return await asyncio.wait_for(
                    self._session.call_tool(name, arguments),
                    timeout=self.operation_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout while calling tool {name} for {self.server_name}")
                raise
            except Exception as e:
                logger.error(f"Error calling tool {name} for {self.server_name}: {str(e)}")
                raise

        return await self._retry_operation(_call_tool)

    @property
    def is_connected(self) -> bool:
        return self._is_connected