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

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

class TestGetTableStatsContract:
    """Contract tests for get_table_stats tool."""

    def test_get_table_stats_returns_statistics(self):
        """Test that get_table_stats returns row count and size."""
        from lib.mcp_tools import get_table_stats

        # Mock database service with correct field names
        mock_db = Mock()
        mock_db.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'row_count': 1500,
                'dead_rows': 10,
                'table_size': '128 KB',
                'table_size_bytes': 131072,
                'index_size': '32 KB',
                'index_size_bytes': 32768,
                'toast_size': '0 bytes',
                'toast_size_bytes': 0,
                'total_relation_size': '160 KB',
                'total_relation_size_bytes': 163840,
                'index_count': 2,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1500,
                'rows_updated': 100,
                'rows_deleted': 10,
                'rows_hot_updated': 50,
                'sequential_scans': 100,
                'index_scans': 500,
                'index_scan_ratio': 83.33
            }
        ]

        result = get_table_stats(db_service=mock_db, table_name='users')

        assert isinstance(result, dict)
        assert 'table_name' in result
        assert result['table_name'] == 'users'
        assert 'row_count' in result
        assert result['row_count'] == 1500
        assert 'table_size' in result
        assert 'table_size_bytes' in result

    def test_get_table_stats_multiple_tables(self):
        """Test get_table_stats can handle multiple tables."""
        from lib.mcp_tools import get_table_stats

        mock_db = Mock()
        # For multiple tables, implementation expects multiple rows
        mock_db.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'row_count': 1000,
                'dead_rows': 5,
                'table_size': '64 KB',
                'table_size_bytes': 65536,
                'index_size': '16 KB',
                'index_size_bytes': 16384,
                'toast_size': '0 bytes',
                'toast_size_bytes': 0,
                'total_relation_size': '80 KB',
                'total_relation_size_bytes': 81920,
                'index_count': 1,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 50,
                'rows_deleted': 5,
                'rows_hot_updated': 25,
                'sequential_scans': 50,
                'index_scans': 200,
                'index_scan_ratio': 80.0
            },
            {
                'table_name': 'orders',
                'schema_name': 'public',
                'row_count': 5000,
                'dead_rows': 20,
                'table_size': '256 KB',
                'table_size_bytes': 262144,
                'index_size': '64 KB',
                'index_size_bytes': 65536,
                'toast_size': '0 bytes',
                'toast_size_bytes': 0,
                'total_relation_size': '320 KB',
                'total_relation_size_bytes': 327680,
                'index_count': 3,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 5000,
                'rows_updated': 200,
                'rows_deleted': 20,
                'rows_hot_updated': 100,
                'sequential_scans': 100,
                'index_scans': 800,
                'index_scan_ratio': 88.89
            }
        ]

        result = get_table_stats(db_service=mock_db, table_names=['users', 'orders'])

        assert isinstance(result, dict)
        # Implementation returns 'statistics' for multiple tables
        assert 'statistics' in result
        assert isinstance(result['statistics'], list)
        assert len(result['statistics']) == 2
        assert 'table_count' in result
        assert result['table_count'] == 2

        # Check each table has required fields
        for table_stat in result['statistics']:
            assert 'table_name' in table_stat
            assert 'row_count' in table_stat
            assert 'table_size' in table_stat

    def test_get_table_stats_invalid_table(self):
        """Test get_table_stats with non-existent table."""
        from lib.mcp_tools import get_table_stats
        from src.models.error_types import InvalidTableError

        mock_db = Mock()
        mock_db.execute_readonly_query.return_value = []

        with pytest.raises(InvalidTableError) as exc_info:
            get_table_stats(db_service=mock_db, table_name='non_existent_table')

        assert "non_existent_table" in str(exc_info.value)

    def test_get_table_stats_includes_indexes(self):
        """Test that get_table_stats includes index statistics."""
        from lib.mcp_tools import get_table_stats

        mock_db = Mock()
        mock_db.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'row_count': 1000,
                'dead_rows': 5,
                'table_size': '64 KB',
                'table_size_bytes': 65536,
                'index_size': '16 KB',
                'index_size_bytes': 16384,
                'toast_size': '0 bytes',
                'toast_size_bytes': 0,
                'total_relation_size': '80 KB',
                'total_relation_size_bytes': 81920,
                'index_count': 3,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 50,
                'rows_deleted': 5,
                'rows_hot_updated': 25,
                'sequential_scans': 50,
                'index_scans': 200,
                'index_scan_ratio': 80.0
            }
        ]

        result = get_table_stats(db_service=mock_db, table_name='users')

        assert 'index_count' in result
        assert result['index_count'] == 3
        assert 'index_size' in result
        assert 'index_size_bytes' in result

    def test_get_table_stats_vacuum_info(self):
        """Test that get_table_stats includes vacuum/analyze info."""
        from lib.mcp_tools import get_table_stats

        mock_db = Mock()
        mock_db.execute_readonly_query.return_value = [
            {
                'table_name': 'users',
                'schema_name': 'public',
                'row_count': 1000,
                'dead_rows': 50,
                'table_size': '64 KB',
                'table_size_bytes': 65536,
                'index_size': '16 KB',
                'index_size_bytes': 16384,
                'toast_size': '0 bytes',
                'toast_size_bytes': 0,
                'total_relation_size': '80 KB',
                'total_relation_size_bytes': 81920,
                'index_count': 1,
                'last_vacuum': '2024-01-15 10:30:00',
                'last_autovacuum': None,
                'vacuum_count': 1,
                'autovacuum_count': 0,
                'last_analyze': '2024-01-15 10:35:00',
                'last_autoanalyze': None,
                'analyze_count': 1,
                'autoanalyze_count': 0,
                'rows_inserted': 1000,
                'rows_updated': 50,
                'rows_deleted': 5,
                'rows_hot_updated': 25,
                'sequential_scans': 50,
                'index_scans': 200,
                'index_scan_ratio': 80.0
            }
        ]

        result = get_table_stats(db_service=mock_db, table_name='users')

        assert 'dead_rows' in result
        assert result['dead_rows'] == 50
        assert 'last_vacuum' in result
        assert result['last_vacuum'] == '2024-01-15 10:30:00'
        assert 'last_analyze' in result
        assert result['last_analyze'] == '2024-01-15 10:35:00'

    def test_get_table_stats_response_format(self):
        """Test that get_table_stats returns proper MCP tool response format."""
        from lib.mcp_tools import get_table_stats

        mock_db = Mock()
        mock_db.execute_readonly_query.return_value = [
            {
                'table_name': 'test_table',
                'schema_name': 'public',
                'row_count': 100,
                'dead_rows': 0,
                'table_size': '8 KB',
                'table_size_bytes': 8192,
                'index_size': '0 bytes',
                'index_size_bytes': 0,
                'toast_size': '0 bytes',
                'toast_size_bytes': 0,
                'total_relation_size': '8 KB',
                'total_relation_size_bytes': 8192,
                'index_count': 0,
                'last_vacuum': None,
                'last_autovacuum': None,
                'vacuum_count': 0,
                'autovacuum_count': 0,
                'last_analyze': None,
                'last_autoanalyze': None,
                'analyze_count': 0,
                'autoanalyze_count': 0,
                'rows_inserted': 100,
                'rows_updated': 0,
                'rows_deleted': 0,
                'rows_hot_updated': 0,
                'sequential_scans': 10,
                'index_scans': 0,
                'index_scan_ratio': 0.0
            }
        ]

        result = get_table_stats(db_service=mock_db, table_name='test_table')

        # MCP tool response format
        assert isinstance(result, dict)
        assert 'table_name' in result
        assert result['table_name'] == 'test_table'
        assert 'row_count' in result
        assert isinstance(result['row_count'], int)
        assert 'table_size' in result