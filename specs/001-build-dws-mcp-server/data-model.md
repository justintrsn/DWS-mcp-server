# Data Model: PostgreSQL MCP Server

## Core Entities

### ConnectionPool
Manages database connections with automatic lifecycle handling.

**Attributes**:
- `min_connections`: int = 2 (minimum idle connections)
- `max_connections`: int = 10 (maximum total connections)
- `active_connections`: int (current active count)
- `idle_connections`: int (current idle count)
- `queue_size`: int (waiting requests)
- `created_at`: datetime (pool initialization time)

**State Transitions**:
- INITIALIZING → READY (on startup)
- READY → BUSY (when max_connections reached)
- BUSY → READY (when connection freed)
- ANY → ERROR (on critical failure)
- ERROR → READY (on recovery)

**Validation Rules**:
- min_connections must be ≥ 1
- max_connections must be ≥ min_connections
- max_connections must be ≤ 10 (per spec)

### ClientSession
Tracks individual client state for rate limiting and fairness.

**Attributes**:
- `client_id`: str (unique identifier)
- `request_count`: int (requests in current window)
- `window_start`: datetime (rate limit window start)
- `last_request`: datetime (for idle tracking)
- `queued_requests`: int (current queued count)
- `total_requests`: int (lifetime counter)

**State Transitions**:
- NEW → ACTIVE (first request)
- ACTIVE → RATE_LIMITED (exceeds 10 req/min)
- RATE_LIMITED → ACTIVE (window reset)
- ACTIVE → IDLE (no requests for 5 min)
- IDLE → ACTIVE (new request)

**Validation Rules**:
- client_id must be non-empty string
- request_count must not exceed 10 per minute
- queued_requests must not exceed 3 per client

### QueryRequest
Represents a database query request from a client.

**Attributes**:
- `request_id`: str (unique identifier)
- `client_id`: str (requesting client)
- `table`: str (target table name)
- `columns`: list[str] (columns to select, default ["*"])
- `filters`: dict (filter conditions)
- `limit`: int (row limit, default 5, max 50)
- `offset`: int (pagination offset, default 0)
- `timeout`: int (query timeout seconds, default 30)
- `created_at`: datetime (request time)

**Validation Rules**:
- table must match ^[a-zA-Z_][a-zA-Z0-9_]*$
- columns must be valid identifiers or "*"
- filters must use allowed operators only
- limit must be 1-50
- timeout must be 1-30 seconds

### ErrorResponse
Structured error information for clients.

**Attributes**:
- `code`: str (error code enum)
- `message`: str (human-readable message)
- `retryable`: bool (can client retry)
- `retry_after`: int (seconds to wait, optional)
- `details`: dict (additional context)
- `suggestion`: str (fix recommendation)
- `timestamp`: datetime (error occurrence time)

**Error Codes** (enum):
- `CONNECTION_POOL_EXHAUSTED`
- `RATE_LIMIT_EXCEEDED`
- `QUERY_TIMEOUT`
- `INVALID_TABLE_NAME`
- `INVALID_COLUMN_NAME`
- `MALFORMED_FILTER`
- `AUTHENTICATION_FAILED`
- `PERMISSION_DENIED`
- `DATABASE_UNAVAILABLE`
- `INTERNAL_ERROR`

### DatabaseMetadata
Cached database schema information.

**Attributes**:
- `tables`: dict[str, TableInfo] (table definitions)
- `last_refresh`: datetime (cache timestamp)
- `refresh_interval`: int = 3600 (seconds)
- `version`: str (schema version)

### TableInfo
Schema information for a single table.

**Attributes**:
- `name`: str (table name)
- `columns`: list[ColumnInfo] (column definitions)
- `row_count`: int (estimated rows)
- `size_bytes`: int (table size)
- `indexes`: list[str] (index names)

### ColumnInfo
Schema information for a single column.

**Attributes**:
- `name`: str (column name)
- `data_type`: str (PostgreSQL type)
- `nullable`: bool (allows NULL)
- `default`: str (default value/expression)
- `is_primary`: bool (part of primary key)
- `is_unique`: bool (has unique constraint)

## Relationships

```
ConnectionPool ──owns──> Connection (1:N)
ClientSession ──submits──> QueryRequest (1:N)
QueryRequest ──uses──> Connection (N:1)
QueryRequest ──returns──> ErrorResponse (1:0..1)
DatabaseMetadata ──contains──> TableInfo (1:N)
TableInfo ──contains──> ColumnInfo (1:N)
```

## Data Flow

1. **Client connects** → Create/retrieve ClientSession
2. **Client sends request** → Create QueryRequest
3. **Rate limiter checks** → Update ClientSession.request_count
4. **Queue if needed** → Add to ConnectionPool.queue
5. **Acquire connection** → Get from ConnectionPool
6. **Execute query** → Use Connection with timeout
7. **Return results** → Format response or ErrorResponse
8. **Release connection** → Return to ConnectionPool
9. **Update metrics** → Log to structured logs

## Consistency Rules

1. **Connection Invariants**:
   - Active connections ≤ max_connections
   - Active + idle = total connections
   - Queue size ≤ 15 (max pending requests)

2. **Rate Limit Invariants**:
   - Request count resets every 60 seconds
   - No client exceeds 10 requests per minute
   - Fair scheduling via round-robin

3. **Resource Invariants**:
   - No client uses >40% of connections
   - Queries cancelled at 30-second timeout
   - Idle connections closed after 300 seconds

## Caching Strategy

1. **Metadata Cache**:
   - TTL: 3600 seconds (1 hour)
   - Invalidation: On DDL operations (if detected)
   - Refresh: Lazy on expiration

2. **Connection Cache**:
   - Pool maintains warm connections
   - Min connections always ready
   - Health check every 60 seconds

3. **Client Session Cache**:
   - In-memory for active clients
   - Eviction: After 5 minutes idle
   - Persistence: None (stateless restart)

## Security Constraints

1. **Input Validation**:
   - All identifiers regex validated
   - Filter operators whitelisted
   - SQL injection prevention via parameters

2. **Access Control**:
   - Read-only database connections
   - No DDL operations permitted
   - Row-level security respected

3. **Audit Requirements**:
   - Log all queries with client_id
   - Track error patterns per client
   - Monitor resource usage trends

## Performance Targets

1. **Response Times**:
   - Metadata: <100ms p95
   - Simple queries: <500ms p95
   - Complex filters: <2000ms p95

2. **Throughput**:
   - 50 requests/second sustained
   - 100 requests/second burst
   - 5 concurrent clients

3. **Resource Limits**:
   - Memory: <100MB baseline
   - Connections: 10 maximum
   - Queue depth: 15 maximum