"""Contract tests for get_table_stats MCP tool.

These tests verify the get_table_stats tool contract:
- Returns row count and size statistics
- Handles multiple tables
- Returns proper error for invalid tables
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports (will fail until implementation exists)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

class TestGetTableStatsContract:
    """Contract tests for get_table_stats tool."""
    
    def test_get_table_stats_returns_statistics(self):
        """Test that get_table_stats returns row count and size."""
        # This will fail until we implement the tool
        from lib.mcp_tools import get_table_stats
        
        # Mock database service
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'relname': 'users',
                'n_live_tup': 1500,
                'n_dead_tup': 10,
                'pg_size_pretty': '128 KB',
                'pg_total_relation_size': 131072
            }
        ]
        
        result = get_table_stats(db_service=mock_db, table_name='users')
        
        assert isinstance(result, dict)
        assert 'table_name' in result
        assert result['table_name'] == 'users'
        assert 'row_count' in result
        assert result['row_count'] == 1500
        assert 'size' in result or 'table_size' in result
        assert 'size_bytes' in result or 'total_size_bytes' in result
    
    def test_get_table_stats_multiple_tables(self):
        """Test get_table_stats can handle multiple tables."""
        from lib.mcp_tools import get_table_stats
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'relname': 'users',
                'n_live_tup': 1000,
                'pg_size_pretty': '64 KB',
                'pg_total_relation_size': 65536
            },
            {
                'relname': 'orders',
                'n_live_tup': 5000,
                'pg_size_pretty': '256 KB',
                'pg_total_relation_size': 262144
            }
        ]
        
        result = get_table_stats(db_service=mock_db, table_names=['users', 'orders'])
        
        assert isinstance(result, dict)
        assert 'tables' in result
        assert isinstance(result['tables'], list)
        assert len(result['tables']) == 2
        
        # Check each table has required fields
        for table_stat in result['tables']:
            assert 'table_name' in table_stat
            assert 'row_count' in table_stat
            assert 'size' in table_stat or 'table_size' in table_stat
    
    def test_get_table_stats_invalid_table(self):
        """Test get_table_stats with non-existent table."""
        from lib.mcp_tools import get_table_stats
        from models.error_types import InvalidTableError
        
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        
        with pytest.raises(InvalidTableError) as exc_info:
            get_table_stats(db_service=mock_db, table_name='non_existent_table')
        
        assert "non_existent_table" in str(exc_info.value)
    
    def test_get_table_stats_includes_indexes(self):
        """Test that get_table_stats includes index statistics."""
        from lib.mcp_tools import get_table_stats
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'relname': 'users',
                'n_live_tup': 1000,
                'pg_size_pretty': '64 KB',
                'pg_total_relation_size': 65536,
                'pg_indexes_size': 16384,
                'n_indexes': 3
            }
        ]
        
        result = get_table_stats(db_service=mock_db, table_name='users')
        
        assert 'index_count' in result or 'indexes' in result
        assert 'index_size' in result or 'indexes_size' in result
    
    def test_get_table_stats_vacuum_info(self):
        """Test that get_table_stats includes vacuum/analyze info."""
        from lib.mcp_tools import get_table_stats
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'relname': 'users',
                'n_live_tup': 1000,
                'n_dead_tup': 50,
                'pg_size_pretty': '64 KB',
                'pg_total_relation_size': 65536,
                'last_vacuum': '2024-01-15 10:30:00',
                'last_analyze': '2024-01-15 10:35:00'
            }
        ]
        
        result = get_table_stats(db_service=mock_db, table_name='users')
        
        assert 'dead_rows' in result or 'n_dead_tup' in result
        assert 'last_vacuum' in result or 'vacuum_info' in result
        assert 'last_analyze' in result or 'analyze_info' in result
    
    def test_get_table_stats_response_format(self):
        """Test that get_table_stats returns proper MCP tool response format."""
        from lib.mcp_tools import get_table_stats
        
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                'relname': 'test_table',
                'n_live_tup': 100,
                'pg_size_pretty': '8 KB',
                'pg_total_relation_size': 8192
            }
        ]
        
        result = get_table_stats(db_service=mock_db, table_name='test_table')
        
        # MCP tool response format
        assert isinstance(result, dict)
        assert 'table_name' in result
        assert 'row_count' in result
        assert 'size' in result or 'table_size' in result
        assert isinstance(result.get('row_count'), int)