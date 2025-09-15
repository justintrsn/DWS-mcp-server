"""Unit tests for database configuration."""

import pytest
import sys
import os
from unittest.mock import patch, Mock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from models.config import DatabaseConfig


class TestDatabaseConfig:
    """Unit tests for database configuration."""
    
    @patch.dict(os.environ, {
        'DB_HOST': 'test-host',
        'DB_PORT': '5432',
        'DB_DATABASE': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'DB_CONNECT_TIMEOUT': '30',
        'DB_QUERY_TIMEOUT': '60'
    })
    def test_config_from_environment(self):
        """Test loading configuration from environment variables."""
        config = DatabaseConfig()
        
        assert config.host == 'test-host'
        assert config.port == 5432
        assert config.database == 'test_db'
        assert config.user == 'test_user'
        assert config.password == 'test_pass'
        assert config.connect_timeout == 30
        assert config.query_timeout == 60
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass'
    }, clear=True)
    @patch('models.config.load_dotenv')  # Prevent loading .env file
    def test_config_defaults(self, mock_load_dotenv):
        """Test configuration with default values."""
        config = DatabaseConfig()

        assert config.host == 'localhost'  # default
        assert config.port == 5432  # default
        assert config.database == 'footfall'  # default
        assert config.user == 'dbadmin'  # default
        assert config.password == 'test_pass'  # from env
        assert config.connect_timeout == 10  # default
        assert config.query_timeout == 30  # default
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('models.config.load_dotenv')  # Prevent loading .env file
    def test_config_missing_password(self, mock_load_dotenv):
        """Test configuration validation with missing password."""
        with pytest.raises(ValueError) as exc_info:
            DatabaseConfig()
        
        assert "DB_PASSWORD environment variable is required" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass',
        'DB_HOST': '',
    })
    def test_config_empty_host(self):
        """Test configuration validation with empty host."""
        with pytest.raises(ValueError) as exc_info:
            DatabaseConfig()
        
        assert "DB_HOST environment variable is required" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass',
        'DB_DATABASE': '',
    })
    def test_config_empty_database(self):
        """Test configuration validation with empty database."""
        with pytest.raises(ValueError) as exc_info:
            DatabaseConfig()
        
        assert "DB_DATABASE environment variable is required" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass',
        'DB_USER': '',
    })
    def test_config_empty_user(self):
        """Test configuration validation with empty user."""
        with pytest.raises(ValueError) as exc_info:
            DatabaseConfig()
        
        assert "DB_USER environment variable is required" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'DB_HOST': 'test-host',
        'DB_PORT': 'invalid',
        'DB_PASSWORD': 'test_pass'
    }, clear=True)
    @patch('models.config.load_dotenv')  # Prevent loading .env file
    def test_config_invalid_port(self, mock_load_dotenv):
        """Test configuration with invalid port number."""
        with pytest.raises(ValueError):
            DatabaseConfig()
    
    @patch.dict(os.environ, {
        'DB_CONNECT_TIMEOUT': 'not_a_number',
        'DB_PASSWORD': 'test_pass'
    }, clear=True)
    @patch('models.config.load_dotenv')  # Prevent loading .env file
    def test_config_invalid_timeout(self, mock_load_dotenv):
        """Test configuration with invalid timeout value."""
        with pytest.raises(ValueError):
            DatabaseConfig()
    
    @patch.dict(os.environ, {
        'DB_HOST': 'test-host',
        'DB_PORT': '5432',
        'DB_DATABASE': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass'
    })
    def test_config_to_dict(self):
        """Test converting configuration to dictionary."""
        config = DatabaseConfig()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict['host'] == 'test-host'
        assert config_dict['port'] == 5432
        assert config_dict['database'] == 'test_db'
        assert config_dict['user'] == 'test_user'
        assert config_dict['password'] == 'test_pass'
        assert config_dict['connect_timeout'] == 10
        
        # Should not include query_timeout in psycopg2 config
        assert 'query_timeout' not in config_dict
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass',
        'DB_PORT': '0'
    })
    def test_config_edge_case_port(self):
        """Test configuration with edge case port values."""
        config = DatabaseConfig()
        assert config.port == 0  # Should accept 0 (though not practical)
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass',
        'DB_PORT': '65535'
    })
    def test_config_max_port(self):
        """Test configuration with maximum port number."""
        config = DatabaseConfig()
        assert config.port == 65535  # Max valid port
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'test_pass',
        'DB_CONNECT_TIMEOUT': '0',
        'DB_QUERY_TIMEOUT': '0'
    })
    def test_config_zero_timeouts(self):
        """Test configuration with zero timeout values."""
        config = DatabaseConfig()
        assert config.connect_timeout == 0  # Should accept 0 (infinite timeout)
        assert config.query_timeout == 0
    
    @patch.dict(os.environ, {
        'DB_PASSWORD': 'pass with spaces',
        'DB_HOST': 'host-with-dashes.example.com',
        'DB_DATABASE': 'db_with_underscores',
        'DB_USER': 'user@domain'
    })
    def test_config_special_characters(self):
        """Test configuration with special characters in values."""
        config = DatabaseConfig()
        
        assert config.password == 'pass with spaces'
        assert config.host == 'host-with-dashes.example.com'
        assert config.database == 'db_with_underscores'
        assert config.user == 'user@domain'
    
    @patch('models.config.load_dotenv')
    @patch.dict(os.environ, {'DB_PASSWORD': 'test_pass'})
    def test_config_loads_dotenv(self, mock_load_dotenv):
        """Test that configuration loads .env file."""
        DatabaseConfig()
        
        # Verify load_dotenv was called
        mock_load_dotenv.assert_called_once()