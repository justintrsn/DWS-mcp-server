"""Contract tests for get_tables MCP tool.

These tests verify the get_tables tool contract:
- Returns a list of table names
- Handles schema filtering
- Returns proper error for connection issues
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports (will fail until implementation exists)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

class TestGetTablesContract:
    """Contract tests for get_tables tool."""

    def test_get_tables_returns_list(self):
        """Test that get_tables returns a list of table names."""
        from lib.mcp_tools import get_tables

        # Mock database service
        mock_db = Mock()
        mock_db.config = {'database': 'testdb'}
        mock_db.execute_readonly_query.return_value = [
            {'table_name': 'users', 'table_schema': 'public', 'table_owner': 'owner',
             'table_type': 'BASE TABLE', 'row_count': 100, 'total_size': 8192,
             'size_pretty': '8 KB', 'index_count': 1, 'toast_size': 0},
            {'table_name': 'products', 'table_schema': 'public', 'table_owner': 'owner',
             'table_type': 'BASE TABLE', 'row_count': 200, 'total_size': 16384,
             'size_pretty': '16 KB', 'index_count': 2, 'toast_size': 0},
            {'table_name': 'orders', 'table_schema': 'public', 'table_owner': 'owner',
             'table_type': 'BASE TABLE', 'row_count': 300, 'total_size': 32768,
             'size_pretty': '32 KB', 'index_count': 3, 'toast_size': 0}
        ]

        result = get_tables(db_service=mock_db)

        assert isinstance(result, dict)
        assert 'tables' in result
        assert isinstance(result['tables'], list)
        assert len(result['tables']) == 3

        # Check table names are present (can be strings or dicts)
        table_names = []
        for table in result['tables']:
            if isinstance(table, str):
                table_names.append(table)
            else:
                table_names.append(table['table_name'])

        assert 'users' in table_names
        assert 'products' in table_names
        assert 'orders' in table_names

    def test_get_tables_with_schema_filter(self):
        """Test that get_tables can filter by schema."""
        from lib.mcp_tools import get_tables

        mock_db = Mock()
        mock_db.config = {'database': 'testdb'}
        mock_db.execute_readonly_query.return_value = [
            {'table_name': 'users', 'table_schema': 'public', 'table_owner': 'owner',
             'table_type': 'BASE TABLE', 'row_count': 100, 'total_size': 8192,
             'size_pretty': '8 KB', 'index_count': 1, 'toast_size': 0},
            {'table_name': 'products', 'table_schema': 'public', 'table_owner': 'owner',
             'table_type': 'BASE TABLE', 'row_count': 200, 'total_size': 16384,
             'size_pretty': '16 KB', 'index_count': 2, 'toast_size': 0}
        ]

        result = get_tables(db_service=mock_db, schema='public')

        assert isinstance(result, dict)
        assert 'tables' in result
        assert 'schema' in result
        assert result['schema'] == 'public'

    def test_get_tables_empty_database(self):
        """Test get_tables returns empty list for empty database."""
        from lib.mcp_tools import get_tables

        mock_db = Mock()
        mock_db.config = {'database': 'testdb'}
        mock_db.execute_readonly_query.return_value = []

        result = get_tables(db_service=mock_db)

        assert isinstance(result, dict)
        assert 'tables' in result
        assert result['tables'] == []
        assert result['count'] == 0

    def test_get_tables_connection_error(self):
        """Test get_tables handles connection errors properly."""
        from lib.mcp_tools import get_tables
        from models.error_types import MCPError

        mock_db = Mock()
        mock_db.config = {'database': 'testdb'}
        mock_db.execute_readonly_query.side_effect = Exception("Connection failed")

        # The function should handle the error and return an error dict or raise MCPError
        with pytest.raises(Exception):
            result = get_tables(db_service=mock_db)

    def test_get_tables_response_format(self):
        """Test get_tables response has correct format."""
        from lib.mcp_tools import get_tables

        mock_db = Mock()
        mock_db.config = {'database': 'testdb'}
        mock_db.execute_readonly_query.return_value = [
            {'table_name': 'test_table', 'table_schema': 'public', 'table_owner': 'owner',
             'table_type': 'BASE TABLE', 'row_count': 100, 'total_size': 8192,
             'size_pretty': '8 KB', 'index_count': 1, 'toast_size': 0}
        ]

        result = get_tables(db_service=mock_db)

        # Check response structure
        assert 'tables' in result
        assert 'count' in result
        assert 'database' in result
        assert result['count'] == 1
        assert result['database'] == 'testdb'