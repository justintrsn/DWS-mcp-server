# Research: OpenAI-Compatible MCP Middleware Implementation

**Date**: 2025-09-23
**Feature**: OpenAI-Compatible MCP Middleware for Agent Interaction

## Research Areas

### 1. OpenAI Function Calling Pattern
**Decision**: Use OpenAI's tools API with structured outputs
**Rationale**:
- Native support for function calling in OpenAI API
- Structured outputs ensure consistent responses
- Compatible with Huawei MaaS OpenAI-compatible endpoints
**Alternatives considered**:
- Custom prompt engineering: Rejected - less reliable
- Direct function mapping: Rejected - not standardized

**Implementation Pattern**:
```python
# Tool format conversion
openai_tool = {
    "type": "function",
    "function": {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.inputSchema
    }
}
```

### 2. MCP Transport Architecture
**Decision**: Use abstraction layer with stdio and SSE support
**Rationale**:
- Stdio best for local/desktop integrations
- SSE (Server-Sent Events) for production servers
- HTTP transport recommended for 2024+ deployments
**Alternatives considered**:
- WebSocket: Rejected - more complex, overkill for request/response
- gRPC: Rejected - not supported by MCP standard

**Implementation Pattern**:
- Base transport interface
- Separate implementations for each transport
- Connection pooling for HTTP/SSE
- Process-per-session for stdio

### 3. Rate Limiting Strategy
**Decision**: Token bucket algorithm with per-client tracking
**Rationale**:
- Smooth traffic shaping
- Allows burst handling
- Fair resource allocation
**Alternatives considered**:
- Fixed window: Rejected - can cause thundering herd
- Sliding window: Rejected - more complex, minimal benefit
- Leaky bucket: Rejected - doesn't handle bursts well

**Implementation Pattern**:
- 10 tokens capacity (requests)
- 1/6 token per second refill rate (10 per minute)
- Background refill task
- Per-client isolation

### 4. Connection Pooling
**Decision**: Async connection pool with health checks
**Rationale**:
- Reuse connections for performance
- Health checks prevent stale connections
- Automatic cleanup of expired connections
**Alternatives considered**:
- No pooling: Rejected - poor performance
- Simple queue: Rejected - no health management
- Thread pool: Rejected - not async-native

**Implementation Pattern**:
- Min 2, max 10 connections
- 5-minute idle timeout
- Health checks before reuse
- Exponential backoff retry

## Integration Patterns

### LLM Provider Abstraction
```python
class LLMProvider(Protocol):
    async def complete(messages, tools) -> Response
    async def validate_config() -> bool
```

### Transport Abstraction
```python
class MCPTransport(Protocol):
    async def connect() -> Session
    async def call_tool(name, args) -> Result
    async def list_tools() -> List[Tool]
```

### Middleware Pipeline
```
Request → Rate Limit → LLM Provider → Tool Execution → Response
```

## Configuration Strategy
**Decision**: Environment variables with defaults
**Rationale**:
- Standard for containerized deployments
- Easy override for different environments
- Secure for sensitive credentials

**Key Variables**:
- `LLM_PROVIDER`: 'openai' (default) or 'huawei_maas'
- `OPENAI_API_KEY`: OpenAI authentication
- `OPENAI_MODEL`: 'gpt-4o' (only supported model)
- `MAAS_*`: Huawei MaaS configuration
- `MCP_TRANSPORT`: 'stdio' or 'sse'
- `MCP_SERVER_URL`: For SSE transport

## Error Handling Strategy
**Decision**: Graceful degradation with detailed logging
**Rationale**:
- User-friendly error messages
- Detailed logs for debugging
- Automatic retry for transient failures

**Error Categories**:
1. **Recoverable**: Connection issues, rate limits
   - Retry with exponential backoff
2. **Non-recoverable**: Invalid queries, auth failures
   - Return clear error message
3. **Partial**: Some tools fail
   - Complete with available data, note failures

## Testing Strategy
**Decision**: Real services with Docker containers
**Rationale**:
- Catches integration issues early
- Reflects production behavior
- Docker ensures consistency

**Test Levels**:
1. **Contract Tests**: API schema validation
2. **Integration Tests**: Real LLM + MCP calls
3. **E2E Tests**: Complete query lifecycle
4. **Performance Tests**: Rate limiting, concurrency

## Performance Considerations
- **Connection Reuse**: Pool connections to MCP servers
- **Parallel Tool Execution**: Use asyncio.gather for multiple tools
- **Response Streaming**: Support streaming for large responses
- **Caching**: Cache tool discoveries for 30 minutes

## Security Considerations
- **API Key Management**: Never log sensitive keys
- **Input Validation**: Sanitize all user inputs
- **Rate Limiting**: Prevent abuse
- **Timeout Protection**: 30s per tool, 60s total

## Monitoring & Observability
- **Structured Logging**: JSON format with trace IDs
- **Metrics**: Request count, latency, error rate
- **Health Checks**: `/health` endpoint
- **Tracing**: Optional OpenTelemetry support

---
*All technical clarifications resolved. Ready for Phase 1: Design & Contracts*