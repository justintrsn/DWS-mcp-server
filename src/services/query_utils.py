"""Query utilities for SQL injection prevention and validation."""

import re
from typing import Optional


def validate_table_name(table_name: str) -> bool:
    """Validate table name to prevent SQL injection.
    
    Args:
        table_name: Table name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Allow alphanumeric, underscore, and dot (for schema.table)
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$'
    return bool(re.match(pattern, table_name))


def validate_schema_name(schema_name: str) -> bool:
    """Validate schema name to prevent SQL injection.
    
    Args:
        schema_name: Schema name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Allow alphanumeric and underscore
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    return bool(re.match(pattern, schema_name))


def validate_column_name(column_name: str) -> bool:
    """Validate column name to prevent SQL injection.
    
    Args:
        column_name: Column name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Allow alphanumeric and underscore
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    return bool(re.match(pattern, column_name))


def escape_identifier(identifier: str) -> str:
    """Escape a SQL identifier for safe use in queries.
    
    Args:
        identifier: Identifier to escape
        
    Returns:
        Escaped identifier
    """
    # Remove any existing quotes and re-quote
    identifier = identifier.replace('"', '')
    return f'"{identifier}"'


def split_table_schema(full_table_name: str) -> tuple[Optional[str], str]:
    """Split a table name into schema and table parts.
    
    Args:
        full_table_name: Table name, possibly with schema (e.g., 'public.users')
        
    Returns:
        Tuple of (schema, table_name) where schema may be None
    """
    parts = full_table_name.split('.')
    if len(parts) == 2:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return None, parts[0]
    else:
        raise ValueError(f"Invalid table name format: {full_table_name}")