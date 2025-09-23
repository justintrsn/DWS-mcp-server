# Claude Code Context - PostgreSQL MCP Server

## Project Overview
PostgreSQL MCP (Model Context Protocol) server providing safe database operations through standardized tools with connection pooling, rate limiting, and comprehensive error handling.

## Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastMCP (MCP protocol implementation), FastAPI
- **Database**: PostgreSQL via psycopg2
- **LLM Providers**: OpenAI (gpt-4o), Huawei MaaS (OpenAI-compatible)
- **Async**: asyncio, httpx, aiohttp
- **Testing**: pytest with Docker PostgreSQL
- **Configuration**: python-dotenv for environment variables

## Key Components

### MCP Tools
1. **get_metadata**: Retrieve database schema information
2. **select_data**: Query data with column/row limits
3. **execute_filter**: Apply safe filtered queries

### Core Features
- Connection pooling (10 max connections)
- Rate limiting (10 requests/minute per client)
- Query timeout (30 seconds max)
- Structured error responses with retry guidance
- Read-only database access for security

## Project Structure
```
src/
├── models/          # Data models (query, session, tool invocation)
├── services/        # Business logic (LLM, MCP, middleware)
├── cli/            # CLI tools for testing
├── lib/            # Core libraries
│   ├── transport/  # MCP transport abstractions (stdio, SSE)
│   └── providers/  # LLM provider abstractions
└── api/            # FastAPI endpoints

tests/
├── contract/       # API contract tests
├── integration/    # E2E tests with real services
└── unit/          # Component unit tests
```

## Development Workflow

### Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Configure database credentials in .env
```

### Testing
```bash
# Run tests with Docker PostgreSQL
docker-compose -f docker-compose.test.yml up -d
pytest

# Check specific components
pytest tests/integration/test_connection_pool.py
```

### Running
```bash
# MCP Server
python -m src.cli.mcp_server --transport sse --port 3000

# Middleware API
python -m src.api.main

# Test E2E
python -m src.cli.middleware --test-e2e --query "List tables"
```

## Key Patterns

### Connection Pooling
- Uses psycopg2 ThreadedConnectionPool
- Maintains 2-10 connections
- Queue overflow returns busy error

### Rate Limiting  
- Token bucket algorithm
- Per-client tracking
- Sliding window (60 seconds)

### Error Handling
- Recoverable: Connection issues, rate limits, timeouts
- Non-recoverable: Invalid queries, auth failures
- All errors include actionable guidance

## Common Tasks

### Add New MCP Tool
1. Define tool schema in `contracts/mcp-tools.json`
2. Create contract test in `tests/contract/`
3. Implement tool in `src/lib/mcp_tools.py`
4. Add integration test in `tests/integration/`

### Debug Connection Issues
1. Check logs: `tail -f logs/mcp-server.log`
2. Verify pool status: `/health` endpoint
3. Monitor database: `SELECT * FROM pg_stat_activity`

### Optimize Performance
1. Add database indexes for filtered columns
2. Use column selection instead of `SELECT *`
3. Implement query result caching if needed

## Testing Guidelines
- TDD: Write failing tests first
- Use real PostgreSQL in Docker
- Test error conditions explicitly
- Verify rate limiting behavior

## Security Considerations
- Database user has SELECT-only permissions
- All identifiers validated with regex
- Parameterized queries prevent injection
- No DDL operations allowed

## Recent Changes
- Added OpenAI-Compatible MCP Middleware (002)
- LLM provider abstraction (OpenAI/Huawei MaaS)
- Transport abstraction layer (stdio/SSE)
- API endpoints for query processing

---
*Generated for PostgreSQL MCP Server v1.0.0*