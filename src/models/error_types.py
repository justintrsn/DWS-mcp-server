"""Error types for PostgreSQL MCP Server."""

class MCPError(Exception):
    """Base error class for MCP operations."""
    
    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.recoverable = recoverable


class InvalidTableError(MCPError):
    """Error raised when a table name is invalid or doesn't exist."""
    
    def __init__(self, table_name: str, message: str = None):
        if message is None:
            message = f"Table '{table_name}' does not exist or is invalid"
        super().__init__(message, recoverable=False)
        self.table_name = table_name


class InvalidQueryError(MCPError):
    """Error raised when a query is unsafe or invalid for execution."""

    def __init__(self, query: str, reason: str):
        message = f"Invalid query: {reason}. Query: {query[:100]}{'...' if len(query) > 100 else ''}"
        super().__init__(message, recoverable=False)
        self.query = query
        self.reason = reason


class ConnectionError(MCPError):
    """Error raised when database connection fails."""

    def __init__(self, message: str):
        super().__init__(message, recoverable=True)