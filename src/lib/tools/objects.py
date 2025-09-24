"""Object-level database inspection tools for PostgreSQL MCP Server.
"""

from typing import Dict, List, Any, Optional
import json
from src.services.database_service import DatabaseService
from src.models.error_types import MCPError
from src.utils.logger import get_logger, log_database_query

logger = get_logger(__name__)


def describe_object(db_service: DatabaseService,
                   object_name: str,
                   object_type: Optional[str] = None,
                   schema: str = 'public') -> Dict[str, Any]:
    """Universal object inspector for PostgreSQL objects.

    Args:
        db_service: Database service instance
        object_name: Name of the object to describe
        object_type: Type of object (table, view, function, index, etc.)
                    If not provided, will auto-detect
        schema: Schema name (default: public)

    Returns:
        Dictionary with comprehensive object metadata
    """
    logger.info(f"Describing object: {schema}.{object_name} (type: {object_type or 'auto-detect'})")

    # Auto-detect object type if not provided
    if not object_type:
        detect_query = """
            SELECT
                CASE
                    WHEN t.tablename IS NOT NULL THEN 'table'
                    WHEN v.viewname IS NOT NULL THEN 'view'
                    WHEN p.proname IS NOT NULL THEN 'function'
                    WHEN i.indexname IS NOT NULL THEN 'index'
                    WHEN s.sequence_name IS NOT NULL THEN 'sequence'
                    ELSE 'unknown'
                END as object_type
            FROM (SELECT %s::text as obj_name, %s::text as obj_schema) params
            LEFT JOIN pg_tables t ON t.tablename = params.obj_name AND t.schemaname = params.obj_schema
            LEFT JOIN pg_views v ON v.viewname = params.obj_name AND v.schemaname = params.obj_schema
            LEFT JOIN pg_proc p ON p.proname = params.obj_name
                AND p.pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = params.obj_schema)
            LEFT JOIN pg_indexes i ON i.indexname = params.obj_name AND i.schemaname = params.obj_schema
            LEFT JOIN information_schema.sequences s ON s.sequence_name = params.obj_name
                AND s.sequence_schema = params.obj_schema
        """

        results = db_service.execute_readonly_query(detect_query, (object_name, schema))
        if results and results[0]['object_type'] != 'unknown':
            object_type = results[0]['object_type']
            logger.debug(f"Auto-detected object type: {object_type}")
        else:
            raise MCPError(f"Object '{schema}.{object_name}' not found")

    # Query based on object type
    if object_type == 'table':
        query = """
            SELECT
                'table' as object_type,
                t.tablename as object_name,
                t.schemaname as schema,
                t.tableowner as owner,
                obj_description(c.oid, 'pg_class') as description,
                pg_size_pretty(pg_total_relation_size(c.oid)) as size,
                s.n_live_tup as row_count,
                (SELECT count(*) FROM pg_index WHERE indrelid = c.oid) as index_count,
                c.relhassubclass as has_partitions,
                c.relpersistence = 't' as is_temporary,
                s.last_vacuum::text,
                s.last_analyze::text
            FROM pg_tables t
            JOIN pg_class c ON c.relname = t.tablename
            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.schemaname
            LEFT JOIN pg_stat_user_tables s ON s.schemaname = t.schemaname AND s.relname = t.tablename
            WHERE t.tablename = %s AND t.schemaname = %s
        """
    elif object_type == 'view':
        query = """
            SELECT
                CASE WHEN m.matviewname IS NOT NULL THEN 'materialized_view' ELSE 'view' END as object_type,
                COALESCE(v.viewname, m.matviewname) as object_name,
                COALESCE(v.schemaname, m.schemaname) as schema,
                COALESCE(v.viewowner, m.matviewowner) as owner,
                obj_description(c.oid, 'pg_class') as description,
                COALESCE(v.definition, m.definition) as definition,
                pg_size_pretty(pg_relation_size(c.oid)) as size,
                m.ispopulated as is_populated,
                s.last_refresh::text
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_views v ON v.viewname = c.relname AND v.schemaname = n.nspname
            LEFT JOIN pg_matviews m ON m.matviewname = c.relname AND m.schemaname = n.nspname
            LEFT JOIN pg_stat_user_tables s ON s.schemaname = n.nspname AND s.relname = c.relname
            WHERE c.relname = %s AND n.nspname = %s
            AND (v.viewname IS NOT NULL OR m.matviewname IS NOT NULL)
        """
    elif object_type == 'function':
        query = """
            SELECT
                'function' as object_type,
                p.proname as object_name,
                n.nspname as schema,
                r.rolname as owner,
                obj_description(p.oid, 'pg_proc') as description,
                l.lanname as language,
                pg_get_function_arguments(p.oid) as arguments,
                t.typname as return_type,
                p.prosrc as source_code,
                p.provolatile as volatility,
                p.proisstrict as is_strict,
                p.prosecdef as security_definer
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_roles r ON r.oid = p.proowner
            JOIN pg_language l ON l.oid = p.prolang
            JOIN pg_type t ON t.oid = p.prorettype
            WHERE p.proname = %s AND n.nspname = %s
        """
    elif object_type == 'index':
        query = """
            SELECT
                'index' as object_type,
                i.indexname as object_name,
                i.schemaname as schema,
                t.tableowner as owner,
                i.tablename as table_name,
                obj_description(c.oid, 'pg_class') as description,
                pg_size_pretty(pg_relation_size(c.oid)) as size,
                i.indexdef as definition,
                idx.indisunique as is_unique,
                idx.indisprimary as is_primary,
                s.idx_scan as index_scans,
                s.idx_tup_read as tuples_read,
                s.idx_tup_fetch as tuples_fetched
            FROM pg_indexes i
            JOIN pg_class c ON c.relname = i.indexname
            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = i.schemaname
            JOIN pg_index idx ON idx.indexrelid = c.oid
            LEFT JOIN pg_tables t ON t.tablename = i.tablename AND t.schemaname = i.schemaname
            LEFT JOIN pg_stat_user_indexes s ON s.schemaname = i.schemaname AND s.indexrelname = i.indexname
            WHERE i.indexname = %s AND i.schemaname = %s
        """
    else:
        raise MCPError(f"Unsupported object type: {object_type}")

    results = db_service.execute_readonly_query(query, (object_name, schema))

    if not results:
        raise MCPError(f"Object '{schema}.{object_name}' not found")

    result = dict(results[0])

    # Clean up None values
    return {k: v for k, v in result.items() if v is not None}


def explain_query(db_service: DatabaseService,
                 query: str,
                 analyze: bool = False,
                 format: str = 'json') -> Dict[str, Any]:
    """Query plan analyzer with performance insights.

    Args:
        db_service: Database service instance
        query: SQL query to explain
        analyze: If True, actually execute the query for timing info
        format: Output format (json, text, xml, yaml)

    Returns:
        Dictionary with query plan and performance warnings
    """
    logger.info(f"Explaining query (analyze: {analyze})")

    # Build EXPLAIN command
    explain_options = []
    if analyze:
        explain_options.append('ANALYZE true')
    explain_options.append(f'FORMAT {format}')

    explain_cmd = f"EXPLAIN ({', '.join(explain_options)}) {query}"

    try:
        results = db_service.execute_readonly_query(explain_cmd)

        if format == 'json' and results:
            plan_data = results[0].get('QUERY PLAN', [])
            if isinstance(plan_data, list) and plan_data:
                plan = plan_data[0]
            else:
                plan = plan_data

            # Convert plan keys to snake_case for consistency
            plan_data = plan.get('Plan', {})
            if plan_data:
                # Convert keys with spaces to snake_case
                normalized_plan = {}
                for key, value in plan_data.items():
                    snake_key = key.lower().replace(' ', '_')
                    normalized_plan[snake_key] = value
            else:
                normalized_plan = {}

            response = {
                'query': query[:200] + '...' if len(query) > 200 else query,
                'plan': normalized_plan,
                'warnings': []
            }

            # Extract timing info if ANALYZE was used
            if analyze:
                response['execution_time'] = plan.get('Execution Time', 0)
                response['planning_time'] = plan.get('Planning Time', 0)
                response['total_time'] = response['execution_time'] + response['planning_time']

            # Add performance warnings
            if 'Plan' in plan:
                response['total_cost'] = plan['Plan'].get('Total Cost', 0)

                # Check for performance issues
                if 'Seq Scan' in str(plan):
                    response['warnings'].append('Sequential scan detected - consider adding indexes')

                if analyze and response.get('execution_time', 0) > 1000:
                    response['warnings'].append(f"Slow query: {response['execution_time']:.2f}ms execution time")

                if plan['Plan'].get('Total Cost', 0) > 10000:
                    response['warnings'].append('High cost query - consider optimization')

            return response
        else:
            return {
                'query': query[:200] + '...' if len(query) > 200 else query,
                'plan': results,
                'warnings': []
            }

    except Exception as e:
        logger.error(f"Error explaining query: {e}")
        raise MCPError(f"Failed to explain query: {str(e)}")


def list_views(db_service: DatabaseService,
              schema: str = 'public',
              include_definition: bool = False) -> Dict[str, Any]:
    """List all views in a schema.

    Args:
        db_service: Database service instance
        schema: Schema name (default: public)
        include_definition: Include view SQL definition

    Returns:
        Dictionary with list of views and metadata
    """
    logger.info(f"Listing views in schema: {schema}")

    query = """
        SELECT
            v.viewname as view_name,
            v.schemaname as schema_name,
            v.viewowner as owner,
            FALSE as is_materialized,
            obj_description(c.oid, 'pg_class') as description
            %s
        FROM pg_views v
        JOIN pg_class c ON c.relname = v.viewname
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = v.schemaname
        WHERE v.schemaname = %%s

        UNION ALL

        SELECT
            m.matviewname as view_name,
            m.schemaname as schema_name,
            m.matviewowner as owner,
            TRUE as is_materialized,
            obj_description(c.oid, 'pg_class') as description
            %s
        FROM pg_matviews m
        JOIN pg_class c ON c.relname = m.matviewname
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = m.schemaname
        WHERE m.schemaname = %%s

        ORDER BY schema_name, view_name
    """

    if include_definition:
        definition_cols = ", v.definition", ", m.definition"
    else:
        definition_cols = "", ""

    formatted_query = query % definition_cols
    results = db_service.execute_readonly_query(formatted_query, (schema, schema))

    views = []
    for row in results:
        view_info = {
            'view_name': row['view_name'],
            'schema_name': row['schema_name'],
            'owner': row['owner'],
            'is_materialized': row['is_materialized'],
            'description': row.get('description')
        }

        if include_definition and 'definition' in row:
            view_info['definition'] = row['definition']

        views.append(view_info)

    return {
        'schema': schema,
        'views': views,
        'count': len(views)
    }


def list_functions(db_service: DatabaseService,
                  schema: str = 'public',
                  include_system: bool = False) -> Dict[str, Any]:
    """List all functions in a schema.

    Args:
        db_service: Database service instance
        schema: Schema name (default: public)
        include_system: Include system functions

    Returns:
        Dictionary with list of functions and metadata
    """
    logger.info(f"Listing functions in schema: {schema}")

    query = """
        SELECT
            p.proname as function_name,
            n.nspname as schema_name,
            r.rolname as owner,
            l.lanname as language,
            pg_get_function_arguments(p.oid) as arguments,
            t.typname as return_type,
            obj_description(p.oid, 'pg_proc') as description,
            CASE p.provolatile
                WHEN 'i' THEN 'immutable'
                WHEN 's' THEN 'stable'
                WHEN 'v' THEN 'volatile'
            END as volatility,
            p.proisagg as is_aggregate,
            p.proiswindow as is_window,
            p.proretset as returns_set
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_roles r ON r.oid = p.proowner
        JOIN pg_language l ON l.oid = p.prolang
        JOIN pg_type t ON t.oid = p.prorettype
        WHERE n.nspname = %s
        %s
        ORDER BY n.nspname, p.proname
    """

    # Filter system functions if requested
    system_filter = ""
    if not include_system:
        system_filter = """
            AND p.proname NOT LIKE 'pg_%'
            AND p.proname NOT LIKE 'gs_%'
            AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        """

    # Build query with proper formatting
    if include_system:
        formatted_query = query.replace('%s\n', '')
    else:
        formatted_query = query.replace('%s', system_filter)
    results = db_service.execute_readonly_query(formatted_query, (schema,))

    functions = []
    for row in results:
        func_info = {
            'function_name': row['function_name'],
            'schema_name': row['schema_name'],
            'owner': row['owner'],
            'language': row['language'],
            'arguments': row.get('arguments') or '',
            'return_type': row['return_type'],
            'volatility': row.get('volatility'),
            'is_aggregate': row.get('is_aggregate', False),
            'is_window': row.get('is_window', False),
            'returns_set': row.get('returns_set', False)
        }

        if row.get('description'):
            func_info['description'] = row['description']

        functions.append(func_info)

    return {
        'schema': schema,
        'functions': functions,
        'count': len(functions)
    }


def list_indexes(db_service: DatabaseService,
                table_name: Optional[str] = None,
                schema: str = 'public',
                include_unused: bool = True) -> Dict[str, Any]:
    """List indexes with usage statistics.

    Args:
        db_service: Database service instance
        table_name: Optional specific table name
        schema: Schema name (default: public)
        include_unused: Include unused indexes

    Returns:
        Dictionary with list of indexes and usage stats
    """
    logger.info(f"Listing indexes (table: {table_name}, schema: {schema})")

    query = """
        SELECT
            i.indexname as index_name,
            i.tablename as table_name,
            i.schemaname as schema_name,
            t.tableowner as owner,
            idx.indisprimary as is_primary,
            idx.indisunique as is_unique,
            idx.indisclustered as is_clustered,
            idx.indisvalid as is_valid,
            pg_size_pretty(pg_relation_size(c.oid)) as index_size,
            COALESCE(s.idx_scan, 0) as index_scans,
            COALESCE(s.idx_tup_read, 0) as tuples_read,
            COALESCE(s.idx_tup_fetch, 0) as tuples_fetched,
            i.indexdef as index_definition,
            obj_description(c.oid, 'pg_class') as description
        FROM pg_indexes i
        JOIN pg_class c ON c.relname = i.indexname
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = i.schemaname
        JOIN pg_index idx ON idx.indexrelid = c.oid
        LEFT JOIN pg_tables t ON t.tablename = i.tablename AND t.schemaname = i.schemaname
        LEFT JOIN pg_stat_user_indexes s ON s.schemaname = i.schemaname
            AND s.indexrelname = i.indexname
        WHERE i.schemaname = %s
        %s
        %s
        ORDER BY i.schemaname, i.tablename, i.indexname
    """

    # Add table filter if specified
    table_filter = ""
    params = [schema]
    if table_name:
        table_filter = "AND i.tablename = %s"
        params.append(table_name)

    # Add unused filter if requested
    unused_filter = ""
    if not include_unused:
        unused_filter = "AND COALESCE(s.idx_scan, 0) > 0"

    # Build query with proper formatting
    formatted_query = query.replace('%s', table_filter, 1).replace('%s', unused_filter, 1)
    results = db_service.execute_readonly_query(formatted_query, tuple(params))

    indexes = []
    warnings = []

    for row in results:
        index_info = {
            'index_name': row['index_name'],
            'table_name': row['table_name'],
            'schema_name': row['schema_name'],
            'owner': row.get('owner'),
            'is_primary': row.get('is_primary', False),
            'is_unique': row.get('is_unique', False),
            'is_clustered': row.get('is_clustered', False),
            'is_valid': row.get('is_valid', True),
            'index_size': row['index_size'],
            'index_scans': row['index_scans'],
            'tuples_read': row.get('tuples_read', 0),
            'tuples_fetched': row.get('tuples_fetched', 0),
            'index_definition': row['index_definition']
        }

        if row.get('description'):
            index_info['description'] = row['description']

        # Check for unused indexes
        if row['index_scans'] == 0 and not row['is_primary']:
            index_info['is_unused'] = True
            warnings.append(f"Index '{row['index_name']}' on '{row['table_name']}' has never been used")

        indexes.append(index_info)

    response = {
        'schema': schema,
        'indexes': indexes,
        'count': len(indexes)
    }

    if table_name:
        response['table_name'] = table_name

    if warnings:
        response['warnings'] = warnings

    return response


def get_table_constraints(db_service: DatabaseService,
                         table_name: str,
                         schema: str = 'public') -> Dict[str, Any]:
    """Get all constraints for a specific table.

    Args:
        db_service: Database service instance
        table_name: Table name
        schema: Schema name (default: public)

    Returns:
        Dictionary with all table constraints
    """
    logger.info(f"Getting constraints for table: {schema}.{table_name}")

    query = """
        WITH constraints AS (
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                tc.table_name,
                kcu.column_name,
                pg_get_constraintdef(con.oid, true) as definition,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column,
                rc.update_rule,
                rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN pg_constraint con ON con.conname = tc.constraint_name
                AND con.connamespace = (SELECT oid FROM pg_namespace WHERE nspname = tc.table_schema)
            LEFT JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
                AND tc.constraint_type = 'FOREIGN KEY'
            LEFT JOIN information_schema.referential_constraints rc
                ON rc.constraint_name = tc.constraint_name
                AND rc.constraint_schema = tc.table_schema
            WHERE tc.table_schema = %s
            AND tc.table_name = %s
        )
        SELECT DISTINCT
            constraint_name,
            constraint_type,
            table_name,
            string_agg(DISTINCT column_name, ', ') OVER (PARTITION BY constraint_name) as columns,
            definition,
            foreign_table,
            foreign_column,
            update_rule,
            delete_rule
        FROM constraints
        ORDER BY
            CASE constraint_type
                WHEN 'PRIMARY KEY' THEN 1
                WHEN 'UNIQUE' THEN 2
                WHEN 'FOREIGN KEY' THEN 3
                WHEN 'CHECK' THEN 4
                ELSE 5
            END,
            constraint_name
    """

    results = db_service.execute_readonly_query(query, (schema, table_name))

    constraints = []
    seen_constraints = set()

    for row in results:
        # Avoid duplicates from the window function
        if row['constraint_name'] in seen_constraints:
            continue
        seen_constraints.add(row['constraint_name'])

        constraint_info = {
            'constraint_name': row['constraint_name'],
            'constraint_type': row['constraint_type'],
            'table_name': row['table_name'],
            'columns': row.get('columns'),
            'definition': row['definition']
        }

        # Add foreign key specific info
        if row['constraint_type'] == 'FOREIGN KEY':
            constraint_info['foreign_table'] = row.get('foreign_table')
            constraint_info['foreign_column'] = row.get('foreign_column')
            constraint_info['update_rule'] = row.get('update_rule')
            constraint_info['delete_rule'] = row.get('delete_rule')

        constraints.append(constraint_info)

    return {
        'table_name': table_name,
        'schema': schema,
        'constraints': constraints,
        'constraint_count': len(constraints)
    }


def get_dependencies(db_service: DatabaseService,
                    object_name: str,
                    schema: str = 'public',
                    direction: str = 'both') -> Dict[str, Any]:
    """Analyze object dependencies.

    Args:
        db_service: Database service instance
        object_name: Object name to analyze
        schema: Schema name (default: public)
        direction: 'depends_on', 'dependents', or 'both'

    Returns:
        Dictionary with dependency information
    """
    logger.info(f"Getting dependencies for: {schema}.{object_name} (direction: {direction})")

    # Query for what this object depends on
    depends_on_query = """
        WITH RECURSIVE dep_tree AS (
            SELECT DISTINCT
                c1.relname as dependent_object,
                n1.nspname as dependent_schema,
                CASE c1.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'v' THEN 'view'
                    WHEN 'm' THEN 'materialized view'
                    WHEN 'i' THEN 'index'
                    WHEN 'S' THEN 'sequence'
                    WHEN 'f' THEN 'foreign table'
                    ELSE 'other'
                END as dependent_type,
                c2.relname as depends_on_object,
                n2.nspname as depends_on_schema,
                CASE c2.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'v' THEN 'view'
                    WHEN 'm' THEN 'materialized view'
                    WHEN 'i' THEN 'index'
                    WHEN 'S' THEN 'sequence'
                    WHEN 'f' THEN 'foreign table'
                    ELSE 'other'
                END as depends_on_type,
                d.deptype as dependency_type
            FROM pg_depend d
            JOIN pg_class c1 ON c1.oid = d.objid
            JOIN pg_namespace n1 ON n1.oid = c1.relnamespace
            JOIN pg_class c2 ON c2.oid = d.refobjid
            JOIN pg_namespace n2 ON n2.oid = c2.relnamespace
            WHERE c1.relname = %s
            AND n1.nspname = %s
            AND d.deptype IN ('n', 'a', 'i')
            AND n2.nspname NOT IN ('pg_catalog', 'information_schema')
        )
        SELECT * FROM dep_tree
    """

    # Query for what depends on this object
    dependents_query = """
        WITH RECURSIVE dep_tree AS (
            SELECT DISTINCT
                c1.relname as dependent_object,
                n1.nspname as dependent_schema,
                CASE c1.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'v' THEN 'view'
                    WHEN 'm' THEN 'materialized view'
                    WHEN 'i' THEN 'index'
                    WHEN 'S' THEN 'sequence'
                    WHEN 'f' THEN 'foreign table'
                    ELSE 'other'
                END as dependent_type,
                c2.relname as depends_on_object,
                n2.nspname as depends_on_schema,
                CASE c2.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'v' THEN 'view'
                    WHEN 'm' THEN 'materialized view'
                    WHEN 'i' THEN 'index'
                    WHEN 'S' THEN 'sequence'
                    WHEN 'f' THEN 'foreign table'
                    ELSE 'other'
                END as depends_on_type,
                d.deptype as dependency_type
            FROM pg_depend d
            JOIN pg_class c1 ON c1.oid = d.objid
            JOIN pg_namespace n1 ON n1.oid = c1.relnamespace
            JOIN pg_class c2 ON c2.oid = d.refobjid
            JOIN pg_namespace n2 ON n2.oid = c2.relnamespace
            WHERE c2.relname = %s
            AND n2.nspname = %s
            AND d.deptype IN ('n', 'a', 'i')
            AND n1.nspname NOT IN ('pg_catalog', 'information_schema')
        )
        SELECT * FROM dep_tree
    """

    response = {
        'object_name': object_name,
        'schema': schema
    }

    if direction in ['depends_on', 'both']:
        depends_on_results = db_service.execute_readonly_query(depends_on_query, (object_name, schema))

        dependencies = []
        for row in depends_on_results:
            dep = {
                'depends_on_object': row['depends_on_object'],
                'depends_on_schema': row.get('depends_on_schema'),
                'depends_on_type': row['depends_on_type'],
                'dependency_type': _format_dependency_type(row['dependency_type'])
            }
            dependencies.append(dep)

        if direction == 'both':
            response['depends_on'] = dependencies
            response['depends_on_count'] = len(dependencies)
        else:
            response['dependencies'] = dependencies

    if direction in ['dependents', 'both']:
        dependents_results = db_service.execute_readonly_query(dependents_query, (object_name, schema))

        dependents = []
        for row in dependents_results:
            dep = {
                'dependent_object': row['dependent_object'],
                'dependent_schema': row.get('dependent_schema'),
                'dependent_type': row['dependent_type'],
                'dependency_type': _format_dependency_type(row['dependency_type'])
            }
            dependents.append(dep)

        if direction == 'both':
            response['dependents'] = dependents
            response['dependents_count'] = len(dependents)
        else:
            response['dependencies'] = dependents

    return response


def _format_dependency_type(deptype: str) -> str:
    """Format dependency type code to human-readable string."""
    dependency_types = {
        'n': 'normal',
        'a': 'auto',
        'i': 'internal',
        'e': 'extension',
        'p': 'pin'
    }
    return dependency_types.get(deptype, deptype)