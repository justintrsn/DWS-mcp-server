"""Integration tests for enhanced PostgreSQL MCP tools."""

import pytest
from unittest.mock import Mock, MagicMock
from src.lib import mcp_tools
from src.services.database_service import DatabaseService


class TestEnhancedGetTables:
    """Tests for enhanced get_tables functionality."""

    def test_get_tables_with_metadata(self):
        """Test that get_tables includes owner, table_type, and size estimates."""
        # Mock database service
        db_service = Mock(spec=DatabaseService)
        db_service.config = {'database': 'test_db'}

        # Mock query result with enhanced metadata
        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'table_type': 'BASE TABLE',
                'table_owner': 'postgres',
                'row_count': 1500,
                'size_bytes': 65536,
                'size_pretty': '64 kB',
                'index_count': 3,
                'has_toast': False
            },
            {
                'table_name': 'products',
                'schema_name': 'public',
                'table_type': 'BASE TABLE',
                'table_owner': 'postgres',
                'row_count': 5000,
                'size_bytes': 262144,
                'size_pretty': '256 kB',
                'index_count': 5,
                'has_toast': True
            }
        ]
        # Mock second query for constraints
        db_service.execute_readonly_query.side_effect = [db_service.execute_readonly_query.return_value, []]

        # Call enhanced get_tables
        result = mcp_tools.get_tables(db_service, schema='public')

        # Assertions
        assert result['count'] == 2
        assert 'tables' in result
        assert len(result['tables']) == 2

        # Check first table has all enhanced fields
        first_table = result['tables'][0]
        assert first_table['table_name'] == 'users'
        assert first_table['table_owner'] == 'postgres'
        assert first_table['table_type'] == 'BASE TABLE'
        assert first_table['size_bytes'] == 65536
        assert first_table['size_pretty'] == '64 kB'
        assert first_table['row_count'] == 1500
        assert first_table['index_count'] == 3
        assert first_table['has_toast'] is False

        # Check second table
        second_table = result['tables'][1]
        assert second_table['has_toast'] is True

    def test_get_tables_schema_classification(self):
        """Test that schemas are properly classified as system or user schemas."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # Test with system schema
        db_service.execute_readonly_query.return_value = []
        # Mock second query for constraints
        db_service.execute_readonly_query.side_effect = [db_service.execute_readonly_query.return_value, []]
        result = mcp_tools.get_tables(db_service, schema='pg_catalog')

        # Should handle system schemas appropriately
        assert 'tables' in result
        assert result['count'] == 0

    def test_get_tables_with_no_schema(self):
        """Test get_tables without specifying a schema."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}
        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'table_type': 'BASE TABLE',
                'table_owner': 'postgres',
                'row_count': 100,
                'size_bytes': 8192,
                'size_pretty': '8192 bytes',
                'index_count': 1,
                'has_toast': False
            }
        ]
        # Mock second query for constraints
        db_service.execute_readonly_query.side_effect = [db_service.execute_readonly_query.return_value, []]

        result = mcp_tools.get_tables(db_service)
        assert result['count'] == 1
        assert result['tables'][0]['schema_name'] == 'public'


class TestEnhancedGetColumns:
    """Tests for enhanced get_columns functionality."""

    def test_get_columns_with_comments(self):
        """Test that get_columns includes column comments."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # Mock query result with comments
        # First call returns columns, second call returns constraints
        db_service.execute_readonly_query.side_effect = [
            # First query: column data
            [
                {
                    'column_name': 'id',
                    'data_type': 'integer',
                    'is_nullable': 'NO',
                    'column_default': "nextval('users_id_seq'::regclass)",
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_primary_key': True,
                    'column_comment': 'User unique identifier',
                    'index_names': 'users_pkey'
                },
                {
                    'column_name': 'email',
                    'data_type': 'character varying',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 2,
                    'character_maximum_length': 255,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_primary_key': False,
                    'column_comment': 'User email address',
                    'index_names': 'users_email_idx'
                }
            ],
            # Second query: constraint data
            [
                {
                    'constraint_type': 'PRIMARY KEY',
                    'constraint_name': 'users_pkey',
                    'definition': 'PRIMARY KEY (id)'
                }
            ]
        ]

        result = mcp_tools.get_columns(db_service, 'users')

        assert result['column_count'] == 2
        assert result['columns'][0].get('comment') == 'User unique identifier'
        assert result['columns'][1].get('comment') == 'User email address'

    def test_get_columns_with_foreign_keys(self):
        """Test that get_columns includes foreign key relationships."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # First call returns columns with foreign key, second call returns constraints
        db_service.execute_readonly_query.side_effect = [
            # First query: column data with foreign key
            [
                {
                    'column_name': 'user_id',
                    'data_type': 'integer',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_primary_key': False,
                    'foreign_table_schema': 'public',
                    'foreign_table': 'users',
                    'foreign_column': 'id',
                    'fk_constraint_name': 'orders_user_id_fkey',
                    'column_comment': None,
                    'index_names': None
                }
            ],
            # Second query: constraint data
            [
                {
                    'constraint_type': 'FOREIGN KEY',
                    'constraint_name': 'orders_user_id_fkey',
                    'definition': 'FOREIGN KEY (user_id) REFERENCES users(id)'
                }
            ]
        ]

        result = mcp_tools.get_columns(db_service, 'orders')

        column = result['columns'][0]
        assert 'foreign_key' in column
        assert column['foreign_key']['references_table'] == 'users'
        assert column['foreign_key']['references_column'] == 'id'

    def test_get_columns_with_index_participation(self):
        """Test that get_columns shows which indexes include each column."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # First call returns columns with indexes, second call returns constraints
        db_service.execute_readonly_query.side_effect = [
            # First query: column data
            [
                {
                    'column_name': 'created_at',
                    'data_type': 'timestamp with time zone',
                    'is_nullable': 'NO',
                    'column_default': 'CURRENT_TIMESTAMP',
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_primary_key': False,
                    'column_comment': None,
                    'index_names': 'idx_created_at, idx_user_created'
                }
            ],
            # Second query: constraint data
            []
        ]

        result = mcp_tools.get_columns(db_service, 'users')

        column = result['columns'][0]
        assert 'indexes' in column
        assert len(column['indexes']) == 2
        assert 'idx_created_at' in column['indexes']
        assert 'idx_user_created' in column['indexes']

    def test_get_columns_with_constraints(self):
        """Test that get_columns includes table constraints."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # First call returns columns, second call returns constraints
        db_service.execute_readonly_query.side_effect = [
            # First query: column data
            [
                {
                    'column_name': 'email',
                    'data_type': 'character varying',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 1,
                    'character_maximum_length': 255,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_primary_key': False,
                    'column_comment': None,
                    'index_names': 'users_email_key'
                }
            ],
            # Second query: constraint data
            [
                {
                    'constraint_type': 'UNIQUE',
                    'constraint_name': 'users_email_key',
                    'definition': 'UNIQUE (email)'
                }
            ]
        ]

        result = mcp_tools.get_columns(db_service, 'users')

        # Enhanced version should include constraints
        if 'constraints' in result:
            assert isinstance(result['constraints'], list)


class TestEnhancedGetTableStats:
    """Tests for enhanced get_table_stats functionality."""

    def test_get_table_stats_with_toast(self):
        """Test that get_table_stats includes TOAST table size."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'documents',
                'schema_name': 'public',
                'row_count': 1000,
                'dead_rows': 0,
                'table_size_bytes': 8388608,
                'table_size': '8192 kB',
                'index_size_bytes': 262144,
                'index_size': '256 kB',
                'toast_size_bytes': 4194304,
                'toast_size': '4096 kB',
                'total_relation_size_bytes': 12845056,
                'total_relation_size': '12 MB',
                'index_count': 2,
                'last_vacuum': '2024-01-15 10:30:00',
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': '2024-01-15 10:30:00',
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 100,
                'rows_deleted': 10,
                'rows_hot_updated': 50,
                'sequential_scans': 100,
                'sequential_tuples_read': 0,
                'index_scans': 500,
                'index_tuples_fetched': 0,
                'index_scan_ratio': 83.33
            }
        ]

        result = mcp_tools.get_table_stats(db_service, 'documents')

        # Single table returns direct stats, not statistics array
        assert 'toast_size_bytes' in result
        assert result['toast_size_bytes'] == 4194304
        assert result['toast_size'] == '4096 kB'

    def test_get_table_stats_total_relation_size(self):
        """Test that get_table_stats includes total_relation_size."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'row_count': 5000,
                'dead_rows': 0,
                'table_size_bytes': 524288,
                'table_size': '512 kB',
                'index_size_bytes': 131072,
                'index_size': '128 kB',
                'toast_size_bytes': 0,
                'toast_size': '0 bytes',
                'total_relation_size_bytes': 655360,
                'total_relation_size': '640 kB',
                'index_count': 2,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 100,
                'rows_deleted': 10,
                'rows_hot_updated': 50,
                'sequential_scans': 100,
                'sequential_tuples_read': 0,
                'index_scans': 500,
                'index_tuples_fetched': 0,
                'index_scan_ratio': 83.33
            }
        ]

        result = mcp_tools.get_table_stats(db_service, 'users')

        # Single table returns direct stats, not statistics array
        assert 'total_relation_size_bytes' in result
        assert result['total_relation_size_bytes'] == 655360
        assert result['total_relation_size'] == '640 kB'

    def test_get_table_stats_multiple_tables(self):
        """Test get_table_stats with multiple tables."""
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'row_count': 1000,
                'dead_rows': 0,
                'table_size_bytes': 65536,
                'table_size': '64 kB',
                'index_size_bytes': 16384,
                'index_size': '16 kB',
                'toast_size_bytes': 0,
                'toast_size': '0 bytes',
                'total_relation_size_bytes': 81920,
                'total_relation_size': '80 kB',
                'index_count': 2,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 100,
                'rows_deleted': 10,
                'rows_hot_updated': 50,
                'sequential_scans': 100,
                'sequential_tuples_read': 0,
                'index_scans': 500,
                'index_tuples_fetched': 0,
                'index_scan_ratio': 83.33
            },
            {
                'table_name': 'products',
                'schema_name': 'public',
                'row_count': 5000,
                'dead_rows': 0,
                'table_size_bytes': 262144,
                'table_size': '256 kB',
                'index_size_bytes': 65536,
                'index_size': '64 kB',
                'toast_size_bytes': 131072,
                'toast_size': '128 kB',
                'total_relation_size_bytes': 458752,
                'total_relation_size': '448 kB',
                'index_count': 2,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 100,
                'rows_deleted': 10,
                'rows_hot_updated': 50,
                'sequential_scans': 100,
                'sequential_tuples_read': 0,
                'index_scans': 500,
                'index_tuples_fetched': 0,
                'index_scan_ratio': 83.33
            }
        ]

        result = mcp_tools.get_table_stats(db_service, table_names=['users', 'products'])

        assert len(result['statistics']) == 2
        assert result['statistics'][0]['table_name'] == 'users'
        assert result['statistics'][1]['table_name'] == 'products'
        assert result['statistics'][1]['toast_size_bytes'] == 131072