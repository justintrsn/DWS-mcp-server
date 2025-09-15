# Research Findings: PostgreSQL MCP Server

## FastMCP Framework

**Decision**: Use FastMCP's built-in decorators and tool registration  
**Rationale**: 
- Native MCP protocol support with minimal boilerplate
- Automatic schema generation from Python type hints
- Built-in error handling and response formatting
- Async/await support for concurrent operations

**Alternatives considered**:
- Raw MCP protocol implementation: Too complex, reinventing the wheel
- Other MCP libraries: FastMCP is most mature and actively maintained

**Implementation approach**:
```python
from fastmcp import FastMCP, Tool

mcp = FastMCP("postgresql-mcp")

@mcp.tool()
async def get_metadata(table: str = None) -> dict:
    """Get database metadata"""
    pass
```

## Connection Pooling Strategy

**Decision**: psycopg2 ThreadedConnectionPool with async wrapper  
**Rationale**:
- Thread-safe for concurrent client access
- Built-in connection lifecycle management
- Automatic connection recovery on failure
- Configurable min/max connections

**Alternatives considered**:
- asyncpg: Better performance but less mature ecosystem
- SQLAlchemy pool: Too heavy for simple needs
- Manual pooling: Error-prone, reinventing standard patterns

**Configuration**:
```python
from psycopg2 import pool

connection_pool = pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
```

## Rate Limiting Implementation

**Decision**: Token bucket algorithm with sliding window  
**Rationale**:
- Smooth traffic shaping vs hard cutoffs
- Memory efficient for tracking clients
- Fair burst handling
- Simple to implement and understand

**Alternatives considered**:
- Fixed window: Can cause thundering herd
- Leaky bucket: More complex, similar results
- Redis-based: Unnecessary external dependency

**Implementation pattern**:
```python
class RateLimiter:
    def __init__(self, rate: int = 10, per: int = 60):
        self.rate = rate  # 10 requests
        self.per = per    # per 60 seconds
        self.allowance = {}
        self.last_check = {}
    
    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        # Token bucket logic
        pass
```

## Error Handling Standards

**Decision**: Structured error responses with MCP ErrorData  
**Rationale**:
- MCP protocol standard compliance
- Machine-readable error classification
- Human-friendly messages
- Actionable recovery guidance

**Error categories**:
1. **Recoverable** (transient):
   - Connection timeouts
   - Rate limits
   - Resource contention
   - Include: retry_after, retry_count

2. **Non-recoverable** (permanent):
   - Invalid queries
   - Authentication failures
   - Schema violations
   - Include: fix_suggestion, documentation_link

**Response format**:
```python
{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Request limit exceeded",
        "data": {
            "retryable": true,
            "retry_after": 5,
            "limit": 10,
            "window": 60,
            "client_requests": 11
        }
    }
}
```

## Query Safety and Injection Prevention

**Decision**: Parameterized queries with whitelist validation  
**Rationale**:
- psycopg2 native parameter binding prevents injection
- Whitelist approach for dynamic identifiers (table/column names)
- Clear separation of data and structure

**Alternatives considered**:
- Query builders (SQLAlchemy): Overkill for simple needs
- String escaping: Error-prone, not recommended
- Stored procedures only: Too restrictive for metadata operations

**Implementation**:
```python
# Safe parameterized query
cursor.execute(
    "SELECT %s FROM %s WHERE %s = %s",
    (AsIs(columns), AsIs(table), AsIs(filter_col), value)
)

# Identifier validation
def validate_identifier(name: str) -> bool:
    return re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name) is not None
```

## Timeout Management

**Decision**: Statement-level timeouts with graceful cancellation  
**Rationale**:
- PostgreSQL native statement_timeout
- Clean resource cleanup on timeout
- Client notification before disconnection

**Configuration**:
```python
# Per-query timeout
cursor.execute("SET statement_timeout = '30s'")

# Connection-level default
connection.set_session(
    readonly=True,
    autocommit=True,
    options='-c statement_timeout=30s'
)
```

## Logging Architecture

**Decision**: Structured logging with Python logging + JSON formatter  
**Rationale**:
- Standard Python logging compatibility
- JSON format for log aggregation
- Configurable levels per component
- Minimal performance overhead

**Alternatives considered**:
- structlog: More features but additional dependency
- Custom logger: Maintenance burden
- Print statements: Not production-ready

**Configuration**:
```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': record.created,
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'extra': record.__dict__.get('extra', {})
        })
```

## Testing Strategy

**Decision**: Real PostgreSQL in Docker for all tests  
**Rationale**:
- Catches real database behavior issues
- No mock/stub maintenance burden
- Consistent dev/test/prod behavior
- Docker ensures isolation

**Test database setup**:
```python
# docker-compose.test.yml
services:
  postgres-test:
    image: postgres:15
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    ports:
      - "5432:5432"
```

## Performance Optimizations

**Decision**: Query result streaming with cursor pagination  
**Rationale**:
- Memory efficient for large results
- Responsive first-byte times
- Natural pagination support

**Implementation**:
```python
# Server-side cursor for streaming
with connection.cursor('large_query', cursor_factory=DictCursor) as cursor:
    cursor.itersize = 100  # Fetch 100 rows at a time
    cursor.execute(query)
    for row in cursor:
        yield row
```

## Security Considerations

**Decision**: Principle of least privilege with read-only connections  
**Rationale**:
- MCP server should not modify data
- Reduces attack surface
- Clear security boundary

**Implementation**:
- Database user with SELECT-only permissions
- Connection forced to read-only mode
- No DDL operations allowed
- Audit logging for all queries

---

## Summary of Key Decisions

1. **FastMCP** for MCP protocol handling
2. **psycopg2 ThreadedConnectionPool** for connection management
3. **Token bucket** rate limiting per client
4. **Structured JSON** error responses
5. **Parameterized queries** with identifier validation
6. **PostgreSQL statement_timeout** for query limits
7. **Python logging with JSON** formatting
8. **Docker PostgreSQL** for testing
9. **Streaming cursors** for large results
10. **Read-only connections** for security

All technical decisions prioritize simplicity, safety, and MCP protocol compliance while meeting the specified requirements for concurrent client support and comprehensive error handling.