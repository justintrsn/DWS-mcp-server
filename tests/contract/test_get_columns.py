"""Contract tests for get_columns MCP tool.

These tests verify the get_columns tool contract:
- Returns column details for a specific table
- Includes data types, nullable, defaults
- Handles invalid table names
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add src to path for imports (will fail until implementation exists)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

class TestGetColumnsContract:
    """Contract tests for get_columns tool."""

    def test_get_columns_returns_column_details(self):
        """Test that get_columns returns detailed column information."""
        from lib.mcp_tools import get_columns

        # Mock database service with multiple query responses
        mock_db = Mock()

        # First call returns column data, second call returns empty constraints
        mock_db.execute_readonly_query.side_effect = [
            # Column data
            [
                {
                    'column_name': 'id',
                    'data_type': 'integer',
                    'is_nullable': 'NO',
                    'column_default': "nextval('users_id_seq'::regclass)",
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': 32,
                    'numeric_scale': 0,
                    'column_comment': 'Primary key',
                    'is_primary_key': True,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': None,
                    'index_names': None,
                    'check_constraint_name': None,
                    'check_constraint_def': None
                },
                {
                    'column_name': 'username',
                    'data_type': 'character varying',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 2,
                    'character_maximum_length': 50,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'column_comment': None,
                    'is_primary_key': None,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': None,
                    'index_names': None,
                    'check_constraint_name': None,
                    'check_constraint_def': None
                },
                {
                    'column_name': 'created_at',
                    'data_type': 'timestamp without time zone',
                    'is_nullable': 'YES',
                    'column_default': 'CURRENT_TIMESTAMP',
                    'ordinal_position': 3,
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'column_comment': None,
                    'is_primary_key': None,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': None,
                    'index_names': None,
                    'check_constraint_name': None,
                    'check_constraint_def': None
                }
            ],
            # Constraint data (empty for simplicity)
            []
        ]

        result = get_columns(db_service=mock_db, table_name='users')

        assert isinstance(result, dict)
        assert 'columns' in result
        assert isinstance(result['columns'], list)
        assert len(result['columns']) == 3

        # Check column names are present
        col_names = [col['column_name'] for col in result['columns']]
        assert 'id' in col_names
        assert 'username' in col_names
        assert 'created_at' in col_names

    def test_get_columns_with_schema(self):
        """Test get_columns with schema specification."""
        from lib.mcp_tools import get_columns

        mock_db = Mock()
        mock_db.execute_readonly_query.side_effect = [
            [
                {
                    'column_name': 'id',
                    'data_type': 'integer',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': 32,
                    'numeric_scale': 0,
                    'column_comment': None,
                    'is_primary_key': True,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': None,
                    'index_names': None,
                    'check_constraint_name': None,
                    'check_constraint_def': None
                }
            ],
            []
        ]

        result = get_columns(db_service=mock_db, table_name='users', schema='public')

        assert 'columns' in result
        assert len(result['columns']) == 1
        assert result['table_name'] == 'users'
        assert result.get('schema') == 'public'

    def test_get_columns_invalid_table(self):
        """Test get_columns with non-existent table."""
        from lib.mcp_tools import get_columns
        from src.models.error_types import InvalidTableError

        mock_db = Mock()
        # First query returns empty results (no columns found)
        mock_db.execute_readonly_query.return_value = []

        # Should raise InvalidTableError
        with pytest.raises(InvalidTableError):
            get_columns(db_service=mock_db, table_name='non_existent_table')

    def test_get_columns_includes_constraints(self):
        """Test that get_columns includes constraint information."""
        from lib.mcp_tools import get_columns

        mock_db = Mock()
        mock_db.execute_readonly_query.side_effect = [
            [
                {
                    'column_name': 'id',
                    'data_type': 'integer',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': 32,
                    'numeric_scale': 0,
                    'column_comment': None,
                    'is_primary_key': True,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': None,
                    'index_names': None,
                    'check_constraint_name': None,
                    'check_constraint_def': None
                },
                {
                    'column_name': 'email',
                    'data_type': 'character varying',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'ordinal_position': 2,
                    'character_maximum_length': 100,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'column_comment': None,
                    'is_primary_key': None,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': True,
                    'index_names': 'users_email_idx',
                    'check_constraint_name': None,
                    'check_constraint_def': None
                }
            ],
            []
        ]

        result = get_columns(db_service=mock_db, table_name='users')

        # Check for constraint info in columns
        for col in result['columns']:
            if col['column_name'] == 'id':
                assert col.get('is_primary_key') == True
            if col['column_name'] == 'email':
                assert col.get('is_unique') or col.get('indexes')

    def test_get_columns_response_format(self):
        """Test that get_columns returns proper MCP tool response format."""
        from lib.mcp_tools import get_columns

        mock_db = Mock()
        mock_db.execute_readonly_query.side_effect = [
            [
                {
                    'column_name': 'test_col',
                    'data_type': 'text',
                    'is_nullable': 'YES',
                    'column_default': None,
                    'ordinal_position': 1,
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'column_comment': None,
                    'is_primary_key': None,
                    'foreign_table': None,
                    'foreign_column': None,
                    'constraint_name': None,
                    'constraint_type': None,
                    'is_unique': None,
                    'index_names': None,
                    'check_constraint_name': None,
                    'check_constraint_def': None
                }
            ],
            []
        ]

        result = get_columns(db_service=mock_db, table_name='test_table')

        # MCP tool response format
        assert isinstance(result, dict)
        assert 'columns' in result
        assert 'table_name' in result
        assert result['table_name'] == 'test_table'
        assert 'column_count' in result
        assert result['column_count'] == 1