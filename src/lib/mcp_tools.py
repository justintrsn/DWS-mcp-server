"""MCP Tools Orchestration Layer.

This module provides backward compatibility and a single entry point for all MCP tools.
The actual implementations are organized in the tools package by operational level.

Structure:
- tools/database.py: Database-level operations
- tools/schema.py: Schema-level operations
- tools/table.py: Table-level operations

This orchestration layer maintains the original API while delegating to the
modular implementations.
"""

from typing import Dict, Any, Optional, List

# Import all tools from the modular package
from .tools import (
    # Database-level tools
    get_database_stats,
    get_connection_info,
    # Schema-level tools
    list_schemas,
    # Table-level tools
    get_tables,
    get_columns,
    get_table_stats,
    get_column_statistics,
    # Object-level tools
    inspect_database_object,
    analyze_query_plan,
    enumerate_views,
    enumerate_functions,
    enumerate_indexes,
    fetch_table_constraints,
    analyze_object_dependencies
)

# Re-export all tools for backward compatibility
__all__ = [
    # Database tools
    'get_database_stats',
    'get_connection_info',
    # Schema tools
    'list_schemas',
    # Table tools
    'get_tables',
    'get_columns',
    'get_table_stats',
    'get_column_statistics',
    # Object tools
    'inspect_database_object',
    'analyze_query_plan',
    'enumerate_views',
    'enumerate_functions',
    'enumerate_indexes',
    'fetch_table_constraints',
    'analyze_object_dependencies'
]

# Optional: Add convenience functions or orchestration logic here
# For example, a function that combines multiple tool calls:

def get_database_overview(db_service) -> Dict[str, Any]:
    """Get a comprehensive overview of the database.

    This orchestrates multiple tool calls to provide a complete picture.

    Args:
        db_service: Database service instance

    Returns:
        Dictionary containing database overview information
    """
    overview = {}

    # Get database stats
    overview['database'] = get_database_stats(db_service)

    # Get connection info
    overview['connections'] = get_connection_info(db_service, by_state=True)

    # Get schema summary
    schema_info = list_schemas(db_service, include_system=False)
    overview['schemas'] = {
        'count': schema_info['count'],
        'user_schemas': [s['schema_name'] for s in schema_info['schemas']
                        if s['schema_type'] == 'User Schema']
    }

    # Get table summary
    table_info = get_tables(db_service)
    overview['tables'] = {
        'total_count': table_info['count'],
        'by_schema': {}
    }

    # Group tables by schema
    for table in table_info['tables']:
        schema = table['schema_name']
        if schema not in overview['tables']['by_schema']:
            overview['tables']['by_schema'][schema] = 0
        overview['tables']['by_schema'][schema] += 1

    return overview