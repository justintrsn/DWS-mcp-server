# Tasks: PostgreSQL MCP Server (MVP - Metadata Only)

**Input**: Design documents from `/specs/003-add-in-feature/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## MVP Scope
Building a minimal MCP server with 1-3 tools focused on database metadata viewing:
- `get_tables`: List all tables in the database
- `get_columns`: Get column information for a specific table
- `get_table_stats`: Get row count and size statistics

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- All paths shown are relative to repository root

## Phase 3.1: Setup
- [x] T001 Create project structure: src/{models,services,lib}, tests/{contract,integration,unit}
- [x] T002 Create requirements.txt with: fastmcp>=0.1.0, psycopg2-binary>=2.9.0, python-dotenv>=1.0.0, pytest>=7.0.0, pytest-asyncio>=0.21.0, uvicorn>=0.20.0, fastapi>=0.100.0
- [x] T003 Create .env.example with DB_HOST, DB_PORT, DB_DATABASE, DB_USER, DB_PASSWORD placeholders
- [x] T004 Create .env file with DWS credentials: host=124.243.149.239, port=8000, database=footfall, user=dbadmin, password in environment variable
- [x] T005 [P] Modify the .gitignore to exclude .env, __pycache__, *.pyc, .pytest_cache/
- [x] T006 [P] Create docker-compose.test.yml for local PostgreSQL test database

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [x] T007 [P] Contract test for get_tables tool in tests/contract/test_get_tables.py - verify returns list of table names
- [x] T008 [P] Contract test for get_columns tool in tests/contract/test_get_columns.py - verify returns column details with types
- [x] T009 [P] Contract test for get_table_stats tool in tests/contract/test_get_table_stats.py - verify returns row count and size
- [x] T010 [P] Integration test database connection in tests/integration/test_connection.py - verify can connect with .env credentials
- [x] T011 [P] Integration test error handling in tests/integration/test_errors.py - verify proper error responses for invalid table names

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [x] T012 [P] Create error types in src/models/error_types.py: MCPError base class, InvalidTableError, ConnectionError
- [x] T013 [P] Create database config in src/models/config.py: load and validate environment variables
- [x] T014 Database service in src/services/database_service.py: connection management, query execution with psycopg2
- [x] T015 [P] Query utilities in src/services/query_utils.py: table name validation, SQL injection prevention
- [x] T016 MCP tool: get_tables in src/lib/mcp_tools.py - query information_schema.tables
- [x] T017 MCP tool: get_columns in src/lib/mcp_tools.py - query information_schema.columns with data types
- [x] T018 MCP tool: get_table_stats in src/lib/mcp_tools.py - query pg_stat_user_tables for row counts
- [x] T019 MCP server initialization in src/cli/mcp_server.py: FastMCP setup, tool registration, main entry point

## Phase 3.4: Transport & API Implementation
- [x] T020 Create stdio transport in src/transport/stdio_server.py: standard input/output mode for CLI
- [x] T021 Create SSE transport in src/transport/sse_server.py: Server-Sent Events for HTTP streaming
- [x] T022 Create health API service in src/services/health_api.py: FastAPI service with /health endpoints
- [x] T023 Update mcp_server.py to support --transport flag (stdio|sse) and concurrent health API
- [x] T024 Integration test for stdio transport in tests/integration/test_stdio_transport.py
- [x] T025 Integration test for SSE transport in tests/integration/test_sse_transport.py
- [x] T026 Integration test for health API in tests/integration/test_health_api.py

## Phase 3.5: Integration & Polish
- [x] T027 Wire database service to MCP tools: dependency injection in mcp_server.py
- [x] T028 Add structured logging with JSON formatter in src/lib/logging_config.py
- [x] T029 Add graceful shutdown handling for database connections and health API
- [x] T030 [P] Unit tests for query utilities in tests/unit/test_query_utils.py
- [x] T031 [P] Unit tests for config validation in tests/unit/test_config.py
- [x] T032 Create README.md with setup instructions, transport modes, and health API documentation
- [x] T033 Create run.py entry point script with transport selection and health API startup
- [x] T034 Manual testing checklist: test both transports, health endpoints, all MCP tools

## Phase 3.6: SSE Transport Fix & OpenAI Integration (2025-09-12)
- [x] T035 Fix SSE transport to use FastMCP's built-in SSE instead of custom implementation
- [x] T036 Add OpenAI configuration to .env and .env.example (API key and model)
- [x] T037 Update requirements.txt to include openai>=1.0.0
- [x] T038 Fill in all __init__.py files with proper module exports to fix VS Code imports
- [x] T039 Create test_openai_simple.py for basic OpenAI integration testing
- [x] T040 Create test_mcp_sse_client.py using proper MCP client library for SSE
- [x] T041 Verify FastMCP SSE transport works at /sse endpoint (not /mcp/v1/sse)
- [x] T042 Document that SSE requires MCP client library, not direct HTTP requests

## Dependencies
- Setup (T001-T006) must complete first
- Tests (T007-T011) before implementation (T012-T019)
- T013 (config) blocks T014 (database service)
- T014 (database service) blocks T016-T018 (MCP tools)
- T016-T018 (tools) block T019 (server)
- Core implementation (T012-T019) before transport/API (T020-T026)
- Transport/API implementation before integration (T027-T029)
- Everything before polish (T030-T034)

## Parallel Execution Examples

### Launch all contract tests together (after setup):
```
Task: "Contract test for get_tables tool in tests/contract/test_get_tables.py"
Task: "Contract test for get_columns tool in tests/contract/test_get_columns.py"
Task: "Contract test for get_table_stats tool in tests/contract/test_get_table_stats.py"
Task: "Integration test database connection in tests/integration/test_connection.py"
Task: "Integration test error handling in tests/integration/test_errors.py"
```

### Launch independent models together:
```
Task: "Create error types in src/models/error_types.py"
Task: "Create database config in src/models/config.py"
Task: "Query utilities in src/services/query_utils.py"
```

### Launch unit tests together (end of development):
```
Task: "Unit tests for query utilities in tests/unit/test_query_utils.py"
Task: "Unit tests for config validation in tests/unit/test_config.py"
```

## Implementation Notes

### Key Simplifications for MVP
1. **No connection pooling** - single connection for simplicity
2. **No rate limiting** - add in future iteration
3. **No caching** - direct queries every time
4. **Read-only operations** - metadata viewing only
5. **Basic error handling** - just invalid table names and connection errors

### Test Database Setup
For local testing without affecting DWS:
```yaml
# docker-compose.test.yml
services:
  postgres-test:
    image: postgres:15
    environment:
      POSTGRES_DB: test_footfall
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    ports:
      - "5433:5432"
```

## Success Criteria
- [x] Can connect to DWS database using .env credentials
- [x] list_tables returns list of all tables in footfall database
- [x] describe_table returns accurate column information with data types
- [x] table_statistics returns row counts for tables
- [x] Proper error messages for invalid table names
- [x] All tests pass with real DWS connection
- [x] Server runs and responds to MCP requests
- [x] SSE transport works with FastMCP's built-in implementation
- [x] OpenAI can analyze database structure via integration
- [x] MCP client library can connect and execute tools via SSE

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Keep MVP scope minimal - just metadata viewing
- Security: Credentials in .env, never in code
- Use parameterized queries to prevent SQL injection

## Key Learnings (2025-09-12)
- FastMCP has built-in SSE transport that should be used instead of custom implementation
- SSE (Server-Sent Events) requires specialized client handling via MCP client library
- Direct HTTP POST requests don't work with SSE - need proper event stream handling
- The SSE endpoint is at `/sse` not `/mcp/v1/sse` when using FastMCP
- All __init__.py files should export modules to fix VS Code import resolution
- OpenAI integration works well for analyzing database structures

## Validation Checklist
- [x] All tools have corresponding contract tests
- [x] Config and error models defined
- [x] All tests come before implementation
- [x] Parallel tasks truly independent
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task
- [x] DWS credentials properly secured in .env