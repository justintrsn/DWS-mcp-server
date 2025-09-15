# Implementation Plan: PostgreSQL MCP Server

**Branch**: `003-add-in-feature` | **Date**: 2025-09-12 | **Spec**: [link](spec.md)
**Input**: Feature specification from `/specs/003-add-in-feature/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → Feature spec loaded successfully
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Project Type: Single project (MCP server library)
   → Structure Decision: Option 1 (single project structure)
3. Evaluate Constitution Check section below
   → No violations detected, proceeding with simple approach
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → Researching FastMCP framework, psycopg2 patterns, connection pooling
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, CLAUDE.md
6. Re-evaluate Constitution Check section
   → Design maintains simplicity
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Task generation approach defined
8. STOP - Ready for /tasks command
```

## Summary
PostgreSQL MCP server providing database operations through standardized tools with connection pooling for 5 concurrent clients, rate limiting (10 req/min), and comprehensive error handling with retry guidance.

## Technical Context
**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastMCP, psycopg2, python-dotenv, uvicorn, fastapi  
**Storage**: PostgreSQL database (external)  
**Testing**: pytest, pytest-asyncio  
**Target Platform**: Linux/macOS/Windows server  
**Project Type**: single - MCP server with dual transport and API service  
**Performance Goals**: Handle 5 concurrent clients, 10 req/min per client  
**Constraints**: <30s query timeout, 10 connection pool limit, 15 request queue  
**Scale/Scope**: MCP server (stdio/SSE), 3 main tools, separate health API  
**Transport Modes**: stdio (CLI), SSE (HTTP streaming)

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 1 (mcp-server)
- Using framework directly? Yes (FastMCP, psycopg2 without wrappers)
- Single data model? Yes (direct database operations)
- Avoiding patterns? Yes (no unnecessary abstractions)

**Architecture**:
- EVERY feature as library? Yes (MCP server as library)
- Libraries listed: postgresql-mcp (database operations via MCP tools)
- CLI per library: mcp-server with --help/--version/--format
- Library docs: llms.txt format planned? Yes

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? Yes
- Git commits show tests before implementation? Yes
- Order: Contract→Integration→E2E→Unit strictly followed? Yes
- Real dependencies used? Yes (actual PostgreSQL database)
- Integration tests for: new libraries, contract changes, shared schemas? Yes
- FORBIDDEN: Implementation before test, skipping RED phase

**Observability**:
- Structured logging included? Yes
- Frontend logs → backend? N/A (server only)
- Error context sufficient? Yes (detailed error responses)

**Versioning**:
- Version number assigned? 1.0.0
- BUILD increments on every change? Yes
- Breaking changes handled? N/A (first version)

## Project Structure

### Documentation (this feature)
```
specs/003-add-in-feature/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project with dual transport (DEFAULT)
src/
├── models/
│   ├── connection_pool.py
│   ├── rate_limiter.py
│   └── error_types.py
├── services/
│   ├── database_service.py
│   ├── query_builder.py
│   └── health_api.py        # Separate HTTP API service
├── transport/
│   ├── stdio_server.py      # stdio transport mode
│   └── sse_server.py        # SSE transport mode
├── cli/
│   └── mcp_server.py        # Entry point with transport selection
└── lib/
    └── mcp_tools.py

tests/
├── contract/
│   └── test_mcp_tools.py
├── integration/
│   ├── test_connection_pool.py
│   ├── test_rate_limiting.py
│   ├── test_stdio_transport.py
│   ├── test_sse_transport.py
│   └── test_health_api.py
└── unit/
    └── test_query_builder.py
```

**Structure Decision**: Option 1 - Single project structure for MCP server library

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - FastMCP framework best practices for tool implementation
   - psycopg2 connection pooling strategies
   - Rate limiting implementation patterns
   - MCP protocol error handling standards

2. **Generate and dispatch research agents**:
   ```
   Task: "Research FastMCP framework for implementing MCP tools"
   Task: "Find best practices for psycopg2 connection pooling"
   Task: "Research rate limiting patterns for Python servers"
   Task: "Study MCP protocol error response standards"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all technical decisions documented

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - ConnectionPool: max_connections, active_connections, queue
   - ClientSession: client_id, request_count, window_start
   - ErrorResponse: code, message, retryable, details
   - QueryRequest: table, columns, filters, limit

2. **Generate API contracts** from functional requirements:
   - Tool: get_metadata → returns tables and columns
   - Tool: select_data → returns filtered data with limits
   - Tool: execute_filter → applies complex filters safely
   - Output MCP tool schemas to `/contracts/`

3. **Generate contract tests** from contracts:
   - test_get_metadata_contract.py
   - test_select_data_contract.py
   - test_execute_filter_contract.py
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Concurrent client handling scenario
   - Rate limiting enforcement scenario
   - Error recovery scenario
   - Query timeout scenario

5. **Update agent file incrementally**:
   - Add PostgreSQL MCP server context
   - Include connection pooling patterns
   - Document error handling approach
   - Output to CLAUDE.md

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, CLAUDE.md

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs
- Each MCP tool → contract test task [P]
- Each entity → model creation task [P]
- Each acceptance scenario → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation
- Dependency order: Models → Services → Tools → CLI
- Mark [P] for parallel execution

**Estimated Output**: 20-25 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*No violations - maintaining simplicity*

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none needed)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*