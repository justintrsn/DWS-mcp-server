"""Integration tests for database connection.

These tests verify actual database connectivity:
- Can connect using .env credentials
- Connection pooling works
- Timeouts are handled properly
"""

import pytest
import os
import sys
from unittest.mock import patch
from dotenv import load_dotenv

# Add src to path for imports (will fail until implementation exists)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Load environment variables
load_dotenv()

class TestDatabaseConnection:
    """Integration tests for database connection."""
    
    @pytest.fixture
    def db_config(self):
        """Get database configuration from environment."""
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_DATABASE', 'test_footfall'),
            'user': os.getenv('DB_USER', 'test_user'),
            'password': os.getenv('DB_PASSWORD', 'test_pass')
        }
    
    def test_connect_with_env_credentials(self, db_config):
        """Test connection using .env credentials."""
        from services.database_service import DatabaseService
        
        db_service = DatabaseService(db_config)
        
        # Test connection
        assert db_service.connect() is True
        
        # Test simple query
        result = db_service.execute_query("SELECT 1 as test")
        assert result[0]['test'] == 1
        
        # Clean up
        db_service.close()
    
    def test_connection_pool_initialization(self, db_config):
        """Test that connection pool initializes properly."""
        from services.database_service import DatabaseService
        
        db_service = DatabaseService(db_config, pool_size=5)
        db_service.connect()
        
        assert db_service.pool is not None
        assert db_service.pool.minconn == 2
        assert db_service.pool.maxconn == 5
        
        db_service.close()
    
    def test_invalid_credentials(self):
        """Test handling of invalid database credentials."""
        from services.database_service import DatabaseService
        from models.error_types import ConnectionError
        
        bad_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'nonexistent',
            'user': 'baduser',
            'password': 'wrongpass'
        }
        
        with pytest.raises(ConnectionError) as exc_info:
            db_service = DatabaseService(bad_config)
            db_service.connect()
        
        assert "Failed to connect" in str(exc_info.value) or "authentication" in str(exc_info.value).lower()
    
    def test_connection_timeout(self, db_config):
        """Test connection timeout handling."""
        from services.database_service import DatabaseService
        
        # Use unreachable host to trigger timeout
        timeout_config = db_config.copy()
        timeout_config['host'] = '192.0.2.1'  # TEST-NET-1, guaranteed unreachable
        timeout_config['connect_timeout'] = 2  # 2 second timeout
        
        db_service = DatabaseService(timeout_config)
        
        with pytest.raises(Exception) as exc_info:
            db_service.connect()
        
        assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()
    
    def test_query_execution(self, db_config):
        """Test basic query execution."""
        from services.database_service import DatabaseService
        
        db_service = DatabaseService(db_config)
        db_service.connect()
        
        # Test SELECT query
        result = db_service.execute_query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 5"
        )
        
        assert isinstance(result, list)
        if len(result) > 0:
            assert 'table_name' in result[0]
        
        db_service.close()
    
    def test_connection_reuse(self, db_config):
        """Test that connections are properly reused from pool."""
        from services.database_service import DatabaseService
        
        db_service = DatabaseService(db_config, pool_size=2)
        db_service.connect()
        
        # Execute multiple queries
        for i in range(5):
            result = db_service.execute_query(f"SELECT {i} as num")
            assert result[0]['num'] == i
        
        # Pool should handle this without creating new connections
        assert db_service.pool is not None
        
        db_service.close()
    
    def test_concurrent_connections(self, db_config):
        """Test handling of concurrent connection requests with pool overflow."""
        from services.database_service import DatabaseService
        import threading
        import time

        db_service = DatabaseService(db_config, pool_size=3)
        db_service.connect()

        results = []
        errors = []
        pool_exhausted_errors = []

        def run_query(query_id):
            try:
                # Add small delay to ensure queries run concurrently
                time.sleep(0.01)
                result = db_service.execute_query(f"SELECT {query_id} as id")
                results.append(result[0]['id'])
            except Exception as e:
                error_msg = str(e)
                if "pool exhausted" in error_msg.lower():
                    pool_exhausted_errors.append(error_msg)
                else:
                    errors.append(error_msg)

        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=run_query, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # With pool_size=3 and 10 concurrent requests, some should be rejected
        # but no unexpected errors should occur
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) + len(pool_exhausted_errors) == 10
        assert len(results) <= 3  # At most 3 can succeed with pool_size=3
        assert len(pool_exhausted_errors) >= 7  # At least 7 should be rejected
        
        db_service.close()
    
    @pytest.mark.skipif(
        os.getenv('DB_HOST') != '124.243.149.239',
        reason="DWS-specific test"
    )
    def test_dws_specific_connection(self, db_config):
        """Test connection specifically to DWS instance."""
        from services.database_service import DatabaseService
        
        # Ensure we're using DWS credentials
        assert db_config['host'] == '124.243.149.239'
        assert db_config['port'] == 8000
        assert db_config['database'] == 'footfall'
        
        db_service = DatabaseService(db_config)
        db_service.connect()
        
        # Query DWS-specific system table
        result = db_service.execute_query(
            "SELECT version()"
        )
        
        assert len(result) > 0
        assert 'version' in result[0]
        
        db_service.close()