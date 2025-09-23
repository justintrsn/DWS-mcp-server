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
3. **get_table_stats**: Enhanced with toast size

### MCP Tools - Phase 2 (Database Level)
4. **list_schemas**: All schemas with classification
5. **get_database_stats**: Overall database metrics
6. **get_connection_info**: Connection pool status

### MCP Tools - Phase 3 (Object Level)
7. **describe_object**: Universal object inspector
8. **explain_query**: Query plan analyzer
9. **list_views**, **list_functions**, **list_indexes**: Object listings
10. **get_table_constraints**: Constraint information
11. **get_dependencies**: Dependency analysis

### MCP Tools - Phase 4 (Optional/Extensions)
12. **get_top_queries**: Performance analysis (pg_stat_statements)
13. **get_index_recommendations**: AI-powered suggestions (hypopg)
14. **check_database_health**: Comprehensive health metrics

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

---
*Generated for PostgreSQL MCP Server v1.0.0*