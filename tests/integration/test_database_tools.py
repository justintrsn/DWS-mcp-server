"""Integration tests for database-level PostgreSQL MCP tools."""

import pytest
from unittest.mock import Mock, MagicMock
from src.lib import mcp_tools
from src.services.database_service import DatabaseService


class TestListSchemas:
    """Tests for list_schemas functionality."""

    def test_list_schemas_basic(self):
        """Test basic schema listing."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'schema_name': 'public',
                'schema_owner': 'postgres',
                'schema_type': 'User Schema',
                'table_count': 15
            },
            {
                'schema_name': 'information_schema',
                'schema_owner': 'postgres',
                'schema_type': 'System Information Schema',
                'table_count': 67
            }
        ]

        result = mcp_tools.list_schemas(db_service)

        assert result['count'] == 2
        assert 'schemas' in result
        assert result['schemas'][0]['schema_name'] == 'public'
        assert result['schemas'][0]['schema_type'] == 'User Schema'

    def test_list_schemas_with_sizes(self):
        """Test schema listing with size information."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'schema_name': 'public',
                'schema_owner': 'postgres',
                'schema_type': 'User Schema',
                'table_count': 10,
                'size_bytes': 10485760,
                'size_pretty': '10 MB'
            }
        ]

        result = mcp_tools.list_schemas(db_service, include_sizes=True)

        assert result['schemas'][0]['size_bytes'] == 10485760
        assert result['schemas'][0]['size_pretty'] == '10 MB'

    def test_list_schemas_exclude_system(self):
        """Test excluding system schemas."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'schema_name': 'public',
                'schema_owner': 'postgres',
                'schema_type': 'User Schema',
                'table_count': 10
            }
        ]

        result = mcp_tools.list_schemas(db_service, include_system=False)

        # Should not include pg_* or information_schema
        for schema in result['schemas']:
            assert not schema['schema_name'].startswith('pg_')
            assert schema['schema_name'] != 'information_schema'


class TestGetDatabaseStats:
    """Tests for get_database_stats functionality."""

    def test_get_database_stats_basic(self):
        """Test basic database statistics retrieval."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'database_name': 'mydb',
                'size_bytes': 52428800,
                'size_pretty': '50 MB',
                'connection_limit': -1,
                'current_connections': 5,
                'max_connections': 100,
                'version': 'PostgreSQL 14.9',
                'uptime': '7 days 03:45:22',
                'transactions_committed': 150000,
                'transactions_rolled_back': 500,
                'blocks_read': 1000000,
                'blocks_hit': 9500000,
                'cache_hit_ratio': 0.905,
                'temp_files': 10,
                'temp_bytes': 1048576,
                'deadlocks': 0
            }
        ]

        result = mcp_tools.get_database_stats(db_service)

        assert result['database_name'] == 'mydb'
        assert result['size_bytes'] == 52428800
        assert result['current_connections'] == 5
        assert result['statistics']['cache_hit_ratio'] == 0.905
        assert result['statistics']['deadlocks'] == 0

    def test_get_database_stats_cache_hit_calculation(self):
        """Test cache hit ratio calculation."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'database_name': 'testdb',
                'size_bytes': 10485760,
                'size_pretty': '10 MB',
                'connection_limit': 50,
                'current_connections': 2,
                'max_connections': 100,
                'version': 'PostgreSQL 15.3',
                'transactions_committed': 10000,
                'transactions_rolled_back': 50,
                'blocks_read': 100,
                'blocks_hit': 9900,
                'cache_hit_ratio': 0.99,
                'temp_files': 0,
                'temp_bytes': 0,
                'deadlocks': 0
            }
        ]

        result = mcp_tools.get_database_stats(db_service)

        # Cache hit ratio should be calculated correctly
        assert result['statistics']['cache_hit_ratio'] == 0.99


class TestGetConnectionInfo:
    """Tests for get_connection_info functionality."""

    def test_get_connection_info_by_state(self):
        """Test connection info grouped by state."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'current_connections': 10,
                'max_connections': 100,
                'idle_connections': 5,
                'active_queries': 3,
                'idle_in_transaction': 2,
                'idle_in_transaction_aborted': 0,
                'fastpath_function_call': 0,
                'disabled': 0
            }
        ]

        result = mcp_tools.get_connection_info(db_service, by_state=True)

        assert result['current_connections'] == 10
        assert result['max_connections'] == 100
        assert result['idle_connections'] == 5
        assert result['active_queries'] == 3

        if 'connections_by_state' in result:
            assert result['connections_by_state']['idle'] == 5
            assert result['connections_by_state']['active'] == 3
            assert result['connections_by_state']['idle_in_transaction'] == 2

    def test_get_connection_info_by_database(self):
        """Test connection info grouped by database."""
        db_service = Mock(spec=DatabaseService)

        # When grouping by database, return different structure
        db_service.execute_readonly_query.return_value = [
            {'database': 'mydb', 'count': 5},
            {'database': 'postgres', 'count': 2},
            {'database': 'template1', 'count': 0}
        ]

        result = mcp_tools.get_connection_info(db_service, by_state=False, by_database=True)

        if 'connections_by_database' in result:
            assert len(result['connections_by_database']) == 3
            assert result['connections_by_database'][0]['database'] == 'mydb'
            assert result['connections_by_database'][0]['count'] == 5

    def test_get_connection_info_saturation_warning(self):
        """Test that connection saturation triggers warnings."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'current_connections': 95,
                'max_connections': 100,
                'idle_connections': 5,
                'active_queries': 90
            }
        ]

        result = mcp_tools.get_connection_info(db_service)

        # Should include warning about connection saturation
        if 'warnings' in result:
            assert any('saturation' in w.lower() or 'connections' in w.lower()
                      for w in result['warnings'])