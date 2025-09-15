"""Contract tests for get_columns MCP tool.

These tests verify the get_columns tool contract:
- Returns column details for a specific table
- Includes data types, nullable, defaults
- Handles invalid table names
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports (will fail until implementation exists)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

class TestGetColumnsContract:
    """Contract tests for get_columns tool."""
    
    def test_get_columns_returns_column_details(self):
        """Test that get_columns returns detailed column information."""
        # This will fail until we implement the tool
        from lib.mcp_tools import get_columns
        
        # Mock database service
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'column_name': 'id',
                'data_type': 'integer',
                'is_nullable': 'NO',
                'column_default': "nextval('users_id_seq'::regclass)"
            },
            {
                'column_name': 'username',
                'data_type': 'character varying',
                'is_nullable': 'NO',
                'column_default': None
            },
            {
                'column_name': 'created_at',
                'data_type': 'timestamp without time zone',
                'is_nullable': 'YES',
                'column_default': 'CURRENT_TIMESTAMP'
            }
        ]
        
        result = get_columns(db_service=mock_db, table_name='users')
        
        assert isinstance(result, dict)
        assert 'columns' in result
        assert isinstance(result['columns'], list)
        assert len(result['columns']) == 3
        
        # Check first column
        id_col = result['columns'][0]
        assert id_col['column_name'] == 'id'
        assert id_col['data_type'] == 'integer'
        assert id_col['nullable'] is False
        assert 'default' in id_col
    
    def test_get_columns_with_schema(self):
        """Test get_columns with schema specification."""
        from lib.mcp_tools import get_columns
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'column_name': 'id',
                'data_type': 'integer',
                'is_nullable': 'NO'
            }
        ]
        
        result = get_columns(db_service=mock_db, table_name='users', schema='public')
        
        assert 'columns' in result
        assert len(result['columns']) == 1
        assert result['table_name'] == 'users'
        assert result.get('schema') == 'public'
    
    def test_get_columns_invalid_table(self):
        """Test get_columns with non-existent table."""
        from lib.mcp_tools import get_columns
        from models.error_types import InvalidTableError
        
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        
        with pytest.raises(InvalidTableError) as exc_info:
            get_columns(db_service=mock_db, table_name='non_existent_table')
        
        assert "non_existent_table" in str(exc_info.value)
    
    def test_get_columns_includes_constraints(self):
        """Test that get_columns includes constraint information."""
        from lib.mcp_tools import get_columns
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'column_name': 'id',
                'data_type': 'integer',
                'is_nullable': 'NO',
                'column_default': None,
                'is_primary_key': True,
                'is_unique': True
            },
            {
                'column_name': 'email',
                'data_type': 'character varying',
                'is_nullable': 'NO',
                'column_default': None,
                'is_primary_key': False,
                'is_unique': True
            }
        ]
        
        result = get_columns(db_service=mock_db, table_name='users')
        
        id_col = result['columns'][0]
        assert 'is_primary_key' in id_col or 'primary_key' in id_col
        assert 'is_unique' in id_col or 'unique' in id_col
    
    def test_get_columns_response_format(self):
        """Test that get_columns returns proper MCP tool response format."""
        from lib.mcp_tools import get_columns
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'column_name': 'test_col',
                'data_type': 'text',
                'is_nullable': 'YES'
            }
        ]
        
        result = get_columns(db_service=mock_db, table_name='test_table')
        
        # MCP tool response format
        assert isinstance(result, dict)
        assert 'columns' in result
        assert 'table_name' in result
        assert result['table_name'] == 'test_table'
        assert 'column_count' in result or 'count' in result