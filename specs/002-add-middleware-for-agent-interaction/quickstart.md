# Quickstart: OpenAI-Compatible MCP Middleware

## Prerequisites
- Python 3.11+
- PostgreSQL database (for MCP tools)
- OpenAI API key or Huawei MaaS credentials
- Docker (optional, for testing)

## Installation

```bash
# Clone repository
git clone <repository-url>
cd DWS-mcp-server

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

## Configuration

Edit `.env` file:

```bash
# LLM Provider Configuration (choose one)
LLM_PROVIDER=openai  # or huawei_maas

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Huawei MaaS Configuration
MAAS_API_URL=https://...
MAAS_API_KEY=...
MAAS_MODEL_NAME=...

# MCP Configuration
MCP_TRANSPORT=sse  # or stdio
MCP_SERVER_URL=http://localhost:3000/sse  # for SSE transport

# PostgreSQL Configuration (for MCP tools)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=testdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_TOKEN=your-bearer-token
```

## Quick Test

### 1. Start MCP Server (SSE mode)
```bash
python -m src.cli.mcp_server --transport sse --port 3000
```

### 2. Start Middleware API
```bash
python -m src.api.main
```

### 3. Test Query Processing
```bash
# Simple query
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer your-bearer-token" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "What tables are in the database?"
  }'

# Query with specific provider
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer your-bearer-token" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Show me the structure of the users table",
    "provider": "huawei_maas"
  }'
```

## Full Workflow Test

### 1. Create Session
```bash
SESSION_ID=$(curl -X POST http://localhost:8000/api/session \
  -H "Authorization: Bearer your-bearer-token" \
  -H "Content-Type: application/json" \
  -d '{"provider_preference": "openai"}' \
  | jq -r '.id')
```

### 2. List Available Tools
```bash
curl http://localhost:8000/api/tools \
  -H "Authorization: Bearer your-bearer-token" | jq
```

### 3. Execute Query with Context
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer your-bearer-token" \
  -H "Content-Type: application/json" \
  -d "{
    \"content\": \"How many records are in the users table?\",
    \"session_id\": \"$SESSION_ID\"
  }" | jq
```

### 4. Follow-up Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer your-bearer-token" \
  -H "Content-Type: application/json" \
  -d "{
    \"content\": \"Show me the first 5 records\",
    \"session_id\": \"$SESSION_ID\"
  }" | jq
```

## Test Both Transports

### STDIO Transport Test
```bash
# Start middleware with stdio
export MCP_TRANSPORT=stdio
python -m src.cli.middleware --test-e2e --query "List all tables"
```

### SSE Transport Test
```bash
# Ensure MCP server is running on port 3000
export MCP_TRANSPORT=sse
export MCP_SERVER_URL=http://localhost:3000/sse
python -m src.cli.middleware --test-e2e --query "List all tables"
```

## Test Both Providers

### OpenAI Provider
```bash
python -m src.cli.llm_test \
  --provider openai \
  --query "What database tables are available?"
```

### Huawei MaaS Provider
```bash
python -m src.cli.llm_test \
  --provider huawei_maas \
  --query "What database tables are available?"
```

## Docker Compose Setup

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: password
      POSTGRES_DB: testdb
    ports:
      - "5432:5432"

  mcp-server:
    build: .
    command: python -m src.cli.mcp_server --transport sse --port 3000
    environment:
      - POSTGRES_HOST=postgres
    ports:
      - "3000:3000"
    depends_on:
      - postgres

  middleware-api:
    build: .
    command: python -m src.api.main
    environment:
      - LLM_PROVIDER=${LLM_PROVIDER}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MCP_SERVER_URL=http://mcp-server:3000/sse
    ports:
      - "8000:8000"
    depends_on:
      - mcp-server
```

## Performance Test

```bash
# Rate limiting test
for i in {1..15}; do
  curl -X POST http://localhost:8000/api/query \
    -H "Authorization: Bearer your-bearer-token" \
    -H "Content-Type: application/json" \
    -d '{"content": "Quick test"}' &
done
wait

# Check rate limit headers
curl -I -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer your-bearer-token" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test"}'
```

## Health Check

```bash
# System health
curl http://localhost:8000/api/health | jq

# Component health
curl http://localhost:8000/api/health | jq '.components'
```

## Troubleshooting

### Connection Issues
```bash
# Test MCP server directly
python -m tests.test_mcp_client --transport sse --port 3000

# Check logs
tail -f logs/middleware.log
```

### Provider Issues
```bash
# Validate OpenAI configuration
python -c "import openai; print(openai.api_key[:10])"

# Test provider directly
python -m src.cli.llm_test --provider openai --validate-only
```

### Rate Limiting
```bash
# Check current limits
curl http://localhost:8000/api/health | jq '.rate_limits'

# Reset rate limits (dev only)
curl -X POST http://localhost:8000/admin/reset-rate-limits \
  -H "Authorization: Bearer admin-token"
```

## Expected Outputs

### Successful Query Response
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "I found 3 tables in the database:\n1. users - Contains user information\n2. posts - Stores blog posts\n3. comments - Holds user comments",
  "tool_calls": [
    {
      "tool_name": "list_tables",
      "arguments": {},
      "result": {
        "tables": ["users", "posts", "comments"],
        "count": 3
      },
      "duration_ms": 125
    }
  ],
  "provider_used": "openai",
  "model": "gpt-4o",
  "usage": {
    "prompt_tokens": 95,
    "completion_tokens": 47,
    "total_tokens": 142
  },
  "timestamp": "2025-09-23T10:30:00Z",
  "duration_ms": 1847
}
```

### Rate Limit Response
```json
{
  "error": "RATE_LIMITED",
  "message": "Rate limit exceeded. Please wait 60 seconds.",
  "details": {
    "limit": 10,
    "remaining": 0,
    "reset_at": "2025-09-23T10:31:00Z"
  }
}
```

## Next Steps
1. Configure production database
2. Set up monitoring (Prometheus/Grafana)
3. Deploy with Kubernetes
4. Enable SSL/TLS
5. Configure CDN for API

---
*For detailed API documentation, see `/contracts/openapi.yaml`*