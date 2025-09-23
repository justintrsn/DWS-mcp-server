"""MCP tool implementations for PostgreSQL operations."""

from typing import Dict, Any, List, Optional
from src.services.database_service import DatabaseService
from src.services.query_utils import validate_table_name, validate_schema_name, split_table_schema
from src.models.error_types import InvalidTableError, MCPError


def get_tables(db_service: DatabaseService, schema: Optional[str] = None) -> Dict[str, Any]:
    """Get list of tables in the database with enhanced metadata.

    Args:
        db_service: Database service instance
        schema: Optional schema name to filter tables

    Returns:
        Dictionary with table list and metadata including:
        - table_name: Name of the table
        - schema: Schema containing the table
        - table_type: Type of table (BASE TABLE, VIEW, etc.)
        - owner: Table owner
        - row_count: Estimated row count
        - size_bytes: Table size in bytes
        - size_pretty: Human-readable size
        - index_count: Number of indexes
        - has_toast: Whether table has TOAST storage

    Raises:
        MCPError: If query fails
    """
    # Validate schema if provided
    if schema and not validate_schema_name(schema):
        raise MCPError(f"Invalid schema name: {schema}", recoverable=False)

    # Build enhanced query with metadata
    if schema:
        query = """
            SELECT
                t.table_name,
                t.table_schema as schema,
                t.table_type,
                pg_get_userbyid(c.relowner) as owner,
                COALESCE(s.n_live_tup, 0) as row_count,
                pg_total_relation_size(quote_ident(t.table_schema)||'.'||quote_ident(t.table_name)) as size_bytes,
                pg_size_pretty(pg_total_relation_size(quote_ident(t.table_schema)||'.'||quote_ident(t.table_name))) as size_pretty,
                (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = t.table_schema AND tablename = t.table_name) as index_count,
                c.reltoastrelid != 0 as has_toast
            FROM information_schema.tables t
            LEFT JOIN pg_class c ON c.relname = t.table_name
                AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = t.table_schema)
            LEFT JOIN pg_stat_user_tables s ON s.schemaname = t.table_schema AND s.relname = t.table_name
            WHERE t.table_schema = %s
            AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """
        params = (schema,)
    else:
        query = """
            SELECT
                t.table_name,
                t.table_schema as schema,
                t.table_type,
                pg_get_userbyid(c.relowner) as owner,
                COALESCE(s.n_live_tup, 0) as row_count,
                pg_total_relation_size(quote_ident(t.table_schema)||'.'||quote_ident(t.table_name)) as size_bytes,
                pg_size_pretty(pg_total_relation_size(quote_ident(t.table_schema)||'.'||quote_ident(t.table_name))) as size_pretty,
                (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = t.table_schema AND tablename = t.table_name) as index_count,
                c.reltoastrelid != 0 as has_toast
            FROM information_schema.tables t
            LEFT JOIN pg_class c ON c.relname = t.table_name
                AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = t.table_schema)
            LEFT JOIN pg_stat_user_tables s ON s.schemaname = t.table_schema AND s.relname = t.table_name
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
            AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_schema, t.table_name
        """
        params = None

    # Execute query with read-only safety
    results = db_service.execute_readonly_query(query, params)

    # Format enhanced response
    tables = []
    for row in results:
        tables.append({
            'table_name': row['table_name'],
            'schema': row['schema'],
            'table_type': row['table_type'],
            'owner': row.get('owner', 'unknown'),
            'row_count': row.get('row_count', 0),
            'size_bytes': row.get('size_bytes', 0),
            'size_pretty': row.get('size_pretty', '0 bytes'),
            'index_count': row.get('index_count', 0),
            'has_toast': row.get('has_toast', False)
        })

    return {
        'tables': tables,
        'count': len(tables),
        'database': db_service.config.get('database', 'unknown')
    }


def get_columns(db_service: DatabaseService, table_name: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """Get enhanced column information for a specific table.

    Args:
        db_service: Database service instance
        table_name: Name of the table
        schema: Optional schema name

    Returns:
        Dictionary with enhanced column details including:
        - Basic info: column_name, data_type, nullable, default
        - Key info: primary_key, unique
        - Foreign keys: references_table, references_column, on_update, on_delete
        - Comments: Column descriptions
        - Index participation: List of indexes including this column
        - Constraints: Table-level constraints

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
    
    # Build enhanced query with comments, foreign keys, and index participation
    if schema:
        query = """
            WITH table_oid AS (
                SELECT c.oid
                FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = %s AND c.relname = %s
            ),
            foreign_keys AS (
                SELECT
                    kcu.column_name,
                    ccu.table_name AS references_table,
                    ccu.column_name AS references_column,
                    rc.update_rule AS on_update,
                    rc.delete_rule AS on_delete
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.referential_constraints rc
                    ON kcu.constraint_name = rc.constraint_name
                    AND kcu.table_schema = rc.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                    AND rc.unique_constraint_schema = ccu.constraint_schema
                WHERE kcu.table_schema = %s AND kcu.table_name = %s
            ),
            index_columns AS (
                SELECT
                    a.attname AS column_name,
                    string_agg(i.indexname, ', ' ORDER BY i.indexname) AS in_indexes
                FROM pg_indexes i
                JOIN pg_class ic ON ic.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = ic.oid
                JOIN pg_attribute a ON a.attrelid = idx.indrelid
                WHERE i.schemaname = %s AND i.tablename = %s
                AND a.attnum = ANY(idx.indkey)
                GROUP BY a.attname
            )
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
                CASE WHEN uc.column_name IS NOT NULL THEN true ELSE false END as is_unique,
                col_description((SELECT oid FROM table_oid), c.ordinal_position) AS comment,
                fk.references_table,
                fk.references_column,
                fk.on_update,
                fk.on_delete,
                COALESCE(ic.in_indexes, '') AS in_indexes
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_schema = %s AND tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_schema = %s AND tc.table_name = %s
                AND tc.constraint_type = 'UNIQUE'
            ) uc ON c.column_name = uc.column_name
            LEFT JOIN foreign_keys fk ON c.column_name = fk.column_name
            LEFT JOIN index_columns ic ON c.column_name = ic.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        params = (schema, table_name, schema, table_name, schema, table_name,
                 schema, table_name, schema, table_name, schema, table_name)
    else:
        # Use public schema as default
        schema = 'public'
        query = """
            WITH table_oid AS (
                SELECT c.oid
                FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = 'public' AND c.relname = %s
            ),
            foreign_keys AS (
                SELECT
                    kcu.column_name,
                    ccu.table_name AS references_table,
                    ccu.column_name AS references_column,
                    rc.update_rule AS on_update,
                    rc.delete_rule AS on_delete
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.referential_constraints rc
                    ON kcu.constraint_name = rc.constraint_name
                    AND kcu.table_schema = rc.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                    AND rc.unique_constraint_schema = ccu.constraint_schema
                WHERE kcu.table_schema = 'public' AND kcu.table_name = %s
            ),
            index_columns AS (
                SELECT
                    a.attname AS column_name,
                    string_agg(i.indexname, ', ' ORDER BY i.indexname) AS in_indexes
                FROM pg_indexes i
                JOIN pg_class ic ON ic.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = ic.oid
                JOIN pg_attribute a ON a.attrelid = idx.indrelid
                WHERE i.schemaname = 'public' AND i.tablename = %s
                AND a.attnum = ANY(idx.indkey)
                GROUP BY a.attname
            )
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
                CASE WHEN uc.column_name IS NOT NULL THEN true ELSE false END as is_unique,
                col_description((SELECT oid FROM table_oid), c.ordinal_position) AS comment,
                fk.references_table,
                fk.references_column,
                fk.on_update,
                fk.on_delete,
                COALESCE(ic.in_indexes, '') AS in_indexes
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'UNIQUE'
            ) uc ON c.column_name = uc.column_name
            LEFT JOIN foreign_keys fk ON c.column_name = fk.column_name
            LEFT JOIN index_columns ic ON c.column_name = ic.column_name
            WHERE c.table_name = %s AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """
        params = (table_name, table_name, table_name, table_name, table_name, table_name)
    
    # Execute query with read-only safety
    results = db_service.execute_readonly_query(query, params)
    
    # Check if table exists
    if not results:
        raise InvalidTableError(table_name)
    
    # Format columns with enhanced metadata
    columns = []
    for row in results:
        column = {
            'column_name': row['column_name'],
            'data_type': row['data_type'],
            'nullable': row['is_nullable'] == 'YES',
            'default': row.get('column_default'),
            'primary_key': row.get('is_primary_key', False),
            'unique': row.get('is_unique', False),
            'comment': row.get('comment'),
            'max_length': row.get('character_maximum_length'),
            'precision': row.get('numeric_precision'),
            'scale': row.get('numeric_scale')
        }

        # Add foreign key info if present
        if row.get('references_table'):
            column['foreign_key'] = {
                'references_table': row['references_table'],
                'references_column': row['references_column'],
                'on_update': row.get('on_update', 'NO ACTION'),
                'on_delete': row.get('on_delete', 'NO ACTION')
            }

        # Add index participation
        if row.get('in_indexes'):
            column['in_indexes'] = [idx.strip() for idx in row['in_indexes'].split(',') if idx.strip()]
        else:
            column['in_indexes'] = []

        columns.append(column)

    # Get table constraints
    constraint_query = """
        SELECT
            tc.constraint_name,
            tc.constraint_type,
            string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns,
            check_clause AS definition
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
            AND tc.table_schema = cc.constraint_schema
        WHERE tc.table_schema = %s AND tc.table_name = %s
        GROUP BY tc.constraint_name, tc.constraint_type, cc.check_clause
        ORDER BY tc.constraint_type, tc.constraint_name
    """
    constraint_params = (schema if schema else 'public', table_name)
    constraint_results = db_service.execute_readonly_query(constraint_query, constraint_params)

    constraints = []
    for row in constraint_results:
        constraints.append({
            'constraint_name': row['constraint_name'],
            'constraint_type': row['constraint_type'],
            'columns': row.get('columns', '').split(', ') if row.get('columns') else [],
            'definition': row.get('definition')
        })
    
    return {
        'table_name': table_name,
        'schema': schema if schema else 'public',
        'columns': columns,
        'column_count': len(columns),
        'constraints': constraints
    }


def get_table_stats(db_service: DatabaseService,
                   table_name: Optional[str] = None,
                   table_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get enhanced statistics for one or more tables including TOAST data.

    Args:
        db_service: Database service instance
        table_name: Single table name (optional)
        table_names: List of table names (optional)

    Returns:
        Dictionary with enhanced table statistics including:
        - Basic stats: row_count, dead_rows
        - Size metrics: table_size_bytes, index_size_bytes, toast_size_bytes
        - Total size: total_relation_size_bytes (table + indexes + toast)
        - Maintenance: last_vacuum, last_analyze timestamps

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
    
    # Build enhanced query with TOAST size
    query = """
        SELECT
            pst.schemaname,
            pst.relname,
            pst.n_live_tup as row_count,
            pst.n_dead_tup as dead_rows,
            pg_relation_size(quote_ident(pst.schemaname)||'.'||quote_ident(pst.relname)) as table_size_bytes,
            pg_size_pretty(pg_relation_size(quote_ident(pst.schemaname)||'.'||quote_ident(pst.relname))) as table_size,
            pg_indexes_size(quote_ident(pst.schemaname)||'.'||quote_ident(pst.relname)) as index_size_bytes,
            pg_size_pretty(pg_indexes_size(quote_ident(pst.schemaname)||'.'||quote_ident(pst.relname))) as index_size,
            COALESCE(pg_relation_size(c.reltoastrelid), 0) as toast_size_bytes,
            pg_size_pretty(COALESCE(pg_relation_size(c.reltoastrelid), 0)) as toast_size,
            pg_total_relation_size(quote_ident(pst.schemaname)||'.'||quote_ident(pst.relname)) as total_relation_size_bytes,
            pg_size_pretty(pg_total_relation_size(quote_ident(pst.schemaname)||'.'||quote_ident(pst.relname))) as total_relation_size,
            pst.last_vacuum,
            pst.last_autovacuum,
            pst.last_analyze,
            pst.last_autoanalyze,
            (SELECT COUNT(*) FROM pg_indexes WHERE tablename = pst.relname AND schemaname = pst.schemaname) as index_count
        FROM pg_stat_user_tables pst
        LEFT JOIN pg_class c ON c.relname = pst.relname
            AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = pst.schemaname)
        WHERE pst.relname = ANY(%s)
        ORDER BY pst.relname
    """

    # Execute query with read-only safety
    results = db_service.execute_readonly_query(query, (tables_to_query,))
    
    # Check if tables exist
    if not results:
        if len(tables_to_query) == 1:
            raise InvalidTableError(tables_to_query[0])
        else:
            raise MCPError(f"None of the specified tables exist: {', '.join(tables_to_query)}", recoverable=False)
    
    # Format results with enhanced metrics
    statistics = []
    for row in results:
        stat = {
            'table_name': row['relname'],
            'schema': row.get('schemaname', 'public'),
            'row_count': row['row_count'],
            'dead_rows': row.get('dead_rows', 0),
            'table_size_bytes': row['table_size_bytes'],
            'table_size': row['table_size'],
            'index_size_bytes': row.get('index_size_bytes', 0),
            'index_size': row.get('index_size', '0 bytes'),
            'toast_size_bytes': row.get('toast_size_bytes', 0),
            'toast_size': row.get('toast_size', '0 bytes'),
            'total_relation_size_bytes': row['total_relation_size_bytes'],
            'total_relation_size': row['total_relation_size'],
            'index_count': row.get('index_count', 0),
            'last_vacuum': str(row['last_vacuum']) if row.get('last_vacuum') else None,
            'last_autovacuum': str(row['last_autovacuum']) if row.get('last_autovacuum') else None,
            'last_analyze': str(row['last_analyze']) if row.get('last_analyze') else None,
            'last_autoanalyze': str(row['last_autoanalyze']) if row.get('last_autoanalyze') else None
        }
        statistics.append(stat)

    # Return format depends on single vs multiple tables
    if len(tables_to_query) == 1:
        # For backward compatibility with single table
        stat = statistics[0]
        return {
            'table_name': stat['table_name'],
            'schema': stat['schema'],
            'row_count': stat['row_count'],
            'dead_rows': stat['dead_rows'],
            'table_size': stat['total_relation_size'],
            'table_size_bytes': stat['table_size_bytes'],
            'index_size_bytes': stat['index_size_bytes'],
            'index_size': stat['index_size'],
            'toast_size_bytes': stat['toast_size_bytes'],
            'toast_size': stat['toast_size'],
            'total_relation_size_bytes': stat['total_relation_size_bytes'],
            'total_relation_size': stat['total_relation_size'],
            'index_count': stat['index_count'],
            'last_vacuum': stat['last_vacuum'],
            'last_analyze': stat['last_analyze']
        }
    else:
        return {
            'statistics': statistics,
            'table_count': len(statistics)
        }