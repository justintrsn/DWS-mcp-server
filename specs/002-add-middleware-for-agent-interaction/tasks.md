# Implementation Tasks: OpenAI-Compatible MCP Middleware

**Feature**: OpenAI-Compatible MCP Middleware for Agent Interaction
**Priority**: Ship core functionality first, test with real services
**Approach**: Implementation-first for rapid delivery, integration tests only

## Task Overview
Total tasks: 25
Parallel groups: 3 groups of concurrent tasks
Estimated time: 2-3 days

## Phase 1: Core Infrastructure (T001-T005)

### T001: Create Base Project Structure
**File**: Multiple directories
**Action**: Create the directory structure and __init__.py files
```bash
mkdir -p src/lib/transport src/lib/providers src/models src/services src/api src/cli
touch src/lib/transport/__init__.py src/lib/providers/__init__.py
touch src/models/__init__.py src/services/__init__.py src/api/__init__.py
```

### T002: Install Core Dependencies
**File**: requirements.txt (append)
**Action**: Add new dependencies to requirements.txt
```
# Add to existing requirements.txt:
openai>=1.0.0
httpx>=0.24.0
aiohttp>=3.9.0
fastapi>=0.100.0
uvicorn>=0.23.0
```

### T003: Create Environment Configuration
**File**: .env.example (append)
**Action**: Add new environment variables
```bash
# LLM Configuration
LLM_PROVIDER=openai  # or huawei_maas
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Huawei MaaS Configuration
MAAS_API_URL=https://...
MAAS_API_KEY=...
MAAS_MODEL_NAME=...

# MCP Configuration
MCP_TRANSPORT=sse  # or stdio
MCP_SERVER_URL=http://localhost:3000/sse

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_TOKEN=your-bearer-token
```

### T004: Core Data Models [P]
**File**: src/models/core.py
**Action**: Create all data models from data-model.md
- Query, AIResponse, MCPConnection, ToolInvocation, Session, MCPTool
- Use Pydantic for validation
- Reference: specs/002-add-middleware-for-agent-interaction/data-model.md

### T005: Configuration Loader [P]
**File**: src/services/config.py
**Action**: Create configuration management
- Load environment variables
- Validate required settings
- Provider selection logic
- Default values

## Phase 2: Transport Layer (T006-T009)

### T006: Transport Base Interface [P]
**File**: src/lib/transport/base.py
**Action**: Create abstract base class for transports
```python
from abc import ABC, abstractmethod
class MCPTransport(ABC):
    @abstractmethod
    async def connect(self): pass
    @abstractmethod
    async def call_tool(self, name, args): pass
    @abstractmethod
    async def list_tools(self): pass
```

### T007: SSE Transport Implementation
**File**: src/lib/transport/sse.py
**Action**: Implement SSE transport using mcp.client.sse
- Reference: test_mcp_client.py lines 66-133
- Connection management
- Tool discovery
- Tool invocation

### T008: STDIO Transport Implementation
**File**: src/lib/transport/stdio.py
**Action**: Implement STDIO transport using mcp.client.stdio
- Reference: test_mcp_client.py lines 77-91
- Process management
- Tool discovery
- Tool invocation

### T009: Transport Manager
**File**: src/lib/transport/manager.py
**Action**: Create transport selection and management
- Runtime transport selection
- Connection pooling for SSE
- Error handling and retry logic

## Phase 3: LLM Provider Layer (T010-T013)

### T010: Provider Base Interface [P]
**File**: src/lib/providers/base.py
**Action**: Create abstract base class for LLM providers
```python
from abc import ABC, abstractmethod
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages, tools): pass
    @abstractmethod
    async def validate_config(self): pass
```

### T011: OpenAI Provider Implementation
**File**: src/lib/providers/openai_provider.py
**Action**: Implement OpenAI provider
- Reference: test_mcp_client.py lines 485-602 (process_query)
- Tool formatting for OpenAI
- Function calling handling
- Response processing

### T012: Huawei MaaS Provider Implementation
**File**: src/lib/providers/huawei_maas_provider.py
**Action**: Implement Huawei MaaS provider (OpenAI-compatible)
- Reference: references/app/services/chat_service.py
- Use OpenAI client with custom base_url
- Configuration from MAAS_* env vars

### T013: Provider Manager
**File**: src/lib/providers/manager.py
**Action**: Create provider selection and management
- Runtime provider selection
- Configuration validation
- Fallback logic

## Phase 4: Core Services (T014-T017)

### T014: MCP Service
**File**: src/services/mcp_service.py
**Action**: Create MCP tool management service
- Tool discovery and caching
- Tool invocation with timeout
- Connection management via transport manager
- Error handling

### T015: LLM Service
**File**: src/services/llm_service.py
**Action**: Create LLM orchestration service
- Message formatting
- Tool call handling
- Provider selection via manager
- Session context management

### T016: Middleware Pipeline
**File**: src/services/middleware.py
**Action**: Create query processing pipeline
- Query validation
- Rate limiting (token bucket)
- LLM + MCP coordination
- Response formatting
- Reference: research.md for patterns

### T017: Session Manager
**File**: src/services/session_manager.py
**Action**: Create session management
- In-memory session storage
- Message history management
- Context pruning
- TTL handling

## Phase 5: API Implementation (T018-T020)

### T018: FastAPI Application Setup
**File**: src/api/main.py
**Action**: Create FastAPI application
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MCP Middleware API")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.on_event("startup")
async def startup():
    # Initialize services
    pass
```

### T019: Query Endpoint
**File**: src/api/endpoints.py
**Action**: Implement /api/query endpoint
- Reference: contracts/openapi.yaml
- Request validation
- Bearer token auth
- Rate limit headers
- Call middleware pipeline

### T020: Support Endpoints [P]
**File**: src/api/endpoints.py (append)
**Action**: Implement remaining endpoints
- GET /api/health
- GET /api/tools
- POST /api/session
- GET /api/session/{id}

## Phase 6: CLI Tools (T021-T023)

### T021: MCP Client CLI [P]
**File**: src/cli/mcp_client.py
**Action**: Create MCP testing CLI
```python
# Commands:
# --list-tools: List available MCP tools
# --test-connection: Test MCP connection
# --call-tool TOOL_NAME: Call specific tool
```

### T022: LLM Test CLI [P]
**File**: src/cli/llm_test.py
**Action**: Create LLM provider testing CLI
```python
# Commands:
# --provider openai/huawei_maas
# --query "test query"
# --validate-config: Check provider configuration
```

### T023: E2E Test CLI [P]
**File**: src/cli/middleware.py
**Action**: Create end-to-end testing CLI
```python
# Commands:
# --test-e2e: Run full pipeline test
# --query "natural language query"
# --transport stdio/sse
# --provider openai/huawei_maas
```

## Phase 7: Integration Testing (T024-T025)

### T024: Real Service Integration Test
**File**: tests/integration/test_real_services.py
**Action**: Create integration test with real services
```python
# Test scenarios from quickstart.md:
# 1. Query with OpenAI → SSE transport → PostgreSQL
# 2. Query with Huawei MaaS → STDIO transport → PostgreSQL
# 3. Session management with follow-up queries
# 4. Rate limiting behavior
# 5. Error handling scenarios
```

### T025: E2E Validation Script
**File**: scripts/validate_e2e.sh
**Action**: Create validation script
```bash
#!/bin/bash
# Start MCP server
# Start middleware API
# Run test queries from quickstart.md
# Verify responses
# Test both providers and transports
```

## Parallel Execution Examples

### Group 1: After T003 completes
```bash
# Can run simultaneously:
Task T004: Create data models
Task T005: Create configuration loader
Task T006: Create transport base interface
Task T010: Create provider base interface
```

### Group 2: After transport/provider bases complete
```bash
# Can run simultaneously:
Task T007: SSE transport
Task T008: STDIO transport
Task T011: OpenAI provider
Task T012: Huawei MaaS provider
```

### Group 3: CLI tools can be developed in parallel
```bash
# Can run simultaneously after services complete:
Task T021: MCP Client CLI
Task T022: LLM Test CLI
Task T023: E2E Test CLI
```

## Execution Order

1. **Setup** (T001-T003): Sequential, foundational
2. **Core Models** (T004-T005): Parallel [P]
3. **Base Interfaces** (T006, T010): Parallel [P]
4. **Implementations** (T007-T009, T011-T013): Parallel within each layer
5. **Services** (T014-T017): Sequential (dependencies)
6. **API** (T018-T020): T018 first, then T019-T020 parallel [P]
7. **CLIs** (T021-T023): All parallel [P]
8. **Testing** (T024-T025): After everything else

## Quick Start Commands

```bash
# After T001-T003:
python -m pip install -r requirements.txt

# After T018-T020:
python -m src.api.main  # Start API server

# After T021-T023:
python -m src.cli.mcp_client --list-tools
python -m src.cli.llm_test --provider openai --query "test"
python -m src.cli.middleware --test-e2e

# After T024-T025:
./scripts/validate_e2e.sh
```

## Success Criteria

- [ ] API server starts without errors
- [ ] Can query with OpenAI and get MCP tool results
- [ ] Can query with Huawei MaaS and get MCP tool results
- [ ] Both STDIO and SSE transports work
- [ ] Rate limiting enforces 10 req/min
- [ ] All quickstart.md examples work

---
*Focus: Ship working middleware quickly. Unit tests and polish in future iteration.*