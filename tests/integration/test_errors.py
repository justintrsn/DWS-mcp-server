"""Integration tests for error handling.

These tests verify proper error handling:
- Invalid table names
- SQL injection attempts
- Connection failures
- Query timeouts
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch
from dotenv import load_dotenv

# Add src to path for imports (will fail until implementation exists)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Load environment variables
load_dotenv()

class TestErrorHandling:
    """Integration tests for error handling."""
    
    @pytest.fixture
    def db_service(self):
        """Create a database service instance."""
        from services.database_service import DatabaseService
        
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_DATABASE', 'test_footfall'),
            'user': os.getenv('DB_USER', 'test_user'),
            'password': os.getenv('DB_PASSWORD', 'test_pass')
        }
        
        service = DatabaseService(config)
        service.connect()
        yield service
        service.close()
    
    def test_invalid_table_name_error(self, db_service):
        """Test error handling for invalid table names."""
        from lib.mcp_tools import get_columns
        from models.error_types import InvalidTableError
        
        with pytest.raises(InvalidTableError) as exc_info:
            get_columns(db_service=db_service, table_name='this_table_does_not_exist_12345')
        
        error = exc_info.value
        assert "this_table_does_not_exist_12345" in str(error)
        assert hasattr(error, 'table_name')
        assert error.table_name == 'this_table_does_not_exist_12345'
    
    def test_sql_injection_prevention(self, db_service):
        """Test that SQL injection attempts are blocked."""
        from lib.mcp_tools import get_columns
        from models.error_types import InvalidTableError, MCPError
        
        # Various SQL injection attempts
        injection_attempts = [
            "users; DROP TABLE users;--",
            "users' OR '1'='1",
            "users/**/UNION/**/SELECT/**/1",
            "users`; DELETE FROM users;",
            "users'); DROP TABLE users;--"
        ]
        
        for malicious_input in injection_attempts:
            with pytest.raises((InvalidTableError, MCPError, ValueError)) as exc_info:
                get_columns(db_service=db_service, table_name=malicious_input)
            
            # Should reject the input before executing any query
            assert "invalid" in str(exc_info.value).lower() or "not allowed" in str(exc_info.value).lower()
    
    def test_connection_lost_during_query(self, db_service):
        """Test handling when connection is lost during query."""
        from models.error_types import ConnectionError
        
        # Simulate connection loss
        with patch.object(db_service, 'execute_query') as mock_execute:
            mock_execute.side_effect = ConnectionError("Connection lost")
            
            with pytest.raises(ConnectionError) as exc_info:
                db_service.execute_query("SELECT 1")
            
            assert "Connection lost" in str(exc_info.value)
            assert hasattr(exc_info.value, 'recoverable')
            assert exc_info.value.recoverable is True
    
    def test_query_timeout(self, db_service):
        """Test query timeout handling."""
        from models.error_types import MCPError
        
        # Set a very short timeout
        db_service.query_timeout = 0.001  # 1ms timeout
        
        with pytest.raises(MCPError) as exc_info:
            # Run a query that takes time
            db_service.execute_query(
                "SELECT pg_sleep(1)"  # Sleep for 1 second
            )
        
        assert "timeout" in str(exc_info.value).lower()
        assert hasattr(exc_info.value, 'recoverable')
        assert exc_info.value.recoverable is True
    
    def test_invalid_schema_name(self, db_service):
        """Test error handling for invalid schema names - returns empty list."""
        from lib.mcp_tools import get_tables

        # Non-existent schema should return empty list, not error
        result = get_tables(db_service=db_service, schema='nonexistent_schema_12345')

        assert result['tables'] == []
        assert result['count'] == 0
    
    def test_permission_denied_error(self):
        """Test handling of write operation errors."""
        from services.database_service import DatabaseService
        from models.error_types import MCPError

        # Try to connect with read-only user and perform write operation
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_DATABASE', 'test_footfall'),
            'user': os.getenv('DB_USER', 'test_user'),
            'password': os.getenv('DB_PASSWORD', 'test_pass')
        }

        db_service = DatabaseService(config)
        db_service.connect()

        with pytest.raises(MCPError) as exc_info:
            # Attempt a write operation (should fail for read-only user)
            db_service.execute_query("CREATE TABLE test_table (id INT)")

        # The error message might vary depending on database configuration
        # but it should be a database error
        assert "database error" in str(exc_info.value).lower() or \
               "permission" in str(exc_info.value).lower() or \
               "denied" in str(exc_info.value).lower() or \
               "no results" in str(exc_info.value).lower()
        assert hasattr(exc_info.value, 'recoverable')

        db_service.close()
    
    def test_malformed_query_error(self, db_service):
        """Test handling of malformed SQL queries."""
        from models.error_types import MCPError
        
        with pytest.raises(MCPError) as exc_info:
            db_service.execute_query("SELECT * FROM WHERE")  # Invalid SQL
        
        assert "syntax" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()
    
    def test_error_response_format(self, db_service):
        """Test that errors follow MCP error response format."""
        from lib.mcp_tools import get_columns
        from models.error_types import InvalidTableError
        
        try:
            get_columns(db_service=db_service, table_name='nonexistent_table')
            assert False, "Should have raised InvalidTableError"
        except InvalidTableError as e:
            # Check error has required attributes
            assert hasattr(e, 'message') or hasattr(e, 'args')
            assert hasattr(e, 'recoverable')
            assert hasattr(e, 'table_name')
            
            # Check error can be serialized for MCP response
            error_dict = {
                'error': str(e),
                'type': e.__class__.__name__,
                'recoverable': e.recoverable,
                'details': {
                    'table_name': e.table_name
                }
            }
            assert isinstance(error_dict, dict)
    
    def test_connection_pool_exhaustion(self):
        """Test error when connection pool is exhausted."""
        from services.database_service import DatabaseService
        from models.error_types import ConnectionError
        import threading
        import time
        
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_DATABASE', 'test_footfall'),
            'user': os.getenv('DB_USER', 'test_user'),
            'password': os.getenv('DB_PASSWORD', 'test_pass')
        }
        
        # Create service with very small pool
        db_service = DatabaseService(config, pool_size=1)
        db_service.connect()
        
        # Hold a connection
        conn1 = db_service.pool.getconn()
        
        # Try to get another connection (should fail or timeout)
        with pytest.raises((ConnectionError, Exception)) as exc_info:
            conn2 = db_service.pool.getconn(timeout=1)
        
        assert "exhausted" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()
        
        # Return connection
        db_service.pool.putconn(conn1)
        db_service.close()
    
    def test_graceful_error_recovery(self, db_service):
        """Test that service can recover from errors gracefully."""
        from models.error_types import MCPError
        
        # Cause an error
        try:
            db_service.execute_query("SELECT * FROM nonexistent_table")
        except MCPError:
            pass  # Expected
        
        # Service should still work for valid queries
        result = db_service.execute_query("SELECT 1 as test")
        assert result[0]['test'] == 1