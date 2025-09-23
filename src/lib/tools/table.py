"""Table-level MCP tools for PostgreSQL operations.

This module contains tools that operate at the table level,
providing table listing, column information, and statistics.
"""

from typing import Dict, Any, Optional, List, Union
from lib.logging_config import get_logger
from models.error_types import MCPError, InvalidTableError
from services.database_service import DatabaseService

logger = get_logger(__name__)


def get_tables(db_service: DatabaseService, schema: Optional[str] = None) -> Dict[str, Any]:
    """List all tables in the database with enhanced metadata.

    Args:
        db_service: Database service instance
        schema: Optional schema name to filter tables (default: all schemas)

    Returns:
        Dictionary containing:
        - tables: List of table information dictionaries
        - count: Number of tables
        - schema: Schema name or 'all'
        - database: Database name
    """
    # Enhanced query with metadata
    query = """
        SELECT
            t.schemaname as schema_name,
            t.tablename as table_name,
            t.tableowner as table_owner,
            CASE
                WHEN t.schemaname LIKE 'pg_%%' THEN 'SYSTEM'
                WHEN t.tablename LIKE 'pg_%%' THEN 'SYSTEM'
                WHEN c.relkind = 'r' THEN 'BASE TABLE'
                WHEN c.relkind = 'p' THEN 'PARTITIONED TABLE'
                WHEN c.relkind = 'f' THEN 'FOREIGN TABLE'
                ELSE 'UNKNOWN'
            END as table_type,
            s.n_live_tup as row_count,
            pg_total_relation_size(c.oid) as size_bytes,
            pg_size_pretty(pg_total_relation_size(c.oid)) as size_pretty,
            (
                SELECT COUNT(*)
                FROM pg_index i
                WHERE i.indrelid = c.oid
            ) as index_count,
            CASE
                WHEN c.reltoastrelid > 0 THEN true
                ELSE false
            END as has_toast
        FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
            AND c.relnamespace = (
                SELECT oid FROM pg_namespace WHERE nspname = t.schemaname
            )
        LEFT JOIN pg_stat_user_tables s ON s.schemaname = t.schemaname
            AND s.relname = t.tablename
        WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
    """

    # Add schema filter if provided
    params = None
    if schema:
        query += " AND t.schemaname = %s"
        params = (schema,)

    query += " ORDER BY t.schemaname, t.tablename"

    try:
        # Debug output
        logger.debug(f"Executing query with params: {params}")
        results = db_service.execute_readonly_query(query, params)

        if results is None:
            raise MCPError("Failed to retrieve table list", recoverable=True)

        # Format results with enhanced metadata
        tables = []
        for row in results:
            table_info = {
                'schema_name': row.get('schema_name'),
                'table_name': row.get('table_name'),
                'table_owner': row.get('table_owner'),
                'table_type': row.get('table_type', 'BASE TABLE'),
                'row_count': row.get('row_count', 0),
                'size_bytes': row.get('size_bytes', 0),
                'size_pretty': row.get('size_pretty', '0 bytes'),
                'index_count': row.get('index_count', 0),
                'has_toast': row.get('has_toast', False)
            }
            tables.append(table_info)

        return {
            'tables': tables,
            'count': len(tables),
            'schema': schema if schema else 'all',
            'database': db_service.config.get('database', 'unknown')
        }

    except MCPError:
        raise
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise MCPError(f"Failed to list tables: {str(e)}", recoverable=True)


def get_columns(db_service: DatabaseService,
                table_name: str,
                schema: Optional[str] = None) -> Dict[str, Any]:
    """Get column information for a specific table with enhanced metadata.

    Args:
        db_service: Database service instance
        table_name: Name of the table to describe
        schema: Optional schema name (default: public)

    Returns:
        Dictionary containing:
        - table_name: Name of the table
        - schema: Schema name
        - columns: List of column details with foreign keys, comments, and constraints
        - column_count: Number of columns
        - constraints: Table constraints
        - primary_key: Primary key information
    """
    if not schema:
        schema = 'public'

    # Enhanced query with foreign keys, comments, and constraints
    query = """
        WITH column_info AS (
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.ordinal_position,
                col_description(pgc.oid, c.ordinal_position) as column_comment
            FROM information_schema.columns c
            JOIN pg_catalog.pg_class pgc ON pgc.relname = c.table_name
            JOIN pg_catalog.pg_namespace pgn ON pgn.oid = pgc.relnamespace
                AND pgn.nspname = c.table_schema
            WHERE c.table_schema = %s
            AND c.table_name = %s
        ),
        foreign_keys AS (
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column,
                rc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
                ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = %s
            AND tc.table_name = %s
        ),
        primary_key AS (
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = %s
            AND tc.table_name = %s
        ),
        check_constraints AS (
            SELECT
                ccu.column_name,
                con.conname as constraint_name,
                pg_get_constraintdef(con.oid) as constraint_definition
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = con.conname
                AND ccu.table_schema = ns.nspname
            WHERE con.contype = 'c'
            AND ns.nspname = %s
            AND rel.relname = %s
        ),
        indexes AS (
            SELECT
                a.attname as column_name,
                string_agg(i.indexname, ', ') as index_names
            FROM pg_indexes i
            JOIN pg_class c ON c.relname = i.indexname
            JOIN pg_index idx ON idx.indexrelid = c.oid
            JOIN pg_attribute a ON a.attrelid = idx.indrelid
                AND a.attnum = ANY(idx.indkey)
            WHERE i.schemaname = %s
            AND i.tablename = %s
            GROUP BY a.attname
        )
        SELECT
            ci.*,
            pk.column_name IS NOT NULL as is_primary_key,
            fk.foreign_table_schema,
            fk.foreign_table,
            fk.foreign_column,
            fk.constraint_name as fk_constraint_name,
            cc.constraint_name as check_constraint_name,
            cc.constraint_definition as check_constraint_def,
            idx.index_names
        FROM column_info ci
        LEFT JOIN primary_key pk ON ci.column_name = pk.column_name
        LEFT JOIN foreign_keys fk ON ci.column_name = fk.column_name
        LEFT JOIN check_constraints cc ON ci.column_name = cc.column_name
        LEFT JOIN indexes idx ON ci.column_name = idx.column_name
        ORDER BY ci.ordinal_position
    """

    params = (schema, table_name, schema, table_name, schema, table_name,
              schema, table_name, schema, table_name)

    try:
        results = db_service.execute_readonly_query(query, params)

        if not results:
            raise InvalidTableError(
                f"Table '{schema}.{table_name}' not found",
                table_name=table_name
            )

        columns = []
        primary_key_columns = []
        all_constraints = []

        for row in results:
            # Build column info with enhanced metadata
            column = {
                'column_name': row['column_name'],
                'data_type': row['data_type'],
                'is_nullable': row['is_nullable'] == 'YES',
                'column_default': row['column_default'],
                'ordinal_position': row['ordinal_position']
            }

            # Add size information if applicable
            if row['character_maximum_length']:
                column['max_length'] = row['character_maximum_length']
            if row['numeric_precision']:
                column['numeric_precision'] = row['numeric_precision']
                if row['numeric_scale']:
                    column['numeric_scale'] = row['numeric_scale']

            # Add primary key flag
            if row.get('is_primary_key'):
                column['is_primary_key'] = True
                primary_key_columns.append(row['column_name'])

            # Add foreign key information
            if row.get('foreign_table'):
                column['foreign_key'] = {
                    'references_schema': row['foreign_table_schema'],
                    'references_table': row['foreign_table'],
                    'references_column': row['foreign_column'],
                    'constraint_name': row['fk_constraint_name']
                }

            # Add column comment if exists
            if row.get('column_comment'):
                column['comment'] = row['column_comment']

            # Add check constraint if exists
            if row.get('check_constraint_name'):
                column['check_constraint'] = {
                    'name': row['check_constraint_name'],
                    'definition': row['check_constraint_def']
                }
                # Track unique constraints
                if row['check_constraint_name'] not in [c['name'] for c in all_constraints]:
                    all_constraints.append({
                        'type': 'CHECK',
                        'name': row['check_constraint_name'],
                        'definition': row['check_constraint_def']
                    })

            # Add index participation
            if row.get('index_names'):
                column['indexes'] = row['index_names'].split(', ')

            columns.append(column)

        # Get table-level constraints
        constraint_query = """
            SELECT
                tc.constraint_type,
                tc.constraint_name,
                pg_get_constraintdef(con.oid, true) as definition
            FROM information_schema.table_constraints tc
            JOIN pg_constraint con ON con.conname = tc.constraint_name
            JOIN pg_namespace ns ON ns.nspname = tc.table_schema
            WHERE tc.table_schema = %s
            AND tc.table_name = %s
            ORDER BY tc.constraint_type
        """

        constraint_results = db_service.execute_readonly_query(
            constraint_query,
            (schema, table_name)
        )

        for con in constraint_results:
            if con['constraint_name'] not in [c['name'] for c in all_constraints]:
                all_constraints.append({
                    'type': con['constraint_type'],
                    'name': con['constraint_name'],
                    'definition': con['definition']
                })

        response = {
            'table_name': table_name,
            'schema': schema,
            'columns': columns,
            'column_count': len(columns),
            'constraints': all_constraints,
            'constraint_count': len(all_constraints)
        }

        # Add primary key info if exists
        if primary_key_columns:
            response['primary_key'] = {
                'columns': primary_key_columns,
                'constraint_name': next(
                    (c['name'] for c in all_constraints
                     if c['type'] == 'PRIMARY KEY'),
                    None
                )
            }

        return response

    except InvalidTableError:
        raise
    except MCPError:
        raise
    except Exception as e:
        logger.error(f"Error describing table {schema}.{table_name}: {e}")
        raise MCPError(f"Failed to describe table: {str(e)}", recoverable=True)


def get_table_stats(db_service: DatabaseService,
                   table_name: Optional[str] = None,
                   table_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get statistics for one or more tables with enhanced metrics.

    Args:
        db_service: Database service instance
        table_name: Single table name (optional)
        table_names: List of table names (optional)

    Returns:
        Dictionary containing table statistics including:
        - row_count: Number of live rows
        - dead_rows: Number of dead rows
        - table_size: Human-readable size
        - TOAST size information
        - total_relation_size: Total size including indexes and TOAST
        - vacuum/analyze information
    """
    # Determine which tables to query
    tables_to_query = []

    if table_name:
        tables_to_query.append(table_name)
    if table_names:
        tables_to_query.extend(table_names)

    if not tables_to_query:
        raise MCPError("No table names provided", recoverable=False)

    # Remove duplicates while preserving order
    tables_to_query = list(dict.fromkeys(tables_to_query))

    # Build query for multiple tables with enhanced metrics
    placeholders = ','.join(['%s'] * len(tables_to_query))
    query = f"""
        SELECT
            n.nspname as schema_name,
            t.tablename as table_name,
            s.n_live_tup as row_count,
            s.n_dead_tup as dead_rows,
            pg_relation_size(c.oid) as table_size_bytes,
            pg_size_pretty(pg_relation_size(c.oid)) as table_size,
            pg_indexes_size(c.oid) as index_size_bytes,
            pg_size_pretty(pg_indexes_size(c.oid)) as index_size,
            CASE
                WHEN c.reltoastrelid > 0 THEN
                    pg_relation_size(c.reltoastrelid)
                ELSE 0
            END as toast_size_bytes,
            CASE
                WHEN c.reltoastrelid > 0 THEN
                    pg_size_pretty(pg_relation_size(c.reltoastrelid))
                ELSE '0 bytes'
            END as toast_size,
            pg_total_relation_size(c.oid) as total_relation_size_bytes,
            pg_size_pretty(pg_total_relation_size(c.oid)) as total_relation_size,
            (SELECT count(*) FROM pg_index WHERE indrelid = c.oid) as index_count,
            s.last_vacuum::text,
            s.last_autovacuum::text,
            s.vacuum_count,
            s.autovacuum_count,
            s.last_analyze::text,
            s.last_autoanalyze::text,
            s.analyze_count,
            s.autoanalyze_count,
            s.n_tup_ins as rows_inserted,
            s.n_tup_upd as rows_updated,
            s.n_tup_del as rows_deleted,
            s.n_tup_hot_upd as rows_hot_updated,
            s.seq_scan as sequential_scans,
            s.seq_tup_read as sequential_tuples_read,
            s.idx_scan as index_scans,
            s.idx_tup_fetch as index_tuples_fetched,
            CASE
                WHEN s.seq_scan + s.idx_scan > 0 THEN
                    round((100.0 * s.idx_scan / (s.seq_scan + s.idx_scan))::numeric, 2)
                ELSE 0
            END as index_scan_ratio
        FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.schemaname
        LEFT JOIN pg_stat_user_tables s ON s.schemaname = t.schemaname
            AND s.relname = t.tablename
        WHERE t.tablename IN ({placeholders})
        ORDER BY t.schemaname, t.tablename
    """

    try:
        results = db_service.execute_readonly_query(query, tuple(tables_to_query))

        if not results:
            if len(tables_to_query) == 1:
                raise InvalidTableError(
                    f"Table '{tables_to_query[0]}' not found",
                    table_name=tables_to_query[0]
                )
            else:
                raise MCPError(f"No tables found matching: {', '.join(tables_to_query)}",
                              recoverable=False)

        # Format results based on single or multiple tables
        if len(results) == 1:
            # Single table - return direct stats with enhanced metrics
            stats = results[0]
            return {
                'table_name': stats['table_name'],
                'schema': stats['schema_name'],
                'row_count': stats['row_count'] or 0,
                'dead_rows': stats['dead_rows'] or 0,
                'table_size': stats['table_size'],
                'table_size_bytes': stats['table_size_bytes'] or 0,
                'index_size': stats['index_size'],
                'index_size_bytes': stats['index_size_bytes'] or 0,
                'toast_size': stats['toast_size'],
                'toast_size_bytes': stats['toast_size_bytes'] or 0,
                'total_relation_size': stats['total_relation_size'],
                'total_relation_size_bytes': stats['total_relation_size_bytes'] or 0,
                'index_count': stats['index_count'] or 0,
                'last_vacuum': stats['last_vacuum'] if stats['last_vacuum'] else 'Never',
                'last_autovacuum': stats['last_autovacuum'] if stats['last_autovacuum'] else 'Never',
                'vacuum_count': stats['vacuum_count'] or 0,
                'autovacuum_count': stats['autovacuum_count'] or 0,
                'last_analyze': stats['last_analyze'] if stats['last_analyze'] else 'Never',
                'last_autoanalyze': stats['last_autoanalyze'] if stats['last_autoanalyze'] else 'Never',
                'analyze_count': stats['analyze_count'] or 0,
                'autoanalyze_count': stats['autoanalyze_count'] or 0,
                'activity': {
                    'rows_inserted': stats['rows_inserted'] or 0,
                    'rows_updated': stats['rows_updated'] or 0,
                    'rows_deleted': stats['rows_deleted'] or 0,
                    'rows_hot_updated': stats['rows_hot_updated'] or 0,
                    'sequential_scans': stats['sequential_scans'] or 0,
                    'index_scans': stats['index_scans'] or 0,
                    'index_scan_ratio': float(stats['index_scan_ratio'] or 0)
                }
            }
        else:
            # Multiple tables - return array with enhanced metrics
            formatted_stats = []
            for stats in results:
                formatted_stats.append({
                    'table_name': stats['table_name'],
                    'schema': stats['schema_name'],
                    'row_count': stats['row_count'] or 0,
                    'dead_rows': stats['dead_rows'] or 0,
                    'table_size': stats['table_size'],
                    'table_size_bytes': stats['table_size_bytes'] or 0,
                    'toast_size': stats['toast_size'],
                    'toast_size_bytes': stats['toast_size_bytes'] or 0,
                    'total_relation_size': stats['total_relation_size'],
                    'total_relation_size_bytes': stats['total_relation_size_bytes'] or 0,
                    'index_count': stats['index_count'] or 0,
                    'index_scan_ratio': float(stats['index_scan_ratio'] or 0),
                    'last_vacuum': stats['last_vacuum'] if stats['last_vacuum'] else 'Never',
                    'last_analyze': stats['last_analyze'] if stats['last_analyze'] else 'Never'
                })

            return {
                'table_count': len(formatted_stats),
                'statistics': formatted_stats
            }

    except InvalidTableError:
        raise
    except MCPError:
        raise
    except Exception as e:
        logger.error(f"Error getting table statistics: {e}")
        raise MCPError(f"Failed to get table statistics: {str(e)}", recoverable=True)