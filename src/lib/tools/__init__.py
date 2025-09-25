"""MCP Tools Package - Modular tool implementations for PostgreSQL operations.

This package provides a modular architecture for MCP tools, organized by
operational level (database, schema, table). Each module contains focused
tools for its specific domain.

Structure:
- database.py: Database-level operations (stats, connections)
- schema.py: Schema-level operations (listing, management)
- table.py: Table-level operations (listing, columns, statistics)
"""

# Database-level tools
from .database import (
    get_database_stats,
    get_connection_info
)

# Schema-level tools
from .schema import (
    list_schemas
)

# Table-level tools
from .table import (
    get_tables,
    get_columns,
    get_table_stats,
    get_column_statistics
)

# Object-level tools
from .objects import (
    inspect_database_object,
    analyze_query_plan,
    enumerate_views,
    enumerate_functions,
    enumerate_indexes,
    fetch_table_constraints,
    analyze_object_dependencies
)

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