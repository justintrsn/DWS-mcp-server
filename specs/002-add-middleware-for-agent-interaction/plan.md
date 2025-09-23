# Implementation Plan: OpenAI-Compatible MCP Middleware for Agent Interaction

**Branch**: `002-add-middleware-for-agent-interaction` | **Date**: 2025-09-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-add-middleware-for-agent-interaction/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → Found and loaded specification
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → All clarifications resolved in spec
   → Detect Project Type: Single project (API with libraries)
   → Set Structure Decision: Option 1 (Single project)
3. Evaluate Constitution Check section below
   → No violations detected
   → Update Progress Tracking: Initial Constitution Check PASS
4. Execute Phase 0 → research.md
   → Research completed successfully
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, CLAUDE.md
6. Re-evaluate Constitution Check section
   → No new violations
   → Update Progress Tracking: Post-Design Constitution Check PASS
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Create a middleware that enables LLM models (OpenAI gpt-4o and Huawei MaaS) to interact with PostgreSQL MCP tools through both stdio and SSE transport protocols. The system will accept natural language queries, process them through the selected LLM provider, execute appropriate MCP tools, and return comprehensive responses. Implementation will follow abstraction patterns for both LLM providers and MCP transports, enabling runtime switching and configuration through environment variables.

## Technical Context
**Language/Version**: Python 3.11 (based on existing codebase)
**Primary Dependencies**: FastMCP, OpenAI SDK, psycopg2, httpx, asyncio, python-dotenv
**Storage**: PostgreSQL (via MCP tools, read-only access)
**Testing**: pytest with Docker PostgreSQL
**Target Platform**: Linux server
**Project Type**: single - API server with library components
**Performance Goals**: 10 requests/minute rate limit, 10 concurrent requests max
**Constraints**: <30s timeout per tool execution, <60s total request timeout
**Scale/Scope**: MVP supporting 2 LLM providers, 2 transport modes, ~10 MCP tools

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 1 (API with libraries)
- Using framework directly? Yes (FastAPI, FastMCP)
- Single data model? Yes (shared entities)
- Avoiding patterns? Yes (direct implementation)

**Architecture**:
- EVERY feature as library? Yes
- Libraries listed:
  - `mcp_client`: MCP connection management and tool invocation
  - `llm_providers`: LLM provider abstraction and implementations
  - `transport`: MCP transport abstractions (stdio/SSE)
  - `middleware`: Query processing and orchestration
- CLI per library:
  - `python -m src.cli.mcp_client --help/--list-tools/--test-connection`
  - `python -m src.cli.llm_test --help/--provider/--query`
  - `python -m src.cli.middleware --help/--test-e2e`
- Library docs: llms.txt format planned? Yes

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? Yes
- Git commits show tests before implementation? Yes
- Order: Contract→Integration→E2E→Unit strictly followed? Yes
- Real dependencies used? Yes (real PostgreSQL, real LLM APIs)
- Integration tests for: new libraries, contract changes, shared schemas? Yes
- FORBIDDEN: Implementation before test, skipping RED phase ✓

**Observability**:
- Structured logging included? Yes
- Frontend logs → backend? N/A (API only)
- Error context sufficient? Yes

**Versioning**:
- Version number assigned? 1.0.0
- BUILD increments on every change? Yes
- Breaking changes handled? N/A (new feature)

## Project Structure

### Documentation (this feature)
```
specs/002-add-middleware-for-agent-interaction/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (SELECTED)
src/
├── models/
│   ├── query.py          # Query and response models
│   ├── session.py        # Session management
│   └── tool_invocation.py # Tool call tracking
├── services/
│   ├── llm_service.py    # LLM orchestration
│   ├── mcp_service.py    # MCP tool management
│   └── middleware.py     # Query processing pipeline
├── cli/
│   ├── mcp_client.py     # MCP testing CLI
│   ├── llm_test.py       # LLM provider testing
│   └── middleware.py     # E2E testing CLI
├── lib/
│   ├── transport/
│   │   ├── __init__.py
│   │   ├── base.py       # Transport interface
│   │   ├── stdio.py      # Stdio implementation
│   │   └── sse.py        # SSE implementation
│   └── providers/
│       ├── __init__.py
│       ├── base.py       # Provider interface
│       ├── openai_provider.py
│       └── huawei_maas_provider.py
└── api/
    └── endpoints.py      # FastAPI endpoints

tests/
├── contract/
│   └── test_api_contracts.py
├── integration/
│   ├── test_openai_integration.py
│   ├── test_huawei_integration.py
│   ├── test_stdio_transport.py
│   └── test_sse_transport.py
└── unit/
    └── test_models.py
```

**Structure Decision**: Option 1 (Single project) - appropriate for API service with library components

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - All technical decisions resolved in specification
   - Reference implementations available (test_mcp_client.py, Reverse-engineer-mcp)

2. **Generate and dispatch research agents**:
   ```
   Task: "Research OpenAI function calling with tools API pattern"
   Task: "Research FastMCP stdio vs SSE connection patterns"
   Task: "Research token bucket rate limiting implementation in Python"
   Task: "Research asyncio connection pooling best practices"
   ```

3. **Consolidate findings** in `research.md`

**Output**: research.md with implementation patterns documented

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Query: user input, session_id, provider selection
   - AIResponse: content, tool_calls, metadata
   - MCPConnection: transport_type, status, tools
   - ToolInvocation: tool_name, arguments, result, duration
   - Session: id, messages[], context

2. **Generate API contracts** from functional requirements:
   - POST /api/query - Process user query
   - GET /api/health - System health check
   - GET /api/tools - List available MCP tools
   - POST /api/session - Create new session
   - GET /api/session/{id} - Retrieve session history
   - Output OpenAPI schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - test_query_endpoint.py
   - test_health_endpoint.py
   - test_tools_endpoint.py
   - test_session_endpoints.py

4. **Extract test scenarios** from user stories:
   - Query with single tool invocation
   - Query with multiple tool invocations
   - Provider switching scenario
   - Transport mode switching
   - Error handling scenarios

5. **Update CLAUDE.md incrementally**:
   - Add FastMCP patterns
   - Add OpenAI/Huawei MaaS configuration
   - Update recent changes

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, CLAUDE.md

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs:
  - Each contract → contract test task [P]
  - Each entity → model creation task [P]
  - Each provider → implementation task
  - Each transport → implementation task
  - Integration tests for each combination
  - API endpoint implementations

**Ordering Strategy**:
- TDD order: Tests before implementation
- Dependency order:
  1. Models and entities
  2. Transport abstractions
  3. Provider abstractions
  4. Service layer
  5. API endpoints
  6. Integration tests
  7. E2E tests
- Mark [P] for parallel execution

**Estimated Output**: 30-35 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
**Phase 4**: Implementation (execute tasks.md following constitutional principles)
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | - | - |

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning approach documented (/plan command)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*