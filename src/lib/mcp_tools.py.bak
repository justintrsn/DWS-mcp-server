"""MCP tool implementations for PostgreSQL operations."""

from typing import Dict, Any, List, Optional
from services.database_service import DatabaseService
from services.query_utils import validate_table_name, validate_schema_name, split_table_schema
from models.error_types import InvalidTableError, MCPError


def get_tables(db_service: DatabaseService, schema: Optional[str] = None) -> Dict[str, Any]:
    """Get list of tables in the database.
    
    Args:
        db_service: Database service instance
        schema: Optional schema name to filter tables
        
    Returns:
        Dictionary with table list and metadata
        
    Raises:
        MCPError: If query fails
    """
    # Validate schema if provided
    if schema and not validate_schema_name(schema):
        raise MCPError(f"Invalid schema name: {schema}", recoverable=False)
    
    # Build query
    if schema:
        query = """
            SELECT table_name, table_schema
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        params = (schema,)
    else:
        query = """
            SELECT table_name, table_schema
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
        """
        params = None
    
    # Execute query
    results = db_service.execute_query(query, params)
    
    # Format response
    tables = [row['table_name'] for row in results]
    
    return {
        'tables': tables,
        'count': len(tables),
        'schema': schema if schema else 'all',
        'database': db_service.config.get('database', 'unknown')
    }


def get_columns(db_service: DatabaseService, table_name: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """Get column information for a specific table.
    
    Args:
        db_service: Database service instance
        table_name: Name of the table
        schema: Optional schema name
        
    Returns:
        Dictionary with column details
        
    Raises:
        InvalidTableError: If table doesn't exist
        MCPError: If query fails
    """
    # Validate table name
    if not validate_table_name(table_name):
        raise InvalidTableError(table_name, f"Invalid table name format: {table_name}")
    
    # Split schema from table name if present
    if '.' in table_name and not schema:
        schema, table_name = split_table_schema(table_name)
    
    # Validate schema if provided
    if schema and not validate_schema_name(schema):
        raise MCPError(f"Invalid schema name: {schema}", recoverable=False)
    
    # Build query
    if schema:
        query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                CASE 
                    WHEN pk.column_name IS NOT NULL THEN true 
                    ELSE false 
                END as is_primary_key,
                CASE 
                    WHEN uc.column_name IS NOT NULL THEN true 
                    ELSE false 
                END as is_unique
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_schema = %s
                AND tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_schema = %s
                AND tc.table_name = %s
                AND tc.constraint_type = 'UNIQUE'
            ) uc ON c.column_name = uc.column_name
            WHERE c.table_schema = %s
            AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        params = (schema, table_name, schema, table_name, schema, table_name)
    else:
        query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                CASE 
                    WHEN pk.column_name IS NOT NULL THEN true 
                    ELSE false 
                END as is_primary_key,
                CASE 
                    WHEN uc.column_name IS NOT NULL THEN true 
                    ELSE false 
                END as is_unique
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_name = %s
                AND tc.constraint_type = 'UNIQUE'
            ) uc ON c.column_name = uc.column_name
            WHERE c.table_name = %s
            AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY c.ordinal_position
        """
        params = (table_name, table_name, table_name)
    
    # Execute query
    results = db_service.execute_query(query, params)
    
    # Check if table exists
    if not results:
        raise InvalidTableError(table_name)
    
    # Format columns
    columns = []
    for row in results:
        column = {
            'column_name': row['column_name'],
            'data_type': row['data_type'],
            'nullable': row['is_nullable'] == 'YES',
            'default': row.get('column_default'),
            'primary_key': row.get('is_primary_key', False),
            'unique': row.get('is_unique', False)
        }
        
        # Add type-specific details
        if row.get('character_maximum_length'):
            column['max_length'] = row['character_maximum_length']
        if row.get('numeric_precision'):
            column['precision'] = row['numeric_precision']
        if row.get('numeric_scale'):
            column['scale'] = row['numeric_scale']
        
        columns.append(column)
    
    return {
        'table_name': table_name,
        'schema': schema if schema else 'public',
        'columns': columns,
        'column_count': len(columns)
    }


def get_table_stats(db_service: DatabaseService, 
                   table_name: Optional[str] = None,
                   table_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get statistics for one or more tables.
    
    Args:
        db_service: Database service instance
        table_name: Single table name (optional)
        table_names: List of table names (optional)
        
    Returns:
        Dictionary with table statistics
        
    Raises:
        InvalidTableError: If table doesn't exist
        MCPError: If query fails
    """
    # Handle input parameters
    if table_name and table_names:
        raise MCPError("Provide either table_name or table_names, not both", recoverable=False)
    
    if table_name:
        tables_to_query = [table_name]
    elif table_names:
        tables_to_query = table_names
    else:
        raise MCPError("Either table_name or table_names must be provided", recoverable=False)
    
    # Validate all table names
    for name in tables_to_query:
        if not validate_table_name(name):
            raise InvalidTableError(name, f"Invalid table name format: {name}")
    
    # Build query - use relname which is the actual column name in pg_stat_user_tables
    query = """
        SELECT
            schemaname,
            relname,
            n_live_tup,
            n_dead_tup,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as pg_size_pretty,
            pg_total_relation_size(schemaname||'.'||relname) as pg_total_relation_size,
            pg_relation_size(schemaname||'.'||relname) as pg_relation_size,
            pg_indexes_size(schemaname||'.'||relname) as pg_indexes_size,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze,
            (SELECT COUNT(*) FROM pg_indexes WHERE tablename = pst.relname AND schemaname = pst.schemaname) as n_indexes
        FROM pg_stat_user_tables pst
        WHERE relname = ANY(%s)
        ORDER BY relname
    """
    
    # Execute query
    results = db_service.execute_query(query, (tables_to_query,))
    
    # Check if tables exist
    if not results:
        if len(tables_to_query) == 1:
            raise InvalidTableError(tables_to_query[0])
        else:
            raise MCPError(f"None of the specified tables exist: {', '.join(tables_to_query)}", recoverable=False)
    
    # Format results
    if len(tables_to_query) == 1:
        # Single table response
        row = results[0]
        return {
            'table_name': row['relname'],
            'schema': row.get('schemaname', 'public'),
            'row_count': row['n_live_tup'],
            'dead_rows': row.get('n_dead_tup', 0),
            'table_size': row['pg_size_pretty'],
            'size_bytes': row['pg_total_relation_size'],
            'data_size_bytes': row.get('pg_relation_size', 0),
            'index_size': row.get('pg_indexes_size', 0),  # Alias for compatibility
            'index_size_bytes': row.get('pg_indexes_size', 0),
            'index_count': row.get('n_indexes', 0),
            'last_vacuum': str(row['last_vacuum']) if row.get('last_vacuum') else None,
            'last_autovacuum': str(row['last_autovacuum']) if row.get('last_autovacuum') else None,
            'last_analyze': str(row['last_analyze']) if row.get('last_analyze') else None,
            'last_autoanalyze': str(row['last_autoanalyze']) if row.get('last_autoanalyze') else None
        }
    else:
        # Multiple tables response
        tables = []
        for row in results:
            tables.append({
                'table_name': row['relname'],
                'schema': row.get('schemaname', 'public'),
                'row_count': row['n_live_tup'],
                'dead_rows': row.get('n_dead_tup', 0),
                'table_size': row['pg_size_pretty'],
                'size_bytes': row['pg_total_relation_size'],
                'index_count': row.get('n_indexes', 0)
            })
        
        return {
            'tables': tables,
            'table_count': len(tables)
        }