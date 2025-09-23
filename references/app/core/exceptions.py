class MCPServerError(Exception):
    """Raised when all MCP servers fail to process a request."""
    pass

class TemplateError(Exception):
    """Raised when there is an error processing templates."""
    pass

class ReactError(Exception):
    """Raised when there is an error in the React pattern processing."""
    pass