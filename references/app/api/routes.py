import json
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.core.config import config
from app.core.exceptions import MCPServerError
from app.core.globals import chat_service

router = APIRouter()

def to_bool(value):
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)

@router.post("/chat/completions")
async def create_chat_completion(request: Request):
    try:
        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]  # Remove "Bearer " prefix
        else:
            raise HTTPException(status_code=401, detail="Invalid or missing Authorization header")

        # Parse the request body
        body = await request.json()

        # 去除请求体中带的 model 参数
        body.pop("model")

        # Get sampling config from config instance
        sampling_config = config.sampling_config
        
        # Initialize extra_body if not exists
        if "extra_body" not in body:
            body["extra_body"] = {}
        
        # Merge sampling config with user input
        for key in ["temperature", "top_p"]:
            if key not in body:
                if key in sampling_config:
                    body[key] = sampling_config[key]
        
        # Handle top_k separately in extra_body
        if "top_k" not in body.get("extra_body", {}):
            if "top_k" in sampling_config:
                body["extra_body"]["top_k"] = sampling_config["top_k"]

        stream = to_bool(body.get("stream", False))
        body["stream"] = stream

        if stream:
            return await create_streaming_chat_completion(body, api_key)
        else:
            return await create_regular_chat_completion(body, api_key)
            
    except MCPServerError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def create_streaming_chat_completion(body: Dict[str, Any], api_key: str):
    async def event_generator():
        try:
            async for chunk in chat_service.process_chat_completion_stream(body, api_key):
                if isinstance(chunk, dict) and "error" in chunk:
                    error_chunk = {
                        "id": "error",
                        "choices": [{
                            "delta": {"content": f"Error: {chunk['error']}"},
                            "finish_reason": "stop",
                            "index": 0
                        }],
                        "created": 0,
                        "model": chat_service.model,
                        "object": "chat.completion.chunk"
                    }
                    yield json.dumps(error_chunk, ensure_ascii=False)
                    return
                chunk_dict = chunk.model_dump()
                result = json.dumps(chunk_dict, ensure_ascii=False)
                yield result
        except Exception as e:
            error_chunk = {
                "id": "error",
                "choices": [{
                    "delta": {"content": f"Error: {str(e)}"},
                    "finish_reason": "stop",
                    "index": 0
                }],
                "created": 0,
                "model": chat_service.model,
                "object": "chat.completion.chunk"
            }
            yield json.dumps(error_chunk, ensure_ascii=False)
        finally:
            yield "[DONE]"

    return EventSourceResponse(event_generator())

async def create_regular_chat_completion(body: Dict[str, Any], api_key: str):
    response = await chat_service.process_chat_completion(body, api_key)
    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])
    return response