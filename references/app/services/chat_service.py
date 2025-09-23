import logging
from typing import AsyncGenerator, List, Dict, Any

import httpx
from fastapi import HTTPException
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from app.core.config import config
from app.core.react_agent import ReactAgent
from app.mcp.client import MCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_last_message(body):
    # 从请求中提取消息
    messages = body.get('messages', [])
    if not messages:
        raise ValueError("No messages provided in request")
    # 获取最后一个用户消息
    user_message = next((msg['content'] for msg in reversed(messages) if msg['role'] == 'user'), None)
    if not user_message:
        raise ValueError("No user message found in request")
    return user_message


class ChatService:
    def __init__(self):
        self.client = None
        self.model = config.model_name
        self.mcp_clients: List[MCPClient] = []
        self.react_agent = ReactAgent()

    def _get_client(self, api_key: str) -> AsyncOpenAI:
        """Get or create the OpenAI client with current API key."""
        if self.client is None:
            if not api_key:
                raise HTTPException(status_code=401, detail="API key not set")
            
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=config.api_url,
                http_client=httpx.AsyncClient(verify=config.ssl_verify)
            )
        return self.client

    async def initialize_mcp_clients(self):
        """Initialize MCP clients from environment variables."""
        try:
            mcp_servers_config = config.mcp_servers_config
            if not mcp_servers_config:
                logger.error("No MCP servers configuration found")
                return

            try:
                servers = mcp_servers_config.get("servers", {})

                for server_id, server_config in servers.items():
                    client = None
                    try:
                        server_type = server_config.get("type")
                        server_url = server_config.get("url")
                        server_headers = server_config.get("headers", {})

                        if not all([server_type, server_url]):
                            logger.warning(f"Incomplete MCP server configuration for {server_id}")
                            continue

                        client = MCPClient(
                            server_name=server_id,
                            server_url=server_url,
                            server_type=server_type,
                            headers=server_headers
                        )

                        # 创建连接
                        client = await client.create(client.server_name, client.server_url, client._headers)
                        logger.info(f"Created connection for MCP client {server_id}")

                        # 获取工具列表
                        tools = await client.list_tools()
                        logger.info(f"Retrieved {len(tools)} tools from MCP client {server_id}")

                        self.mcp_clients.append(client)
                        logger.info(f"Initialized MCP client for {server_id}")

                    except Exception as e:
                        logger.error(f"Error initializing MCP client for {server_id}: {str(e)}")
                        if client:
                            try:
                                await client.close()
                                logger.info(f"Closed connection for MCP client {server_id}")
                            except Exception as close_error:
                                logger.error(f"Error closing MCP client {server_id}: {str(close_error)}")
                        continue

            except Exception as e:
                logger.error(f"Error parsing MCP servers configuration: {str(e)}")
                return

        except Exception as e:
            logger.error(f"Error in initialize_mcp_clients: {str(e)}")
            # 清理所有已创建的客户端
            for client in self.mcp_clients:
                try:
                    await client.close()
                    logger.info(f"Closed connection for MCP client {client.server_name}")
                except Exception as close_error:
                    logger.error(f"Error closing MCP client {client.server_name}: {str(close_error)}")
            self.mcp_clients.clear()
            return

    async def process_chat_completion_stream(
            self,
            body: Dict[str, Any],
            api_key: str
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Process a chat completion request with streaming."""
        try:
            messages = body.get('messages', [])
            if not messages:
                raise ValueError("No messages provided in request")
            
            # 获取最后一个用户消息
            user_message = next((msg['content'] for msg in reversed(messages) if msg['role'] == 'user'), None)
            if not user_message:
                raise ValueError("No user message found in request")

            all_tools = await self.get_mcp_tools()

            # 从 body 中提取大模型参数
            llm_params = {
                k: v for k, v in body.items()
            }
            # 添加对话历史到参数中
            llm_params['messages'] = messages

            # 使用 ReactAgent 处理消息流
            async for chunk in self.react_agent.process_stream(
                prompt=user_message,
                mcp_clients=self.mcp_clients,
                tools=all_tools,
                llm_params=llm_params,
                api_key=api_key
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Error in process_chat_completion_stream: {str(e)}")
            error_chunk = ChatCompletionChunk(
                id="error",
                choices=[Choice(
                    message=ChatCompletionMessage(role="assistant",
                                                  content=f"Error: {str(e)}"),
                    finish_reason="stop",
                    index=0
                )],
                created=0,
                model=self.model,
                object="chat.completion.chunk"
            )
            yield error_chunk

    async def process_chat_completion(
            self,
            body: Dict[str, Any],
            api_key: str
    ) -> Dict[str, Any]:
        """Process a chat completion request."""
        try:
            messages = body.get('messages', [])
            if not messages:
                raise ValueError("No messages provided in request")
            
            # 获取最后一个用户消息
            user_message = next((msg['content'] for msg in reversed(messages) if msg['role'] == 'user'), None)
            if not user_message:
                raise ValueError("No user message found in request")

            all_tools = await self.get_mcp_tools()

            # 从 body 中提取大模型参数
            llm_params = {
                k: v for k, v in body.items()
            }
            # 添加对话历史到参数中
            llm_params['messages'] = messages

            # 使用 ReactAgent 处理消息
            response = await self.react_agent.process(
                prompt=user_message,
                mcp_clients=self.mcp_clients,
                tools=all_tools,
                llm_params=llm_params,
                api_key=api_key
            )

            return response

        except Exception as e:
            logger.error(f"Error in process_chat_completion: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "message": str(e),
                        "type": "internal_error",
                        "code": 500
                    }
                }
            )

    async def get_mcp_tools(self):
        # 获取所有工具
        all_tools = []
        for client in self.mcp_clients:
            tools = await client.list_tools()
            all_tools.extend(tools)
        return all_tools