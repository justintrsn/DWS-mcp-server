"""Schema-level MCP tools for PostgreSQL operations.

This module contains tools that operate at the schema level,
managing and inspecting database schemas.
"""

from typing import Dict, Any, Optional
from lib.logging_config import get_logger
from models.error_types import MCPError
from services.database_service import DatabaseService

logger = get_logger(__name__)


def list_schemas(db_service: DatabaseService,
                include_system: bool = False,
                include_sizes: bool = False) -> Dict[str, Any]:
    """List all database schemas with ownership and classification.

    Args:
        db_service: Database service instance
        include_system: Include system schemas (pg_*, information_schema)
        include_sizes: Include schema sizes (slower query)

    Returns:
        Dictionary containing:
        - schemas: List of schema information
        - count: Number of schemas
        - database: Database name
    """
    # Base query for schema information
    base_query = """
        SELECT
            n.nspname as schema_name,
            pg_catalog.pg_get_userbyid(n.nspowner) as schema_owner,
            CASE
                WHEN n.nspname IN ('information_schema') THEN 'System Information Schema'
                WHEN n.nspname LIKE 'pg_%' THEN 'System Schema'
                WHEN n.nspname = 'public' THEN 'Public Schema'
                ELSE 'User Schema'
            END as schema_type,
            (
                SELECT COUNT(*)
                FROM pg_catalog.pg_class c
                WHERE c.relnamespace = n.oid
                AND c.relkind IN ('r', 'p')
            ) as table_count,
            (
                SELECT COUNT(*)
                FROM pg_catalog.pg_class c
                WHERE c.relnamespace = n.oid
                AND c.relkind = 'v'
            ) as view_count,
            (
                SELECT COUNT(*)
                FROM pg_catalog.pg_proc p
                WHERE p.pronamespace = n.oid
            ) as function_count
        FROM pg_catalog.pg_namespace n
        WHERE 1=1
    """

    # Add system schema filter if needed
    if not include_system:
        base_query += """
            AND n.nspname NOT LIKE 'pg_%'
            AND n.nspname NOT IN ('information_schema')
        """

    base_query += "\nORDER BY n.nspname"

    # Execute base query
    results = db_service.execute_readonly_query(base_query)

    if results is None:
        raise MCPError("Failed to retrieve schema list", recoverable=True)

    schemas = []
    for row in results:
        schema_info = {
            'schema_name': row['schema_name'],
            'schema_owner': row['schema_owner'],
            'schema_type': row['schema_type'],
            'table_count': row.get('table_count', 0),
            'view_count': row.get('view_count', 0),
            'function_count': row.get('function_count', 0)
        }

        # Add sizes if requested (slower query)
        if include_sizes:
            size_query = """
                SELECT
                    SUM(pg_total_relation_size(c.oid)) as total_size
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s
            """
            size_results = db_service.execute_readonly_query(
                size_query,
                (row['schema_name'],)
            )

            if size_results and size_results[0]['total_size']:
                total_size = size_results[0]['total_size']
                schema_info['size_bytes'] = total_size
                schema_info['size_pretty'] = _format_size(total_size)

        schemas.append(schema_info)

    return {
        'database': db_service.config.get('database', 'unknown'),
        'count': len(schemas),
        'schemas': schemas
    }


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "10 MB", "2 GB")
    """
    if size_bytes is None or size_bytes == 0:
        return "0 bytes"

    units = ['bytes', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    # Format based on size
    if unit_index == 0:  # bytes
        return f"{int(size)} {units[unit_index]}"
    elif size >= 10:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"