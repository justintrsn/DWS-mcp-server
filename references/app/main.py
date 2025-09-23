from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

import uvicorn
from app.api.routes import router
from app.core.globals import chat_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    logger.info("Initializing services...")
    await chat_service.initialize_mcp_clients()
    yield
    # Shutdown
    logger.info("Shutting down services...")

app = FastAPI(
    title="MCP Agent API",
    description="API for MCP Agent with OpenAI-compatible interface",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/{bot_name}/{agent_name}/v1")


@app.get("/")
async def root():
    return {"message": "Welcome to MAAS Agent"}


if __name__ == '__main__':
    uvicorn.run(app, port=8000)