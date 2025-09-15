# PostgreSQL MCP Server - Quick Start Guide

## Prerequisites

- Python 3.11 or higher
- PostgreSQL database (version 12+)
- Database credentials with SELECT permissions

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd postgresql-mcp-server

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials
```

## Configuration

Create a `.env` file with your database credentials:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_readonly_user
DB_PASSWORD=your_password

# Connection Pool Settings
DB_MIN_CONNECTIONS=2
DB_MAX_CONNECTIONS=10

# Server Settings
MCP_PORT=3000
LOG_LEVEL=INFO
```

## Starting the Server

```bash
# Run the MCP server
python -m src.cli.mcp_server

# Or with custom config
python -m src.cli.mcp_server --config custom.env --port 3001
```

## Testing the Connection

### 1. Get Database Metadata

```bash
# List all tables
mcp-client call get_metadata

# Get specific table info
mcp-client call get_metadata --table users

# Expected output:
{
  "tables": [
    {
      "name": "users",
      "columns": [
        {"name": "id", "data_type": "integer", "nullable": false, "is_primary": true},
        {"name": "email", "data_type": "varchar", "nullable": false},
        {"name": "created_at", "data_type": "timestamp", "nullable": false}
      ],
      "row_count": 1523
    }
  ],
  "cache_age": 0
}
```

### 2. Select Data

```bash
# Get first 5 rows from a table
mcp-client call select_data --table users

# Select specific columns with limit
mcp-client call select_data \
  --table users \
  --columns '["id", "email"]' \
  --limit 10

# Expected output:
{
  "columns": ["id", "email"],
  "rows": [
    [1, "user1@example.com"],
    [2, "user2@example.com"]
  ],
  "row_count": 2,
  "has_more": true
}
```

### 3. Execute Filtered Query

```bash
# Simple filter
mcp-client call execute_filter \
  --table users \
  --filters '[{"column": "created_at", "operator": ">", "value": "2024-01-01"}]'

# Complex filter with multiple conditions
mcp-client call execute_filter \
  --table orders \
  --filters '[
    {"column": "status", "operator": "=", "value": "completed", "logical": "AND"},
    {"column": "amount", "operator": ">", "value": 100}
  ]' \
  --limit 20
```

## Testing Scenarios

### Scenario 1: Concurrent Clients

```bash
# Terminal 1
for i in {1..5}; do
  mcp-client call select_data --table users &
done

# Should see all 5 requests processed with connection pooling
```

### Scenario 2: Rate Limiting

```bash
# Rapid fire requests from single client
for i in {1..15}; do
  mcp-client call get_metadata
  sleep 0.1
done

# After 10 requests, should see:
# Error: RATE_LIMIT_EXCEEDED
# Retry after: 60 seconds
```

### Scenario 3: Error Recovery

```bash
# Test with invalid table
mcp-client call select_data --table nonexistent_table

# Expected error:
{
  "error": {
    "code": "INVALID_TABLE_NAME",
    "message": "Table 'nonexistent_table' does not exist",
    "retryable": false,
    "suggestion": "Available tables: users, orders, products"
  }
}

# Test with malformed filter
mcp-client call execute_filter \
  --table users \
  --filters '[{"column": "id", "operator": "INVALID", "value": 1}]'

# Expected error:
{
  "error": {
    "code": "MALFORMED_FILTER",
    "message": "Invalid operator 'INVALID'",
    "retryable": false,
    "suggestion": "Valid operators: =, !=, >, <, >=, <=, LIKE, IN"
  }
}
```

### Scenario 4: Query Timeout

```bash
# Create a slow query (if you have a large table)
mcp-client call execute_filter \
  --table large_table \
  --filters '[{"column": "data", "operator": "LIKE", "value": "%pattern%"}]' \
  --limit 50

# After 30 seconds:
{
  "error": {
    "code": "QUERY_TIMEOUT",
    "message": "Query exceeded 30-second timeout",
    "retryable": true,
    "retry_after": 10
  }
}
```

## Monitoring

### Check Server Health

```bash
# Get server status
curl http://localhost:3000/health

# Expected output:
{
  "status": "healthy",
  "connections": {
    "active": 2,
    "idle": 3,
    "total": 5,
    "max": 10
  },
  "queue": {
    "size": 0,
    "max": 15
  },
  "uptime": 3600
}
```

### View Logs

```bash
# Follow server logs
tail -f logs/mcp-server.log | jq '.'

# Filter for errors
grep ERROR logs/mcp-server.log | jq '.message'

# Check rate limiting events
grep RATE_LIMIT logs/mcp-server.log | jq '{client: .client_id, time: .timestamp}'
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/contract/          # Contract tests
pytest tests/integration/       # Integration tests
pytest tests/unit/              # Unit tests

# Run with coverage
pytest --cov=src --cov-report=html

# Run with real database
docker-compose -f docker-compose.test.yml up -d
pytest --database=postgresql://test_user:test_pass@localhost:5432/test_db
```

## Common Issues

### Issue: Connection Pool Exhausted

**Symptom**: `CONNECTION_POOL_EXHAUSTED` errors

**Solution**:
1. Check for long-running queries
2. Increase `DB_MAX_CONNECTIONS` (max 10)
3. Implement query optimization

### Issue: Authentication Failed

**Symptom**: `AUTHENTICATION_FAILED` error on startup

**Solution**:
1. Verify database credentials in `.env`
2. Check database user permissions
3. Ensure database is accessible from server

### Issue: Slow Queries

**Symptom**: Frequent timeout errors

**Solution**:
1. Add database indexes
2. Optimize filter conditions
3. Reduce result set size with limits

## Performance Tips

1. **Use Column Selection**: Don't use `SELECT *` for large tables
2. **Paginate Results**: Use `offset` and `limit` for large datasets
3. **Cache Metadata**: Metadata is cached for 1 hour by default
4. **Index Filtered Columns**: Ensure filtered columns have indexes
5. **Monitor Connections**: Keep active connections below 80% of max

## Security Notes

- Server runs with read-only database access
- All identifiers are validated against injection
- Filters use parameterized queries
- Rate limiting prevents abuse
- Connections use SSL when available

## Next Steps

1. Configure production database access
2. Set up monitoring dashboards
3. Implement custom error handling
4. Add application-specific tools
5. Configure log aggregation