# Multi-stage Docker build for PostgreSQL MCP Server
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mcp && \
    mkdir -p /app && \
    chown -R mcp:mcp /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/mcp/.local

# Set work directory and user
WORKDIR /app
USER mcp

# Ensure local Python packages are in PATH
ENV PATH=/home/mcp/.local/bin:$PATH

# Copy application code
COPY --chown=mcp:mcp src/ ./src/
COPY --chown=mcp:mcp scripts/ ./scripts/
COPY --chown=mcp:mcp requirements.txt ./

# Create config directory for database configurations
RUN mkdir -p /app/config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
EXPOSE 3000 8080

# Default environment variables
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV DATABASE_PROFILE=anime

# Default command - can be overridden
CMD ["python", "-m", "src.cli.mcp_server", "--transport", "sse", "--host", "0.0.0.0", "--port", "3000"]