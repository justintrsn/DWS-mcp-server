import json
import logging
import os
import re
from datetime import datetime
from typing import List, AsyncGenerator, Dict, Any

import httpx
from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta
from openai.types.completion_usage import CompletionUsage

from app.core.config import config
from app.mcp.client import MCPClient, Tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_json_from_response(content: str) -> str:
    """Extract JSON from LLM response content.

    Args:
        content: The response content from LLM

    Returns:
        str: Extracted JSON string or empty string if not found
    """
    if not content:
        logger.error("Empty response content from LLM")
        return ""

    pattern = r'\{[\s\S]*"thought":[\s\S]*\}'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        logger.error(f"Failed to find JSON pattern in response: {content[:200]}...")
        return ""

    return match.group(0)


async def get_mcp_tool_details(tools):
    # Log detailed tool information
    tool_details = []
    for tool in tools:
        if hasattr(tool, 'input_schema'):
            required_params = tool.input_schema.get("required", [])
            properties = tool.input_schema.get("properties", {})
            tool_details.append({
                "name": tool.name,
                "description": tool.description,
                "required_parameters": required_params,
                "parameters": properties
            })
        else:
            logger.info(f"No input schema found for tool: {tool.name}")
            tool_details.append({
                "name": tool.name,
                "description": tool.description,
                "required_parameters": [],
                "parameters": {}
            })
    return tool_details


async def _execute_action(
        action: str,
        action_input: Dict[str, Any],
        mcp_clients: List[MCPClient]
) -> Any:
    """Execute an action using the appropriate MCP client."""
    try:
        # Find the appropriate client
        for client in mcp_clients:
            tools = await client.list_tools()
            matching_tool = next((tool for tool in tools if tool.name == action), None)

            if matching_tool:
                # Validate required parameters
                required_params = matching_tool.input_schema.get("required", [])
                missing_params = [param for param in required_params if param not in action_input]

                if missing_params:
                    error_msg = f"Missing required parameters for tool {action}: {', '.join(missing_params)}"
                    logger.error(error_msg)
                    return f"Error: {error_msg}"

                # Execute the action
                result = await client.call_tool(action, action_input)

                # 处理 CallToolResult 对象
                if hasattr(result, 'content'):
                    for item in result.content:
                        if hasattr(item, 'text'):
                            try:
                                # 尝试解析 JSON
                                return json.loads(item.text)
                            except json.JSONDecodeError:
                                # 如果不是 JSON，直接使用文本
                                return item.text

                    # 如果没有 content 项，返回空列表
                    return []
                else:
                    # 如果不是 CallToolResult 对象，直接返回原始结果
                    return result

        return f"Error: No client found for action {action}"

    except Exception as e:
        logger.error(f"Error executing action {action}: {str(e)}")
        return f"Error executing action {action}: {str(e)}"


async def get_messages(prompt, **kwargs):
    if "messages" in kwargs:
        messages = kwargs.pop("messages")
        # Find the last user message and append the prompt
        found_user_message = False
        for msg in reversed(messages):
            if msg["role"] == "user":
                msg["content"] = prompt
                found_user_message = True
                break
        if not found_user_message:
            messages.append({"role": "user", "content": prompt})
        # Always update kwargs with the modified messages
        kwargs["messages"] = messages
    else:
        messages = [{"role": "user", "content": prompt}]
        kwargs["messages"] = messages
    return kwargs


def _get_client(api_key: str) -> AsyncOpenAI:
    """Get a new OpenAI client with the provided API key."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key not set")

    logger.info(f"Creating new client with API key: {api_key[:8]}... and base URL: {config.api_url}")

    return AsyncOpenAI(
        api_key=api_key,
        base_url=config.api_url,
        http_client=httpx.AsyncClient(verify=config.ssl_verify)
    )


def _process_chunk_content(chunk: ChatCompletionChunk, analysis_response: str) -> tuple[str, ChatCompletionChunk]:
    """Process the content of a chunk and update the analysis response.

    Args:
        chunk: The chunk to process
        analysis_response: The current analysis response string

    Returns:
        tuple[str, ChatCompletionChunk]: Updated analysis response and processed chunk
    """
    if chunk.choices[0].delta.content is not None:
        content = chunk.choices[0].delta.content
        analysis_response += content
        # 将 content 复制到 reasoning_content
        if not hasattr(chunk.choices[0].delta, 'reasoning_content'):
            setattr(chunk.choices[0].delta, 'reasoning_content', None)
        chunk.choices[0].delta.reasoning_content = content
        # 清除原始的 content，避免重复
        chunk.choices[0].delta.content = None
    return analysis_response, chunk


def _create_summary_state(state: Dict[str, Any], action_input: str) -> Dict[str, Any]:
    """Create a summary state with only the last 2 steps of execution history.

    Args:
        state: The full state dictionary
        action_input: The final answer or action input

    Returns:
        Dict[str, Any]: A simplified state dictionary with only recent history
    """
    return {
        "thoughts": state["thoughts"][-2:] if len(state["thoughts"]) > 2 else state["thoughts"],
        "observations": state["observations"][-2:] if len(state["observations"]) > 2 else state["observations"],
        "actions": state["actions"][-2:] if len(state["actions"]) > 2 else state["actions"],
        "results": state["results"][-2:] if len(state["results"]) > 2 else state["results"],
        "final_answer": action_input,
        "context": {}
    }


class ReactAgent:
    def __init__(self):
        self.model = config.model_name

        # 初始化Jinja2环境
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.template = self.env.get_template("prompts/react_agent.jinja2")
        # 获取模板中的宏
        self.analysis_prompt_macro = self.template.module.analysis_prompt
        self.format_result_prompt_macro = self.template.module.format_result_prompt

    def _create_error_chunk(self, error_msg: str, chunk_id: str = "error") -> ChatCompletionChunk:
        """Create a standardized error chunk for streaming responses.

        Args:
            error_msg: The error message to include in the chunk
            chunk_id: The ID to use for the chunk (defaults to "error")

        Returns:
            ChatCompletionChunk: A standardized error chunk
        """
        return ChatCompletionChunk(
            id=chunk_id,
            choices=[Choice(
                delta=ChoiceDelta(content=f"Error: {error_msg}"),
                finish_reason="stop",
                index=0
            )],
            created=0,
            model=self.model,
            object="chat.completion.chunk"
        )

    async def process(
            self,
            prompt: str,
            mcp_clients: List[MCPClient],
            tools: List[Tool],
            llm_params: Dict[str, Any] = None,
            api_key: str = None
    ) -> Any:
        """Process a prompt using the React pattern."""
        logger.info(f"Number of MCP clients: {len(mcp_clients)}")
        logger.info(f"Available tools: {[tool.name for tool in tools]}")

        tool_details = await get_mcp_tool_details(tools)
        current_date = datetime.now().strftime('%Y年%m月%d日')
        
        # Initialize state for multi-step execution
        state = {
            "thoughts": [],      # 存储每一步的思考过程
            "observations": [],  # 存储每一步的观察结果
            "actions": [],       # 存储每一步的动作
            "results": [],       # 存储每一步的结果
            "final_answer": None,  # 存储最终答案
            "context": {}        # 存储上下文信息，可以是任何类型的数据
        }
        
        # Maximum number of steps to prevent infinite loops
        max_steps = 5
        current_step = 0
        
        # 用于累计所有步骤的 tokens
        total_usage = CompletionUsage(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0
        )

        # 用于存储所有分析响应中的thought
        all_thoughts = []
        
        while current_step < max_steps:
            current_step += 1
            
            # 使用模板渲染分析提示词
            analysis_prompt = self.analysis_prompt_macro(
                prompt=prompt,
                tools=[tool.name for tool in tools],
                tool_details=tool_details,
                messages=llm_params.get('messages', []) if llm_params else [],
                current_date=current_date,
                state=state  # Pass current state to the prompt
            )

            # 调用 LLM 获取分析结果
            analysis_response = await self._call_llm(analysis_prompt, api_key=api_key, **llm_params if llm_params else {})

            if analysis_response and len(analysis_response.choices) > 0 and analysis_response.choices[0].message:
                if hasattr(analysis_response.choices[0].message, 'reasoning_content'):
                    all_thoughts.append(analysis_response.choices[0].message.reasoning_content)
                else:
                    all_thoughts.append(analysis_response.choices[0].message.content)

            # 累加当前步骤的 tokens
            if hasattr(analysis_response, 'usage') and analysis_response.usage:
                total_usage.prompt_tokens += analysis_response.usage.prompt_tokens
                total_usage.completion_tokens += analysis_response.usage.completion_tokens
                total_usage.total_tokens += analysis_response.usage.total_tokens

            try:
                result = json.loads(analysis_response.choices[0].message.content)
                
                # Extract thought, action, and action_input
                thought = result.get("thought", "")
                action = result.get("action", "")
                action_input = result.get("action_input", "")

                # Update state
                state["thoughts"].append(thought)

                if not action:
                    error_msg = "No action found in LLM response"
                    logger.error(f"{error_msg}. Result: {result}")
                    return {"error": error_msg}

                # 特殊处理 final_answer 动作
                if action == "final_answer":
                    state["final_answer"] = action_input
                    # 创建精简的state用于summary
                    summary_state = _create_summary_state(state, action_input)
                    # 使用非流式调用获取格式化结果
                    format_prompt = self.format_result_prompt_macro(
                        action=action,
                        action_input=action_input,
                        result_dict=json.dumps({"final_answer": action_input}, ensure_ascii=False, indent=2),
                        user_question=prompt,
                        user_prompt=config.user_prompt,
                        messages=llm_params.get('messages', []) if llm_params else [],
                        current_date=current_date,
                        state=summary_state  # 使用精简的state
                    )

                    # 使用非流式调用获取最终结果
                    final_response = await self._call_llm(format_prompt, api_key=api_key, **llm_params if llm_params else {})
                    final_response.usage = CompletionUsage(
                        prompt_tokens=total_usage.prompt_tokens,
                        completion_tokens=total_usage.completion_tokens,
                        total_tokens=total_usage.total_tokens
                    )
                    # 将所有thought和最终summary添加到reasoning_content
                    if not hasattr(final_response.choices[0].message, 'reasoning_content'):
                        setattr(final_response.choices[0].message, 'reasoning_content', None)
                    # 添加所有thought
                    reasoning_content = "\n\n".join(filter(None, all_thoughts))
                    # 添加最终summary的reasoning_content
                    if hasattr(final_response.choices[0].message, 'reasoning_content') and final_response.choices[0].message.reasoning_content is not None:
                        reasoning_content += "\n\n" + final_response.choices[0].message.reasoning_content
                    final_response.choices[0].message.reasoning_content = reasoning_content
                    # 添加 references 字段
                    if not hasattr(final_response, 'references'):
                        setattr(final_response, 'references', None)
                    final_response.references = state["results"]
                    return final_response

                # Execute the action
                try:
                    result = await _execute_action(action, action_input, mcp_clients)
                    tool_result_json = json.dumps(result, ensure_ascii=False, indent=2)
                    
                    # Update state with action and result
                    state["actions"].append({"action": action, "input": action_input})
                    state["results"].append(result)
                    state["observations"].append(str(result))
                    
                except Exception as e:
                    error_msg = f"Failed to execute action {action}: {str(e)}"
                    logger.error(error_msg)
                    return {"error": error_msg}

                # 只在最后一次工具调用后格式化结果
                if current_step == max_steps:
                    # 创建精简的state用于summary
                    summary_state = _create_summary_state(state, action_input)
                    # 使用非流式调用获取格式化结果
                    format_prompt = self.format_result_prompt_macro(
                        action=action,
                        action_input=action_input,
                        result_dict=tool_result_json,
                        user_question=prompt,
                        user_prompt=config.user_prompt,
                        messages=llm_params.get('messages', []) if llm_params else [],
                        current_date=current_date,
                        state=summary_state  # 使用精简的state
                    )

                    # 使用非流式调用获取最终结果
                    final_response = await self._call_llm(format_prompt, api_key=api_key, **llm_params if llm_params else {})
                    final_response.usage = CompletionUsage(
                        prompt_tokens=total_usage.prompt_tokens,
                        completion_tokens=total_usage.completion_tokens,
                        total_tokens=total_usage.total_tokens
                    )
                    # 将所有thought和最终summary添加到reasoning_content
                    if not hasattr(final_response.choices[0].message, 'reasoning_content'):
                        setattr(final_response.choices[0].message, 'reasoning_content', None)
                    # 添加所有thought
                    reasoning_content = "\n\n".join(filter(None, all_thoughts))
                    # 添加最终summary的reasoning_content
                    if hasattr(final_response.choices[0].message, 'reasoning_content') and final_response.choices[0].message.reasoning_content is not None:
                        reasoning_content += "\n\n" + final_response.choices[0].message.reasoning_content
                    final_response.choices[0].message.reasoning_content = reasoning_content
                    # 添加 references 字段
                    if not hasattr(final_response, 'references'):
                        setattr(final_response, 'references', None)
                    final_response.references = state["results"]
                    return final_response

            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse JSON from LLM response: {str(e)}"
                logger.error(f"{error_msg}. Response content: {analysis_response.choices[0].message.content}")
                return {"error": error_msg}
            except Exception as e:
                error_msg = f"Unexpected error in process: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {"error": error_msg}

        # If we've reached max steps without a final answer
        if not state["final_answer"]:
            return {"error": "Maximum number of steps reached without reaching a final answer"}

    async def process_stream(
            self,
            prompt: str,
            mcp_clients: List[MCPClient],
            tools: List[Tool],
            llm_params: Dict[str, Any] = None,
            api_key: str = None
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Process a prompt using the React pattern with streaming."""
        logger.info(f"Number of MCP clients: {len(mcp_clients)}")
        logger.info(f"Available tools: {[tool.name for tool in tools]}")

        tool_details = await get_mcp_tool_details(tools)
        current_date = datetime.now().strftime('%Y年%m月%d日')
        
        # Initialize state for multi-step execution
        state = {
            "thoughts": [],      # 存储每一步的思考过程
            "observations": [],  # 存储每一步的观察结果
            "actions": [],       # 存储每一步的动作
            "results": [],       # 存储每一步的结果
            "final_answer": None,  # 存储最终答案
            "context": {}        # 存储上下文信息，可以是任何类型的数据
        }
        
        # Maximum number of steps to prevent infinite loops
        max_steps = 5
        current_step = 0

        previous_usage = CompletionUsage(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0
        )

        while current_step < max_steps:
            current_step += 1
            first_step = current_step == 1
            
            # 使用模板渲染分析提示词
            analysis_prompt = self.analysis_prompt_macro(
                prompt=prompt,
                tools=[tool.name for tool in tools],
                tool_details=tool_details,
                messages=llm_params.get('messages', []) if llm_params else [],
                current_date=current_date,
                state=state  # Pass current state to the prompt
            )

            # 使用流式调用获取分析结果
            analysis_response = ""

            async for chunk in self._call_llm_stream(analysis_prompt, api_key=api_key):
                if not chunk or not chunk.choices or len(chunk.choices) == 0 or not chunk.choices[0].delta:
                    continue

                if chunk and chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].finish_reason:

                    if hasattr(chunk, 'usage') and chunk.usage:
                        chunk_copy = CompletionUsage(
                            prompt_tokens=chunk.usage.prompt_tokens + previous_usage.prompt_tokens,
                            completion_tokens=chunk.usage.completion_tokens + previous_usage.completion_tokens,
                            total_tokens=chunk.usage.total_tokens + previous_usage.total_tokens
                        )
                        previous_usage = chunk_copy

                    if chunk.choices[0].delta.content is not None:
                        analysis_response, chunk = _process_chunk_content(chunk, analysis_response)
                        chunk.choices[0].finish_reason = None
                    else:
                        continue

                if hasattr(chunk, 'usage') and chunk.usage:
                    if first_step:
                        previous_usage = chunk.usage
                    else:
                        chunk.usage.prompt_tokens += previous_usage.prompt_tokens
                        chunk.usage.completion_tokens += previous_usage.completion_tokens
                        chunk.usage.total_tokens += previous_usage.total_tokens

                analysis_response, chunk = _process_chunk_content(chunk, analysis_response)
                yield chunk

            matched_json = extract_json_from_response(analysis_response)

            try:
                if not matched_json:
                    error_msg = "Failed to find valid JSON response in LLM output"
                    logger.error(f"{error_msg}. Analysis response: {analysis_response}")
                    yield self._create_error_chunk(error_msg)
                    return

                try:
                    result = json.loads(matched_json)
                except json.JSONDecodeError as e:
                    error_msg = f"Failed to parse JSON from LLM response: {str(e)}"
                    logger.error(f"{error_msg}. JSON string: {matched_json}")
                    yield self._create_error_chunk(error_msg)
                    return

                # Extract thought, action, and action_input
                thought = result.get("thought", "")
                action = result.get("action", "")
                action_input = result.get("action_input", "")

                # Update state
                state["thoughts"].append(thought)

                if not action:
                    error_msg = "No action found in LLM response"
                    logger.error(f"{error_msg}. Result: {result}")
                    yield self._create_error_chunk(error_msg)
                    return

                # 特殊处理 final_answer 动作
                if action == "final_answer":
                    state["final_answer"] = action_input
                    # 创建精简的state用于summary
                    summary_state = _create_summary_state(state, action_input)
                    # 使用非流式调用获取格式化结果
                    format_prompt = self.format_result_prompt_macro(
                        action=action,
                        action_input=action_input,
                        result_dict=json.dumps({"final_answer": action_input}, ensure_ascii=False, indent=2),
                        user_question=prompt,
                        user_prompt=config.user_prompt,
                        messages=llm_params.get('messages', []) if llm_params else [],
                        current_date=current_date,
                        state=summary_state  # 使用精简的state
                    )

                    async for chunk in self._handle_streaming_response(
                        format_prompt, api_key, llm_params
                    ):
                        if hasattr(chunk, 'usage') and chunk.usage:
                            if first_step:
                                previous_usage = chunk.usage
                            else:
                                chunk.usage.prompt_tokens += previous_usage.prompt_tokens
                                chunk.usage.completion_tokens += previous_usage.completion_tokens
                                chunk.usage.total_tokens += previous_usage.total_tokens
                        
                        # 在最后一个chunk添加 references 字段
                        if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].finish_reason == "stop":
                            if not hasattr(chunk, 'references'):
                                setattr(chunk, 'references', None)
                            chunk.references = state["results"]
                        
                        yield chunk
                    return

                # Execute the action
                try:
                    result = await _execute_action(action, action_input, mcp_clients)
                    tool_result_json = json.dumps(result, ensure_ascii=False, indent=2)
                    
                    # Update state with action and result
                    state["actions"].append({"action": action, "input": action_input})
                    state["results"].append(result)
                    state["observations"].append(str(result))
                    
                except Exception as e:
                    error_msg = f"Failed to execute action {action}: {str(e)}"
                    logger.error(error_msg)
                    yield self._create_error_chunk(error_msg)
                    return

                # 只在最后一次工具调用后格式化结果
                if current_step == max_steps:
                    # 创建精简的state用于summary
                    summary_state = _create_summary_state(state, action_input)
                    # 使用流式调用获取格式化结果
                    format_prompt = self.format_result_prompt_macro(
                        action=action,
                        action_input=action_input,
                        result_dict=tool_result_json,
                        user_question=prompt,
                        user_prompt=config.user_prompt,
                        messages=llm_params.get('messages', []) if llm_params else [],
                        current_date=current_date,
                        state=summary_state  # 使用精简的state
                    )
                    logger.info(f"format_prompt: {format_prompt}")

                    async for chunk in self._handle_streaming_response(
                        format_prompt, api_key, llm_params
                    ):
                        if hasattr(chunk, 'usage') and chunk.usage:
                            if first_step:
                                previous_usage = chunk.usage
                            else:
                                chunk.usage.prompt_tokens += previous_usage.prompt_tokens
                                chunk.usage.completion_tokens += previous_usage.completion_tokens
                                chunk.usage.total_tokens += previous_usage.total_tokens
                        
                        # 在最后一个chunk添加 references 字段
                        if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].finish_reason == "stop":
                            if not hasattr(chunk, 'references'):
                                setattr(chunk, 'references', None)
                            chunk.references = state["results"]
                        
                        yield chunk

            except Exception as e:
                error_msg = f"Unexpected error in process_stream: {str(e)}"
                logger.error(error_msg, exc_info=True)
                yield self._create_error_chunk(error_msg)
                return

        # If we've reached max steps without a final answer
        if not state["final_answer"]:
            yield self._create_error_chunk("Maximum number of steps reached without reaching a final answer")

    async def _call_llm(self, prompt: str, api_key: str = None, **kwargs) -> Any:
        """Call the LLM with a prompt.

        Args:
            prompt: The prompt to send to the LLM
            api_key: The API key to use for authentication
            **kwargs: Additional parameters to pass to the OpenAI API, such as:
                - max_tokens: Maximum number of tokens to generate
                - top_p: Nucleus sampling parameter
                - frequency_penalty: Penalty for token frequency
                - presence_penalty: Penalty for token presence
                - stop: Stop sequences
                - etc.
        """
        try:
            kwargs = await get_messages(prompt, **kwargs)

            response = await _get_client(api_key).chat.completions.create(
                model=self.model,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise

    async def _call_llm_stream(self, prompt: str, api_key: str = None, **kwargs) -> AsyncGenerator[
        ChatCompletionChunk, None]:
        """Call the LLM with a prompt and stream the response.

        Args:
            prompt: The prompt to send to the LLM
            api_key: The API key to use for authentication
            **kwargs: Additional parameters to pass to the OpenAI API, such as:
                - max_tokens: Maximum number of tokens to generate
                - top_p: Nucleus sampling parameter
                - frequency_penalty: Penalty for token frequency
                - presence_penalty: Penalty for token presence
                - stop: Stop sequences
                - etc.
        """
        try:
            kwargs = await get_messages(prompt, **kwargs)

            if "stream" not in kwargs:
                kwargs["stream"] = True

            stream = await _get_client(api_key).chat.completions.create(
                model=self.model,
                **kwargs
            )

            async for chunk in stream:
                yield chunk

        except Exception as e:
            logger.error(f"Error calling LLM with streaming: {str(e)}")
            yield self._create_error_chunk(str(e))

    async def _handle_streaming_response(self, format_prompt: str, api_key: str, llm_params: Dict[str, Any]) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Handle streaming response from LLM.
        
        Args:
            format_prompt: The prompt for formatting the result
            api_key: The API key for LLM
            llm_params: Parameters for LLM
            
        Yields:
            ChatCompletionChunk: Chunks of the formatted response
        """
        try:
            async for chunk in self._call_llm_stream(format_prompt, api_key, **llm_params):
                yield chunk
        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            yield self._create_error_chunk(str(e))

