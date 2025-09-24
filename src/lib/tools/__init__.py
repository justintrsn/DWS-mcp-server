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
    describe_object,
    explain_query,
    list_views,
    list_functions,
    list_indexes,
    get_table_constraints,
    get_dependencies
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
    'describe_object',
    'explain_query',
    'list_views',
    'list_functions',
    'list_indexes',
    'get_table_constraints',
    'get_dependencies'
]