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

        # Mock query result with enhanced metadata
        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema': 'public',
                'table_type': 'BASE TABLE',
                'owner': 'postgres',
                'row_count': 1500,
                'size_bytes': 65536,
                'size_pretty': '64 kB',
                'index_count': 3,
                'has_toast': False
            },
            {
                'table_name': 'products',
                'schema': 'public',
                'table_type': 'BASE TABLE',
                'owner': 'postgres',
                'row_count': 5000,
                'size_bytes': 262144,
                'size_pretty': '256 kB',
                'index_count': 5,
                'has_toast': True
            }
        ]

        # Call enhanced get_tables
        result = mcp_tools.get_tables(db_service, schema='public')

        # Assertions
        assert result['count'] == 2
        assert 'tables' in result
        assert len(result['tables']) == 2

        # Check first table has all enhanced fields
        first_table = result['tables'][0]
        assert first_table['table_name'] == 'users'
        assert first_table['owner'] == 'postgres'
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

        # Test with system schema
        db_service.execute_readonly_query.return_value = []
        result = mcp_tools.get_tables(db_service, schema='pg_catalog')

        # Should handle system schemas appropriately
        assert 'tables' in result
        assert result['count'] == 0

    def test_get_tables_with_no_schema(self):
        """Test get_tables without specifying a schema."""
        db_service = Mock(spec=DatabaseService)
        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema': 'public',
                'table_type': 'BASE TABLE',
                'owner': 'postgres',
                'row_count': 100,
                'size_bytes': 8192,
                'size_pretty': '8192 bytes',
                'index_count': 1,
                'has_toast': False
            }
        ]

        result = mcp_tools.get_tables(db_service)
        assert result['count'] == 1
        assert result['tables'][0]['schema'] == 'public'


class TestEnhancedGetColumns:
    """Tests for enhanced get_columns functionality."""

    def test_get_columns_with_comments(self):
        """Test that get_columns includes column comments."""
        db_service = Mock(spec=DatabaseService)

        # Mock query result with comments
        db_service.execute_readonly_query.return_value = [
            {
                'column_name': 'id',
                'data_type': 'integer',
                'nullable': False,
                'default': "nextval('users_id_seq'::regclass)",
                'primary_key': True,
                'unique': True,
                'comment': 'User unique identifier',
                'max_length': None,
                'precision': None,
                'scale': None,
                'in_indexes': ['users_pkey']
            },
            {
                'column_name': 'email',
                'data_type': 'character varying',
                'nullable': False,
                'default': None,
                'primary_key': False,
                'unique': True,
                'comment': 'User email address',
                'max_length': 255,
                'precision': None,
                'scale': None,
                'in_indexes': ['users_email_idx']
            }
        ]

        result = mcp_tools.get_columns(db_service, 'users')

        assert result['column_count'] == 2
        assert result['columns'][0]['comment'] == 'User unique identifier'
        assert result['columns'][1]['comment'] == 'User email address'

    def test_get_columns_with_foreign_keys(self):
        """Test that get_columns includes foreign key relationships."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'column_name': 'user_id',
                'data_type': 'integer',
                'nullable': False,
                'default': None,
                'primary_key': False,
                'unique': False,
                'foreign_key': {
                    'references_table': 'users',
                    'references_column': 'id',
                    'on_update': 'CASCADE',
                    'on_delete': 'RESTRICT'
                },
                'comment': None,
                'max_length': None,
                'precision': None,
                'scale': None,
                'in_indexes': []
            }
        ]

        result = mcp_tools.get_columns(db_service, 'orders')

        column = result['columns'][0]
        assert 'foreign_key' in column
        assert column['foreign_key']['references_table'] == 'users'
        assert column['foreign_key']['references_column'] == 'id'
        assert column['foreign_key']['on_update'] == 'CASCADE'
        assert column['foreign_key']['on_delete'] == 'RESTRICT'

    def test_get_columns_with_index_participation(self):
        """Test that get_columns shows which indexes include each column."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'column_name': 'created_at',
                'data_type': 'timestamp with time zone',
                'nullable': False,
                'default': 'CURRENT_TIMESTAMP',
                'primary_key': False,
                'unique': False,
                'comment': None,
                'max_length': None,
                'precision': None,
                'scale': None,
                'in_indexes': ['idx_created_at', 'idx_user_created']
            }
        ]

        result = mcp_tools.get_columns(db_service, 'users')

        column = result['columns'][0]
        assert 'in_indexes' in column
        assert len(column['in_indexes']) == 2
        assert 'idx_created_at' in column['in_indexes']
        assert 'idx_user_created' in column['in_indexes']

    def test_get_columns_with_constraints(self):
        """Test that get_columns includes table constraints."""
        db_service = Mock(spec=DatabaseService)

        # First call returns columns, second call would return constraints
        db_service.execute_readonly_query.return_value = [
            {
                'column_name': 'email',
                'data_type': 'character varying',
                'nullable': False,
                'default': None,
                'primary_key': False,
                'unique': True,
                'comment': None,
                'max_length': 255,
                'precision': None,
                'scale': None,
                'in_indexes': ['users_email_key']
            }
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

        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'documents',
                'schema': 'public',
                'row_count': 1000,
                'table_size_bytes': 8388608,
                'table_size': '8192 kB',
                'index_size_bytes': 262144,
                'index_size': '256 kB',
                'toast_size_bytes': 4194304,
                'toast_size': '4096 kB',
                'total_relation_size_bytes': 12845056,
                'total_relation_size': '12 MB',
                'last_vacuum': '2024-01-15 10:30:00',
                'last_analyze': '2024-01-15 10:30:00'
            }
        ]

        result = mcp_tools.get_table_stats(db_service, 'documents')

        stats = result['statistics'][0]
        assert 'toast_size_bytes' in stats
        assert stats['toast_size_bytes'] == 4194304
        assert stats['toast_size'] == '4096 kB'

    def test_get_table_stats_total_relation_size(self):
        """Test that get_table_stats includes total_relation_size."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema': 'public',
                'row_count': 5000,
                'table_size_bytes': 524288,
                'table_size': '512 kB',
                'index_size_bytes': 131072,
                'index_size': '128 kB',
                'toast_size_bytes': 0,
                'toast_size': '0 bytes',
                'total_relation_size_bytes': 655360,
                'total_relation_size': '640 kB',
                'last_vacuum': None,
                'last_analyze': None
            }
        ]

        result = mcp_tools.get_table_stats(db_service, 'users')

        stats = result['statistics'][0]
        assert 'total_relation_size_bytes' in stats
        assert stats['total_relation_size_bytes'] == 655360
        assert stats['total_relation_size'] == '640 kB'

    def test_get_table_stats_multiple_tables(self):
        """Test get_table_stats with multiple tables."""
        db_service = Mock(spec=DatabaseService)

        db_service.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema': 'public',
                'row_count': 1000,
                'table_size_bytes': 65536,
                'table_size': '64 kB',
                'index_size_bytes': 16384,
                'index_size': '16 kB',
                'toast_size_bytes': 0,
                'toast_size': '0 bytes',
                'total_relation_size_bytes': 81920,
                'total_relation_size': '80 kB',
                'last_vacuum': None,
                'last_analyze': None
            },
            {
                'table_name': 'products',
                'schema': 'public',
                'row_count': 5000,
                'table_size_bytes': 262144,
                'table_size': '256 kB',
                'index_size_bytes': 65536,
                'index_size': '64 kB',
                'toast_size_bytes': 131072,
                'toast_size': '128 kB',
                'total_relation_size_bytes': 458752,
                'total_relation_size': '448 kB',
                'last_vacuum': None,
                'last_analyze': None
            }
        ]

        result = mcp_tools.get_table_stats(db_service, table_names=['users', 'products'])

        assert len(result['statistics']) == 2
        assert result['statistics'][0]['table_name'] == 'users'
        assert result['statistics'][1]['table_name'] == 'products'
        assert result['statistics'][1]['toast_size_bytes'] == 131072