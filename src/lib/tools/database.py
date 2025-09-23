"""Database-level MCP tools for PostgreSQL operations.

This module contains tools that operate at the database level,
providing statistics, connection information, and overall database health.
"""

from typing import Dict, Any
from lib.logging_config import get_logger
from models.error_types import MCPError
from services.database_service import DatabaseService

logger = get_logger(__name__)


def get_database_stats(db_service: DatabaseService) -> Dict[str, Any]:
    """Get comprehensive database statistics and metrics.

    Args:
        db_service: Database service instance

    Returns:
        Dictionary containing database statistics including:
        - Database name, size, connections
        - Transaction statistics
        - Cache hit ratio
        - Temporary files usage
    """
    # Get main database stats (DWS-compatible)
    query = """
        SELECT
            current_database() as database_name,
            pg_database_size(current_database()) as size_bytes,
            pg_size_pretty(pg_database_size(current_database())) as size_pretty,
            (SELECT setting FROM pg_settings WHERE name = 'max_connections')::int as max_connections,
            (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as current_connections,
            (SELECT setting FROM pg_settings WHERE name = 'server_version') as version,
            pg_postmaster_start_time() as server_start_time,
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - pg_postmaster_start_time()))::int as uptime_seconds,
            s.xact_commit as transactions_committed,
            s.xact_rollback as transactions_rolled_back,
            s.blks_read as blocks_read,
            s.blks_hit as blocks_hit,
            CASE
                WHEN s.blks_read + s.blks_hit > 0
                THEN round((s.blks_hit::numeric / (s.blks_read + s.blks_hit)) * 100, 2)
                ELSE 0
            END as cache_hit_ratio,
            s.temp_files,
            s.temp_bytes,
            s.deadlocks,
            (SELECT datconnlimit FROM pg_database WHERE datname = current_database()) as connection_limit
        FROM pg_stat_database s
        WHERE s.datname = current_database()
    """

    results = db_service.execute_readonly_query(query)

    if not results:
        raise MCPError("Failed to retrieve database statistics", recoverable=True)

    stats = results[0]

    # Format uptime
    uptime_seconds = stats.get('uptime_seconds', 0)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    uptime_str = f"{days} days {hours:02d}:{minutes:02d}"

    return {
        'database_name': stats['database_name'],
        'size_bytes': stats['size_bytes'],
        'size_pretty': stats['size_pretty'],
        'connection_limit': stats.get('connection_limit', -1),
        'current_connections': stats['current_connections'],
        'max_connections': stats['max_connections'],
        'version': stats.get('version', 'Unknown'),
        'server_start_time': str(stats.get('server_start_time', '')),
        'uptime': uptime_str,
        'statistics': {
            'transactions_committed': stats.get('transactions_committed', 0),
            'transactions_rolled_back': stats.get('transactions_rolled_back', 0),
            'blocks_read': stats.get('blocks_read', 0),
            'blocks_hit': stats.get('blocks_hit', 0),
            'cache_hit_ratio': float(stats.get('cache_hit_ratio', 0)),
            'temp_files': stats.get('temp_files', 0),
            'temp_bytes': stats.get('temp_bytes', 0),
            'deadlocks': stats.get('deadlocks', 0)
        }
    }


def get_connection_info(db_service: DatabaseService,
                        by_state: bool = True,
                        by_database: bool = False) -> Dict[str, Any]:
    """Get current database connection information and statistics.

    Args:
        db_service: Database service instance
        by_state: Group connections by state
        by_database: Group connections by database

    Returns:
        Dictionary containing connection information
    """
    # Base query for connection info (DWS-compatible using CASE instead of FILTER)
    base_query = """
        SELECT
            (SELECT setting FROM pg_settings WHERE name = 'max_connections')::int as max_connections,
            COUNT(*) as current_connections,
            SUM(CASE WHEN state = 'idle' THEN 1 ELSE 0 END) as idle_connections,
            SUM(CASE WHEN state = 'active' THEN 1 ELSE 0 END) as active_queries,
            SUM(CASE WHEN state = 'idle in transaction' THEN 1 ELSE 0 END) as idle_in_transaction,
            SUM(CASE WHEN state = 'idle in transaction (aborted)' THEN 1 ELSE 0 END) as idle_in_transaction_aborted,
            SUM(CASE WHEN state = 'fastpath function call' THEN 1 ELSE 0 END) as fastpath_function_call,
            SUM(CASE WHEN state IS NULL THEN 1 ELSE 0 END) as disabled
        FROM pg_stat_activity
        WHERE pid != pg_backend_pid()
    """

    # Execute base query
    results = db_service.execute_readonly_query(base_query)

    if not results:
        raise MCPError("Failed to retrieve connection information", recoverable=True)

    conn_info = results[0]

    response = {
        'current_connections': conn_info['current_connections'],
        'max_connections': conn_info['max_connections'],
        'idle_connections': conn_info['idle_connections'],
        'active_queries': conn_info['active_queries']
    }

    # Add connection usage percentage
    if conn_info['max_connections'] > 0:
        response['connection_usage_percent'] = round(
            (conn_info['current_connections'] / conn_info['max_connections']) * 100, 2
        )

    # Group by state if requested
    if by_state:
        response['connections_by_state'] = {
            'active': conn_info['active_queries'],
            'idle': conn_info['idle_connections'],
            'idle_in_transaction': conn_info['idle_in_transaction'],
            'idle_in_transaction_aborted': conn_info['idle_in_transaction_aborted'],
            'fastpath_function_call': conn_info['fastpath_function_call'],
            'disabled': conn_info['disabled']
        }

    # Group by database if requested
    if by_database:
        db_query = """
            SELECT datname as database, COUNT(*) as count
            FROM pg_stat_activity
            WHERE pid != pg_backend_pid()
            GROUP BY datname
            ORDER BY count DESC
        """
        db_results = db_service.execute_readonly_query(db_query)

        response['connections_by_database'] = [
            {'database': row['database'], 'count': row['count']}
            for row in db_results
        ]

    # Add warnings for connection saturation
    usage_percent = response.get('connection_usage_percent', 0)
    warnings = []

    if usage_percent >= 90:
        warnings.append(f"CRITICAL: Connection usage at {usage_percent}% - consider increasing max_connections")
    elif usage_percent >= 75:
        warnings.append(f"WARNING: Connection usage at {usage_percent}% - monitor for potential saturation")

    if conn_info.get('idle_in_transaction', 0) > 10:
        warnings.append(f"High number of idle-in-transaction connections ({conn_info['idle_in_transaction']})")

    if warnings:
        response['warnings'] = warnings

    return response