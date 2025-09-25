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
from lib.mcp_tools import (
    get_tables, get_columns, get_table_stats, get_column_statistics,
    list_schemas, get_database_stats, get_connection_info,
    inspect_database_object, analyze_query_plan, enumerate_views,
    enumerate_functions, enumerate_indexes, fetch_table_constraints,
    analyze_object_dependencies
)

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
    """Get table metadata and storage information (NOT mathematical statistics).

    This tool returns table-level metadata like size, row counts, and maintenance info.
    For mathematical statistics and outlier detection, use column_statistics instead.

    Args:
        table_name: Single table name (optional)
        table_names: List of table names (optional)

    Returns:
        Dictionary containing table metadata including:
        - row_count: Number of live rows
        - dead_rows: Number of dead rows
        - table_size: Storage size (bytes and human-readable)
        - index_count: Number of indexes
        - vacuum/analyze: Maintenance information
        - activity: Scan and update metrics
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


# ============================================================================
# Database-Level Tools (T011-T013)
# ============================================================================

@mcp.tool()
async def schemas_list(include_system: bool = False,
                       include_sizes: bool = False) -> Dict[str, Any]:
    """List all database schemas with ownership and classification.

    Args:
        include_system: Include system schemas (pg_*, information_schema)
        include_sizes: Include schema sizes (slower query)

    Returns:
        Dictionary containing:
        - schemas: List of schema information
        - count: Number of schemas
        - database: Database name
    """
    try:
        if not db_service:
            initialize_database()
        return list_schemas(db_service, include_system, include_sizes)
    except MCPError as e:
        logger.error(f"MCP error in schemas_list: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in schemas_list: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def database_stats() -> Dict[str, Any]:
    """Get comprehensive database statistics and metrics.

    Returns:
        Dictionary containing database statistics including:
        - Database name, size, connections
        - Transaction statistics
        - Cache hit ratio
        - Temporary files usage
    """
    try:
        if not db_service:
            initialize_database()
        return get_database_stats(db_service)
    except MCPError as e:
        logger.error(f"MCP error in database_stats: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in database_stats: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def connection_info(by_state: bool = True,
                         by_database: bool = False) -> Dict[str, Any]:
    """Get current database connection information and statistics.

    Args:
        by_state: Group connections by state
        by_database: Group connections by database

    Returns:
        Dictionary containing connection information including:
        - Current and max connections
        - Connection states breakdown
        - Per-database connection counts (if requested)
        - Connection saturation warnings
    """
    try:
        if not db_service:
            initialize_database()
        return get_connection_info(db_service, by_state, by_database)
    except MCPError as e:
        logger.error(f"MCP error in connection_info: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in connection_info: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def column_statistics(table_name: str,
                           column_names: Optional[list] = None,
                           schema: str = 'public',
                           include_outliers: bool = True,
                           outlier_method: str = 'iqr') -> Dict[str, Any]:
    """Analyze numeric columns for outliers and statistical distributions.

    Use this tool to detect outliers, analyze data distributions, and get
    mathematical statistics for numeric columns (similar to pandas describe()).

    Args:
        table_name: Table name to analyze
        column_names: Optional list of columns to analyze (defaults to all numeric)
        schema: Schema name (default: 'public')
        include_outliers: Whether to detect outliers (default: True)
        outlier_method: Method for outlier detection ('iqr' or 'zscore', default: 'iqr')

    Returns:
        Dictionary containing mathematical statistics for each column:
        - Outlier detection: Count and percentage of outliers
        - Central tendency: mean, median, mode
        - Spread: std deviation, variance, IQR, range
        - Percentiles: 5%, 25%, 50% (median), 75%, 95%
        - Distribution: skewness
        - Data quality: null count, distinct values
    """
    try:
        if not db_service:
            initialize_database()
        return get_column_statistics(db_service, table_name, column_names,
                                    schema, include_outliers, outlier_method)
    except InvalidTableError as e:
        logger.error(f"Invalid table error in column_statistics: {e}")
        return {
            'error': str(e),
            'table_name': e.table_name,
            'recoverable': e.recoverable
        }
    except MCPError as e:
        logger.error(f"MCP error in column_statistics: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in column_statistics: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


# ============================================================================
# Phase 3 Object-Level Tools (T014-T020)
# ============================================================================

@mcp.tool()
async def describe_object(object_name: str,
                         object_type: Optional[str] = None,
                         schema: str = 'public') -> Dict[str, Any]:
    """Universal object inspector for any database object.

    Get detailed information about any database object (table, view, function,
    index, sequence, etc.) with comprehensive metadata.

    Args:
        object_name: Name of the object to describe
        object_type: Optional type hint ('table', 'view', 'function', 'index', etc.)
        schema: Schema name (default: 'public')

    Returns:
        Dictionary containing object details specific to its type:
        - Tables: columns, constraints, indexes, triggers
        - Views: definition, columns, dependencies
        - Functions: signature, source code, language
        - Indexes: columns, type, size
        - Sequences: current value, increment
    """
    try:
        if not db_service:
            initialize_database()
        return inspect_database_object(db_service, object_name, object_type, schema)
    except MCPError as e:
        logger.error(f"MCP error in describe_object: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in describe_object: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def explain_query(query: str,
                       analyze: bool = False,
                       format: str = 'json') -> Dict[str, Any]:
    """Get execution plan for a SQL query.

    Analyze how PostgreSQL will execute a query, including cost estimates,
    join strategies, and index usage.

    Args:
        query: SQL query to explain
        analyze: Execute query and show actual times (default: False)
        format: Output format ('text', 'json', 'xml', 'yaml', default: 'json')

    Returns:
        Dictionary containing query plan with:
        - Execution plan tree
        - Total cost and time estimates
        - Index usage information
        - Join methods and order
        - Actual vs estimated rows (if analyze=True)
    """
    try:
        if not db_service:
            initialize_database()
        return analyze_query_plan(db_service, query, analyze, format)
    except MCPError as e:
        logger.error(f"MCP error in explain_query: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in explain_query: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def list_views(schema: Optional[str] = None,
                    include_system: bool = False) -> Dict[str, Any]:
    """List all views in the database.

    Args:
        schema: Optional schema name to filter views (default: all schemas)
        include_system: Include system views (default: False)

    Returns:
        Dictionary containing:
        - views: List of view information
        - count: Number of views
        - by_schema: Views grouped by schema
    """
    try:
        if not db_service:
            initialize_database()
        return enumerate_views(db_service, schema, include_system)
    except MCPError as e:
        logger.error(f"MCP error in list_views: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in list_views: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def list_functions(schema: Optional[str] = None,
                        include_system: bool = False) -> Dict[str, Any]:
    """List all functions and stored procedures.

    Args:
        schema: Optional schema name to filter (default: all schemas)
        include_system: Include system functions (default: False)

    Returns:
        Dictionary containing:
        - functions: List of function information
        - count: Number of functions
        - by_language: Functions grouped by implementation language
    """
    try:
        if not db_service:
            initialize_database()
        return enumerate_functions(db_service, schema, include_system)
    except MCPError as e:
        logger.error(f"MCP error in list_functions: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in list_functions: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def list_indexes(table_name: Optional[str] = None,
                      schema: str = 'public',
                      include_unused: bool = True) -> Dict[str, Any]:
    """List indexes for tables.

    Args:
        table_name: Optional table name (default: all tables)
        schema: Schema name (default: 'public')
        include_unused: Include unused indexes (default: True)

    Returns:
        Dictionary containing:
        - indexes: List of index information
        - count: Number of indexes
        - by_table: Indexes grouped by table
        - usage_stats: Index scan statistics
    """
    try:
        if not db_service:
            initialize_database()
        return enumerate_indexes(db_service, table_name, schema, include_unused)
    except MCPError as e:
        logger.error(f"MCP error in list_indexes: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in list_indexes: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def get_table_constraints(table_name: str,
                               schema: str = 'public') -> Dict[str, Any]:
    """Get all constraints for a table.

    Args:
        table_name: Table name
        schema: Schema name (default: 'public')

    Returns:
        Dictionary containing:
        - constraints: List of constraint details
        - by_type: Constraints grouped by type
        - foreign_key_graph: Relationships to other tables
    """
    try:
        if not db_service:
            initialize_database()
        return fetch_table_constraints(db_service, table_name, schema)
    except InvalidTableError as e:
        logger.error(f"Invalid table error in get_table_constraints: {e}")
        return {
            'error': str(e),
            'table_name': e.table_name,
            'recoverable': e.recoverable
        }
    except MCPError as e:
        logger.error(f"MCP error in get_table_constraints: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_table_constraints: {e}")
        return {
            'error': f"Unexpected error: {str(e)}",
            'recoverable': False
        }


@mcp.tool()
async def get_dependencies(object_name: str,
                          object_type: str,
                          schema: str = 'public',
                          direction: str = 'both') -> Dict[str, Any]:
    """Get object dependencies (what depends on this, what this depends on).

    Args:
        object_name: Name of the object
        object_type: Type of object ('table', 'view', 'function', etc.)
        schema: Schema name (default: 'public')
        direction: 'depends_on', 'referenced_by', or 'both' (default: 'both')

    Returns:
        Dictionary containing:
        - depends_on: Objects this object depends on
        - referenced_by: Objects that depend on this object
        - dependency_graph: Visual representation of dependencies
    """
    try:
        if not db_service:
            initialize_database()
        return analyze_object_dependencies(db_service, object_name, schema, direction)
    except MCPError as e:
        logger.error(f"MCP error in get_dependencies: {e}")
        return {
            'error': str(e),
            'recoverable': e.recoverable
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_dependencies: {e}")
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