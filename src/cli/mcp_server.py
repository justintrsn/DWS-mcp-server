"""MCP server entry point for PostgreSQL operations."""

import sys
import os
import argparse
import threading
import signal
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastmcp import FastMCP
from models.config import DatabaseConfig
from models.error_types import MCPError, InvalidTableError
from services.database_service import DatabaseService
from services.health_api import HealthAPI
from lib.mcp_tools import get_tables, get_columns, get_table_stats
from transport.stdio_server import StdioTransport

# Initialize logging
from lib.logging_config import setup_logging, get_logger

# Setup structured logging
setup_logging(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    json_format=os.getenv('LOG_JSON', 'false').lower() == 'true',
    log_file=os.getenv('LOG_FILE')
)
logger = get_logger(__name__)

# Initialize MCP server
mcp = FastMCP("PostgreSQL MCP Server")

# Global database service instance
db_service: Optional[DatabaseService] = None


def initialize_database():
    """Initialize database connection."""
    global db_service
    try:
        config = DatabaseConfig()
        db_service = DatabaseService(config.to_dict())
        db_service.connect()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@mcp.tool()
async def list_tables(schema: Optional[str] = None) -> Dict[str, Any]:
    """List all tables in the database.
    
    Args:
        schema: Optional schema name to filter tables (default: all schemas)
        
    Returns:
        Dictionary containing:
        - tables: List of table names
        - count: Number of tables
        - schema: Schema name or 'all'
        - database: Database name
    """
    try:
        if not db_service:
            initialize_database()
        return get_tables(db_service, schema)
    except MCPError as e:
        logger.error(f"MCP error in list_tables: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in list_tables: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def describe_table(table_name: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """Get column information for a specific table.
    
    Args:
        table_name: Name of the table to describe
        schema: Optional schema name (default: public)
        
    Returns:
        Dictionary containing:
        - table_name: Name of the table
        - schema: Schema name
        - columns: List of column details
        - column_count: Number of columns
    """
    try:
        if not db_service:
            initialize_database()
        return get_columns(db_service, table_name, schema)
    except InvalidTableError as e:
        logger.error(f"Invalid table error in describe_table: {e}")
        return {
            'error': str(e),
            'table_name': e.table_name,
            'recoverable': e.recoverable
        }
    except MCPError as e:
        logger.error(f"MCP error in describe_table: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in describe_table: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def table_statistics(table_name: Optional[str] = None, 
                          table_names: Optional[list] = None) -> Dict[str, Any]:
    """Get statistics for one or more tables.
    
    Args:
        table_name: Single table name (optional)
        table_names: List of table names (optional)
        
    Returns:
        Dictionary containing table statistics including:
        - row_count: Number of live rows
        - dead_rows: Number of dead rows
        - table_size: Human-readable size
        - size_bytes: Size in bytes
        - index_count: Number of indexes
        - vacuum/analyze information
    """
    try:
        if not db_service:
            initialize_database()
        return get_table_stats(db_service, table_name, table_names)
    except InvalidTableError as e:
        logger.error(f"Invalid table error in table_statistics: {e}")
        return {
            'error': str(e),
            'table_name': e.table_name,
            'recoverable': e.recoverable
        }
    except MCPError as e:
        logger.error(f"MCP error in table_statistics: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in table_statistics: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


def run_health_api(health_api: HealthAPI):
    """Run health API in a separate thread.
    
    Args:
        health_api: Health API instance to run
    """
    try:
        health_api.run()
    except Exception as e:
        logger.error(f"Health API error: {e}")


def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    # Set shutdown flag
    global shutdown_requested
    shutdown_requested = True
    
    # Clean up resources
    cleanup_resources()
    
    sys.exit(0)


def cleanup_resources():
    """Clean up all resources on shutdown."""
    global db_service
    
    logger.info("Cleaning up resources...")
    
    # Close database connections
    if db_service:
        try:
            db_service.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
    
    # Additional cleanup can be added here
    logger.info("Cleanup complete")


# Global shutdown flag
shutdown_requested = False


def main():
    """Main entry point for the MCP server."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PostgreSQL MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode: stdio (default) or sse"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for SSE server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for SSE server (default: 3000)"
    )
    parser.add_argument(
        "--health-port",
        type=int,
        default=8080,
        help="Port for health API (default: 8080)"
    )
    parser.add_argument(
        "--no-health-api",
        action="store_true",
        help="Disable health API service"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize database on startup
        initialize_database()
        
        # Start health API in background thread if enabled
        health_api = None
        health_thread = None
        
        if not args.no_health_api:
            logger.info(f"Starting Health API on port {args.health_port}")
            health_api = HealthAPI(
                db_service=db_service,
                host=args.host,
                port=args.health_port
            )
            health_thread = threading.Thread(
                target=run_health_api,
                args=(health_api,),
                daemon=True
            )
            health_thread.start()
        
        # Select and run transport
        if args.transport == "stdio":
            logger.info("Starting PostgreSQL MCP Server in stdio mode...")
            transport = StdioTransport(mcp)
            transport.run()
        else:  # sse
            logger.info(f"Starting PostgreSQL MCP Server in SSE mode on {args.host}:{args.port}")
            # Use FastMCP's built-in SSE transport
            mcp.run(
                transport="sse",
                host=args.host,
                port=args.port
            )
            
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via keyboard interrupt")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
    finally:
        # Clean up resources on exit
        cleanup_resources()


if __name__ == "__main__":
    main()