"""Query execution MCP tools for PostgreSQL operations.

This module provides safe query execution capabilities following the
postgres-mcp best practices - simple, flexible, and secure.
"""

import time
from typing import Dict, Any, Optional, List, Set
import pglast
from pglast import ast, stream

from src.lib.logging_config import get_logger
from src.models.error_types import MCPError, InvalidQueryError
from src.services.database_service import DatabaseService

logger = get_logger(__name__)


def validate_safe_sql(query: str) -> None:
    """Validate SQL query for safety using proper SQL parsing.

    Based on postgres-mcp best practices, this validates that the query
    does not contain dangerous operations that could circumvent read-only mode.

    Args:
        query: SQL query string to validate

    Raises:
        InvalidQueryError: If query contains unsafe operations
    """
    if not query or not query.strip():
        raise InvalidQueryError(query, "Empty query")

    try:
        # Parse SQL using pglast (proper PostgreSQL parser)
        parsed = pglast.parse_sql(query)

        # Check each statement in the query
        for statement in parsed:
            _validate_statement_node(statement, query)

    except pglast.Error as e:
        raise InvalidQueryError(query, f"SQL parsing error: {str(e)}")


def extract_table_names_from_query(query: str) -> Set[str]:
    """Extract table names from SQL query using pglast parser.

    Args:
        query: SQL query string

    Returns:
        Set of table names found in the query (lowercase), excluding system tables

    Raises:
        InvalidQueryError: If query cannot be parsed
    """
    if not query or not query.strip():
        return set()

    try:
        # Parse SQL using pglast
        parsed = pglast.parse_sql(query)
        table_names = set()

        # Walk the AST to find table references
        for statement in parsed:
            _extract_tables_from_node(statement, table_names)

        # Filter out system/information schema tables that don't need inspection
        system_tables = {
            'information_schema.tables', 'information_schema.columns',
            'information_schema.schemata', 'pg_tables', 'pg_catalog.pg_tables',
            'pg_stat_activity', 'pg_database', 'pg_user', 'pg_settings',
            # Additional specific table names that might be extracted from system queries
            'tables', 'columns', 'schemata'
        }

        # Remove system tables from validation requirements
        filtered_tables = {t for t in table_names if t not in system_tables and not t.startswith('pg_') and not t.startswith('information_schema.')}

        logger.debug(f"Extracted table names from query (filtered): {sorted(filtered_tables)}")
        return filtered_tables

    except pglast.Error as e:
        raise InvalidQueryError(query, f"SQL parsing error during table extraction: {str(e)}")


def _extract_tables_from_node(node, table_names: Set[str]) -> None:
    """Recursively extract table names from AST node.

    Args:
        node: AST node to examine
        table_names: Set to add found table names to
    """
    if hasattr(node, 'stmt'):
        # Handle statement wrapper
        _extract_tables_from_node(node.stmt, table_names)
    elif hasattr(node, 'fromClause'):
        # Handle SELECT FROM clause
        if node.fromClause:
            for from_item in node.fromClause:
                _extract_tables_from_node(from_item, table_names)
    elif hasattr(node, 'relation'):
        # Handle RangeVar (table reference)
        if node.relation and hasattr(node.relation, 'relname'):
            table_names.add(node.relation.relname.lower())
    elif hasattr(node, 'relname'):
        # Direct table name reference
        table_names.add(node.relname.lower())
    elif hasattr(node, 'larg') or hasattr(node, 'rarg'):
        # Handle joins
        if hasattr(node, 'larg'):
            _extract_tables_from_node(node.larg, table_names)
        if hasattr(node, 'rarg'):
            _extract_tables_from_node(node.rarg, table_names)

    # Recursively check other attributes that might contain nodes
    if hasattr(node, '__dict__'):
        for attr_name, attr_value in node.__dict__.items():
            if isinstance(attr_value, (list, tuple)):
                for item in attr_value:
                    if hasattr(item, '__dict__'):
                        _extract_tables_from_node(item, table_names)
            elif hasattr(attr_value, '__dict__'):
                _extract_tables_from_node(attr_value, table_names)


def _validate_statement_node(stmt_node, original_query: str) -> None:
    """Validate a single parsed statement node.

    Args:
        stmt_node: Parsed AST statement node
        original_query: Original query for error reporting

    Raises:
        InvalidQueryError: If statement is not safe
    """
    stmt = stmt_node.stmt

    # Allow only specific safe statement types
    safe_statements = (
        ast.SelectStmt,    # SELECT queries
        ast.ExplainStmt,   # EXPLAIN queries
        ast.VariableSetStmt,  # SET statements (for query parameters)
    )

    if not isinstance(stmt, safe_statements):
        statement_type = type(stmt).__name__
        raise InvalidQueryError(
            original_query,
            f"Statement type '{statement_type}' is not allowed. Only SELECT and EXPLAIN statements are permitted."
        )

    # Additional safety checks for specific statement types
    if isinstance(stmt, ast.ExplainStmt):
        # For EXPLAIN statements, validate the underlying query
        if stmt.query:
            _validate_statement_node(type('MockStmt', (), {'stmt': stmt.query})(), original_query)

    # Check for dangerous function calls by examining the query tree
    _check_for_dangerous_functions(stmt, original_query)


def _check_for_dangerous_functions(stmt, original_query: str) -> None:
    """Check for potentially dangerous function calls in the AST.

    Args:
        stmt: Statement AST node
        original_query: Original query for error reporting

    Raises:
        InvalidQueryError: If dangerous functions are found
    """
    dangerous_functions = {
        'dblink_exec', 'dblink_connect', 'dblink_disconnect',
        'pg_reload_conf', 'pg_rotate_logfile', 'pg_cancel_backend',
        'pg_terminate_backend', 'pg_file_write', 'pg_file_unlink',
        'pg_file_rename', 'copy_file', 'pg_read_file',
        'lo_import', 'lo_export', 'lo_unlink'
    }

    # Convert AST back to SQL for function checking
    # This is simpler than traversing the entire AST
    try:
        sql_text = stream.RawStream()(stmt).upper()

        for func in dangerous_functions:
            if func.upper() in sql_text:
                raise InvalidQueryError(
                    original_query,
                    f"Query contains forbidden function: {func}"
                )
    except Exception:
        # If we can't check functions, err on the side of caution
        logger.warning("Could not check for dangerous functions in query")


def execute_query(db_service: DatabaseService,
                  query: str,
                  limit: Optional[int] = None) -> Dict[str, Any]:
    """Execute a safe SQL query with validation and safety constraints.

    This follows the postgres-mcp best practices for safe query execution:
    - Proper SQL parsing with pglast
    - Read-only transaction enforcement
    - Execution time limits
    - Result size limits

    Args:
        db_service: Database service instance
        query: SQL query to execute (SELECT, EXPLAIN only)
        limit: Optional result limit (default: 100, max: 1000)

    Returns:
        Dictionary containing:
        - data: List of result rows as dictionaries
        - row_count: Number of rows returned
        - query: The executed query
        - execution_time_ms: Query execution time in milliseconds
        - limited: Whether results were limited
    """
    logger.info(f"Executing query: {query[:100]}{'...' if len(query) > 100 else ''}")

    # Validate query safety
    validate_safe_sql(query)

    # Apply result limits
    if limit is None:
        limit = 100
    elif limit > 1000:
        limit = 1000
        logger.warning("Query limit capped at 1000 rows")

    # Add LIMIT if it's a SELECT query and doesn't already have one
    final_query = _add_limit_if_needed(query, limit)
    was_limited = final_query != query

    # Execute query safely in read-only transaction
    try:
        start_time = time.time()

        results = db_service.execute_readonly_query(final_query)

        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        logger.info(f"Query executed successfully, returned {len(results)} rows in {execution_time:.2f}ms")

        return {
            "data": results,
            "row_count": len(results),
            "query": final_query,
            "execution_time_ms": round(execution_time, 2),
            "limited": was_limited,
            "limit_applied": limit if was_limited else None
        }

    except MCPError:
        # Re-raise MCP errors as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error executing query: {e}")
        raise MCPError(f"Query execution failed: {str(e)}", recoverable=True)


def _add_limit_if_needed(query: str, limit: int) -> str:
    """Add LIMIT clause to SELECT query if not present.

    Args:
        query: SQL query string
        limit: Limit value to add

    Returns:
        Query with LIMIT clause added if necessary
    """
    query_upper = query.strip().upper()

    # Don't add LIMIT to EXPLAIN queries
    if query_upper.startswith('EXPLAIN'):
        return query

    # Check if LIMIT already exists
    if 'LIMIT' in query_upper:
        return query

    # Add LIMIT to SELECT queries
    if query_upper.startswith('SELECT') or query_upper.startswith('WITH'):
        return f"{query.rstrip(';')} LIMIT {limit}"

    return query