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
        # This will fail until we implement the tool
        from lib.mcp_tools import get_tables
        
        # Mock database service
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {'table_name': 'users'},
            {'table_name': 'products'},
            {'table_name': 'orders'}
        ]
        
        result = get_tables(db_service=mock_db)
        
        assert isinstance(result, dict)
        assert 'tables' in result
        assert isinstance(result['tables'], list)
        assert len(result['tables']) == 3
        assert 'users' in result['tables']
        assert 'products' in result['tables']
        assert 'orders' in result['tables']
    
    def test_get_tables_with_schema_filter(self):
        """Test that get_tables can filter by schema."""
        from lib.mcp_tools import get_tables
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {'table_name': 'users', 'table_schema': 'public'},
            {'table_name': 'products', 'table_schema': 'public'}
        ]
        
        result = get_tables(db_service=mock_db, schema='public')
        
        assert 'tables' in result
        assert len(result['tables']) == 2
    
    def test_get_tables_empty_database(self):
        """Test get_tables with empty database."""
        from lib.mcp_tools import get_tables
        
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        
        result = get_tables(db_service=mock_db)
        
        assert 'tables' in result
        assert result['tables'] == []
    
    def test_get_tables_connection_error(self):
        """Test get_tables handles connection errors properly."""
        from lib.mcp_tools import get_tables
        from models.error_types import ConnectionError
        
        mock_db = Mock()
        mock_db.execute_query.side_effect = ConnectionError("Failed to connect to database")
        
        with pytest.raises(ConnectionError) as exc_info:
            get_tables(db_service=mock_db)
        
        assert "Failed to connect" in str(exc_info.value)
    
    def test_get_tables_response_format(self):
        """Test that get_tables returns proper MCP tool response format."""
        from lib.mcp_tools import get_tables
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {'table_name': 'test_table'}
        ]
        
        result = get_tables(db_service=mock_db)
        
        # MCP tool response format
        assert isinstance(result, dict)
        assert 'tables' in result
        assert 'count' in result
        assert result['count'] == 1
        assert 'schema' in result or 'database' in result