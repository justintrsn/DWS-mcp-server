# DWS MCP Server

A Model Context Protocol (MCP) server for Huawei Data Warehouse Service (DWS), providing AI-friendly database operations through standardized tools.

## Features

- **MCP Protocol Support**: Full implementation of Model Context Protocol for AI model integration
- **Multiple Transports**: Support for both stdio and SSE (Server-Sent Events) transports
- **Multi-Round Tool Calling**: Enhanced 3-step workflow with session state tracking (85% success rate)
- **15+ Database Tools**: Comprehensive PostgreSQL introspection and analysis tools
- **Safe Query Execution**: Read-only SQL execution with automatic table validation
- **Session State Management**: Tools remember inspected tables across multiple calls
- **Health Monitoring**: Built-in health API with database and metrics endpoints
- **OpenAI Integration**: Direct integration with OpenAI models for intelligent database queries
- **Connection Pooling**: Thread-safe connection management with automatic retry
- **Rate Limiting**: Token bucket algorithm for request rate management
- **Docker Deployment**: Production-ready containerization with PostgreSQL
- **Comprehensive Testing**: Full test suite with unit, integration, and contract tests

## Architecture

```
src/
├── cli/              # MCP server entry point
├── models/           # Data models (config, errors, pool)
├── services/         # Core services (database, health API)
├── lib/              # MCP tool implementations
│   ├── tools/        # Modular tool organization:
│   │   ├── database.py  # Database-level operations
│   │   ├── schema.py    # Schema-level operations
│   │   └── table.py     # Table-level operations
│   └── mcp_tools.py  # Orchestration layer
└── transport/        # Transport implementations (stdio, SSE)

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests with real database
├── contract/        # MCP protocol contract tests
└── client/          # Tool testers organized by category
```

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL/DWS database access
- Virtual environment (recommended)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dws-mcp-server.git
cd dws-mcp-server
```

2. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

## Docker Deployment

For production deployment, use the provided Docker Compose setup:

```bash
# Start the complete stack (PostgreSQL + MCP Server)
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f mcp-server
```

The Docker setup includes:
- **PostgreSQL Database**: Pre-configured with anime sample data (port 5434)
- **MCP Server**: Production-ready container with health monitoring (ports 3000, 8080)
- **Container Images**: Published to Huawei Cloud SWR registry
- **Health Checks**: Built-in health monitoring and dependency management
- **Data Persistence**: PostgreSQL data persisted in Docker volumes

Services accessible at:
- MCP Server SSE: http://localhost:3000
- Health API: http://localhost:8080/health
- PostgreSQL: localhost:5434

## Configuration

Create a `.env` file with the following configuration:

```env
# Database Configuration
DB_HOST=your-database-host
DB_PORT=8000
DB_DATABASE=your-database-name
DB_USER=your-username
DB_PASSWORD=your-password

# Server Configuration (optional)
MCP_PORT=3000
LOG_LEVEL=INFO
DB_CONNECT_TIMEOUT=10
DB_COMMAND_TIMEOUT=30

# OpenAI Configuration (optional)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
```

## Usage

### Starting the Server

#### Stdio Transport (for Claude Desktop or other MCP clients):
```bash
python -m src.cli.mcp_server --transport stdio
```

#### SSE Transport (for web-based clients):
```bash
python -m src.cli.mcp_server --transport sse --port 3000
```

#### With Health API:
```bash
python -m src.cli.mcp_server --transport sse --port 3000 --health-port 8080
```

### Available MCP Tools (15+ Tools)

The server provides comprehensive PostgreSQL introspection through organized tool categories:

#### 🔄 **Three-Step Query Workflow** (Recommended)

For optimal results, follow this validated workflow:

1. **discover_tables** (🔍 STEP 1): Find available tables
   ```json
   {
     "tool": "discover_tables",
     "arguments": {
       "schema": "public"  // optional
     }
   }
   ```
   Returns: List of tables with owners, types, and sizes

2. **inspect_table_schema** (📋 STEP 2): Required before querying
   ```json
   {
     "tool": "inspect_table_schema",
     "arguments": {
       "table_name": "users",
       "schema": "public"  // optional
     }
   }
   ```
   Returns: Column details, types, constraints, and relationships

3. **safe_read_query** (⚡ STEP 3): Execute validated SQL
   ```json
   {
     "tool": "safe_read_query",
     "arguments": {
       "query": "SELECT name, email FROM users LIMIT 10",
       "limit": 100  // optional, max 1000
     }
   }
   ```
   Returns: Query results with automatic table validation

#### 🗄️ **Database-Level Tools**

4. **schemas_list**: List all database schemas
   ```json
   {
     "tool": "schemas_list",
     "arguments": {
       "include_system": false,  // optional
       "include_sizes": true     // optional
     }
   }
   ```

5. **database_stats**: Comprehensive database metrics
   ```json
   {"tool": "database_stats", "arguments": {}}
   ```
   Returns: Size, connections, activity, and performance metrics

6. **connection_info**: View connection pool status
   ```json
   {
     "tool": "connection_info",
     "arguments": {
       "by_state": true,      // optional
       "by_database": false   // optional
     }
   }
   ```

#### 📊 **Table Analysis Tools**

7. **table_statistics**: Enhanced table metadata and activity
   ```json
   {
     "tool": "table_statistics",
     "arguments": {
       "table_name": "users"  // or "table_names": ["users", "orders"]
     }
   }
   ```
   Returns: Storage size, row counts, activity metrics, maintenance info

8. **column_statistics**: Pandas-like statistical analysis
   ```json
   {
     "tool": "column_statistics",
     "arguments": {
       "table_name": "users",
       "column_names": ["age", "income"]  // optional
     }
   }
   ```
   Returns: Min, max, mean, median, quartiles, null counts, outliers

#### 🔍 **Object Inspection Tools**

9. **describe_object**: Universal database object inspector
   ```json
   {
     "tool": "describe_object",
     "arguments": {
       "object_name": "users",
       "object_type": "table"  // optional: table, view, function, etc.
     }
   }
   ```

10. **explain_query**: Query execution plan analyzer
    ```json
    {
      "tool": "explain_query",
      "arguments": {
        "query": "SELECT * FROM users WHERE age > 25",
        "analyze": true  // optional: include runtime stats
      }
    }
    ```

11. **list_views**: Enumerate database views
    ```json
    {
      "tool": "list_views",
      "arguments": {
        "schema": "public",        // optional
        "include_system": false    // optional
      }
    }
    ```

12. **list_functions**: List stored functions and procedures
    ```json
    {
      "tool": "list_functions",
      "arguments": {
        "schema": "public",        // optional
        "include_system": false    // optional
      }
    }
    ```

13. **list_indexes**: View table indexes and their properties
    ```json
    {
      "tool": "list_indexes",
      "arguments": {
        "table_name": "users",     // optional
        "schema": "public"          // optional
      }
    }
    ```

14. **get_table_constraints**: Detailed constraint information
    ```json
    {
      "tool": "get_table_constraints",
      "arguments": {
        "table_name": "users",
        "schema": "public"  // optional
      }
    }
    ```
    Returns: Primary keys, foreign keys, unique constraints, checks

15. **get_dependencies**: Analyze object dependencies
    ```json
    {
      "tool": "get_dependencies",
      "arguments": {
        "object_name": "users",
        "object_type": "table"
      }
    }
    ```
    Returns: Objects that depend on this object and objects this depends on

#### 🎯 **Multi-Round Tool Calling**

The server features enhanced session state management:

- **Session Memory**: Tools remember which tables have been inspected
- **Automatic Validation**: `safe_read_query` validates that referenced tables are known
- **Helpful Error Recovery**: Specific guidance when prerequisites aren't met
- **85% Success Rate**: Proven effectiveness for complex multi-round database workflows

**Example Multi-Round Workflow:**
```bash
1. discover_tables → Find "users" and "orders" tables
2. inspect_table_schema("users") → Learn column structure
3. inspect_table_schema("orders") → Learn relationships
4. safe_read_query("SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o...") → Execute complex join
```

### Database Profile Management

The server supports multiple database profiles for connecting to different databases dynamically:

#### Profile Configuration
Configure multiple database profiles in your environment or configuration files:
```env
# Main database (default profile)
DB_HOST=production-db
DB_DATABASE=main_db
DB_USER=user1

# Additional profiles can be defined in database_profiles.json
```

#### Runtime Database Switching
Switch between databases using the Health API:
```bash
# List available profiles
curl -X GET http://localhost:8080/api/database/profiles

# Switch to a different database profile
curl -X POST http://localhost:8080/api/database/switch \
  -H "Content-Type: application/json" \
  -d '{"profile": "analytics_db", "validate_connection": true}'

# Test connection to a profile before switching
curl -X POST http://localhost:8080/api/database/test \
  -H "Content-Type: application/json" \
  -d '{"profile": "staging_db", "timeout": 10}'
```

**Note**: Database switching functionality is available but still being tested. Use with caution in production environments.

### Health Monitoring

When health API is enabled, the following endpoints are available:

- `GET /health` - Overall system health
- `GET /health/database` - Database connection status and pool info
- `GET /health/metrics` - Request metrics and error rates
- `GET /health/ready` - Readiness probe for container orchestration
- `GET /health/live` - Liveness probe
- `GET /api/database/profiles` - List available database profiles
- `POST /api/database/switch` - Switch database profiles
- `POST /api/database/test` - Test database profile connections

## Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests (requires database)
pytest tests/integration/

# Contract tests
pytest tests/contract/
```

### Test with Docker PostgreSQL
```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run tests
pytest

# Stop test database
docker-compose -f docker-compose.test.yml down
```

### Manual Testing
```bash
# Run the interactive test client
python tests/test_mcp_client.py
```

## Development

### Project Structure

- **MCP Tools** (`src/lib/mcp_tools.py`): Core database operations exposed as MCP tools
- **Database Service** (`src/services/database_service.py`): Database connection management and query execution
- **Connection Pool** (`src/models/connection_pool.py`): Thread-safe connection pooling
- **Rate Limiter** (`src/models/rate_limiter.py`): Token bucket rate limiting
- **Health API** (`src/services/health_api.py`): FastAPI-based health monitoring

### Adding New Tools

1. Define the tool in `src/lib/mcp_tools.py`
2. Register it with the MCP server in `src/cli/mcp_server.py`
3. Add contract tests in `tests/contract/`
4. Add integration tests in `tests/integration/`

### Error Handling

The server implements comprehensive error handling with:
- Recoverable errors (connection issues, rate limits)
- Non-recoverable errors (invalid queries, auth failures)
- Structured error responses with retry guidance

## Security

- **Read-Only Access**: Database user should have SELECT-only permissions
- **SQL Injection Prevention**: All queries use parameterized statements
- **Input Validation**: All identifiers validated with regex patterns
- **No DDL Operations**: Only data query operations are allowed
- **Environment Variables**: Sensitive data stored in `.env` file (not in version control)

## Performance

- **Connection Pooling**: Maintains 2-5 database connections
- **Rate Limiting**: 10 requests per minute per client (configurable)
- **Query Timeout**: 30-second maximum query execution time
- **Structured Logging**: JSON logging for production environments

## Troubleshooting

### Common Issues

1. **Connection Pool Exhausted**
   - Increase `DB_POOL_MAX_SIZE` in configuration
   - Check for connection leaks in logs

2. **Rate Limit Exceeded**
   - Wait for token bucket to refill (60 seconds)
   - Increase rate limit in configuration

3. **Database Connection Failed**
   - Verify database credentials in `.env`
   - Check network connectivity to database
   - Ensure database user has proper permissions

### Debugging

Enable debug logging:
```bash
LOG_LEVEL=DEBUG python -m src.cli.mcp_server
```

Check health status:
```bash
curl http://localhost:8080/health
curl http://localhost:8080/health/database
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary and confidential.

## Support

For issues and questions, please create an issue in the GitHub repository.