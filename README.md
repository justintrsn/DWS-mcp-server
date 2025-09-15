# DWS MCP Server

A Model Context Protocol (MCP) server for Huawei Data Warehouse Service (DWS), providing AI-friendly database operations through standardized tools.

## Features

- **MCP Protocol Support**: Full implementation of Model Context Protocol for AI model integration
- **Multiple Transports**: Support for both stdio and SSE (Server-Sent Events) transports
- **Database Operations**: Safe, read-only database access with connection pooling
- **Health Monitoring**: Built-in health API with database and metrics endpoints
- **OpenAI Integration**: Direct integration with OpenAI models for intelligent database queries
- **Rate Limiting**: Token bucket algorithm for request rate management
- **Comprehensive Testing**: Full test suite with unit, integration, and contract tests

## Architecture

```
src/
├── cli/              # MCP server entry point
├── models/           # Data models (config, errors, pool)
├── services/         # Core services (database, health API)
├── lib/              # MCP tool implementations
└── transport/        # Transport implementations (stdio, SSE)

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests with real database
└── contract/        # MCP protocol contract tests
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

### Available MCP Tools

1. **list_tables**: List all tables in the database
   ```json
   {
     "tool": "list_tables",
     "arguments": {
       "schema": "public"  // optional
     }
   }
   ```

2. **describe_table**: Get column information for a table
   ```json
   {
     "tool": "describe_table",
     "arguments": {
       "table_name": "users",
       "schema": "public"  // optional
     }
   }
   ```

3. **table_statistics**: Get statistics for tables
   ```json
   {
     "tool": "table_statistics",
     "arguments": {
       "table_name": "users"  // or "table_names": ["users", "orders"]
     }
   }
   ```

### Health Monitoring

When health API is enabled, the following endpoints are available:

- `GET /health` - Overall system health
- `GET /health/database` - Database connection status and pool info
- `GET /health/metrics` - Request metrics and error rates
- `GET /health/ready` - Readiness probe for container orchestration
- `GET /health/live` - Liveness probe

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