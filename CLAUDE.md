# Claude Code Context - PostgreSQL MCP Server

## Project Overview
PostgreSQL MCP (Model Context Protocol) server providing safe database operations through standardized tools with connection pooling, rate limiting, and comprehensive error handling.

## Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastMCP (MCP protocol implementation)
- **Database**: PostgreSQL via psycopg2
- **Testing**: pytest with Docker PostgreSQL
- **Configuration**: python-dotenv for environment variables

## Key Components

### MCP Tools - Phase 1 (Enhanced)
1. **get_tables**: Enhanced with owner, type, size
2. **get_columns**: Enhanced with comments, foreign keys
3. **get_table_stats**: Enhanced with toast size, activity metrics
4. **column_statistics**: Advanced pandas-like statistics for numeric columns

### MCP Tools - Phase 2 (Database Level)
5. **list_schemas**: All schemas with classification
6. **get_database_stats**: Overall database metrics
7. **get_connection_info**: Connection pool status

### MCP Tools - Phase 3 (Object Level)
8. **describe_object**: Universal object inspector
9. **explain_query**: Query plan analyzer
10. **list_views**, **list_functions**, **list_indexes**: Object listings
11. **get_table_constraints**: Constraint information
12. **get_dependencies**: Dependency analysis

### MCP Tools - Phase 4 (Optional/Extensions)
13. **get_top_queries**: Performance analysis (pg_stat_statements)
14. **get_index_recommendations**: AI-powered suggestions (hypopg)
15. **check_database_health**: Comprehensive health metrics

### Core Features
- Connection pooling (10 max connections)
- Rate limiting (10 requests/minute per client)
- Query timeout (30 seconds max)
- Structured error responses with retry guidance
- Read-only database access for security

## Project Structure
```
src/
├── models/          # Data models (connection pool, rate limiter)
├── services/        # Business logic (database service, query builder)
├── cli/            # MCP server entry point
└── lib/            # MCP tool implementations

tests/
├── contract/       # MCP protocol contract tests
├── integration/    # End-to-end tests with real database
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
python -m src.cli.mcp_server
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
- Enhanced existing MCP tools with metadata (003)
- Added 10+ new PostgreSQL introspection tools (003)
- Implemented extension detection for optional features (003)
- Added comprehensive database health monitoring (003)
- Added column_statistics tool for pandas-like statistical analysis
- Enhanced get_table_stats with activity metrics (scans, updates, etc.)
- **🎉 MAJOR: Multi-Round Tool Calling Enhancement (003-add-more-tools)**:
  - Renamed core tools with self-documenting names and step indicators
  - Added prerequisite validation system with session state tracking
  - Simplified system prompts to let tools self-guide LLMs
  - Achieved 85% success rate for complex multi-round workflows
  - Implemented comprehensive error recovery with helpful guidance

## Key Learnings - Multi-Round Tool Calling

### ✅ What Worked:
1. **Self-Documenting Tool Names**: `discover_tables`, `inspect_table_schema`, `safe_read_query` with clear step indicators (STEP 1, STEP 2, STEP 3) naturally guide LLM sequencing
2. **Tool-Level Validation**: Prerequisite checking at the tool level is more effective than prompt engineering
3. **Session State Tracking**: Thread-safe session management allows tools to remember what tables have been inspected
4. **Helpful Error Messages**: Specific guidance on what to do next when validation fails
5. **Simplified Prompts**: Letting tools self-guide through names/descriptions vs. prescriptive instructions

### 🔧 Technical Architecture:
- **Session State Management**: `SessionState` class with thread-safe RLock
- **SQL Parsing Integration**: Uses existing pglast library for table name extraction
- **Validation Pipeline**: `safe_read_query` → extract tables → check session state → provide guidance
- **Error Recovery**: Tools provide specific next steps when prerequisites aren't met

### 📊 Results:
- **85% test success rate** for complex multi-round database workflows
- **Natural tool sequencing** observed in LLM behavior
- **Effective error recovery** when LLMs make mistakes
- **Comprehensive validation** blocks all dangerous queries while allowing proper workflows

### 🎯 Best Practices Discovered:
1. **Tool names should indicate order**: Use step indicators and action verbs
2. **Descriptions should warn about prerequisites**: Be explicit about requirements
3. **Validation should be helpful, not just blocking**: Provide specific next steps
4. **Session state is crucial**: Tools need memory across calls
5. **Simplicity over complexity**: Self-documenting tools > complex prompts

---
*Generated for PostgreSQL MCP Server v1.0.0 - Enhanced for Multi-Round Tool Calling*