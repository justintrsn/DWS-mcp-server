"""Database configuration loader."""

import os
from typing import Dict, Any
from dotenv import load_dotenv


class DatabaseConfig:
    """Database configuration from environment variables."""
    
    def __init__(self):
        load_dotenv()
        self.validate()
        # Validate numeric types during initialization
        self._validate_numeric_config()
    
    @property
    def host(self) -> str:
        return os.getenv('DB_HOST', 'localhost')
    
    @property
    def port(self) -> int:
        return int(os.getenv('DB_PORT', '5432'))
    
    @property
    def database(self) -> str:
        return os.getenv('DB_DATABASE', 'footfall')
    
    @property
    def user(self) -> str:
        return os.getenv('DB_USER', 'dbadmin')
    
    @property
    def password(self) -> str:
        return os.getenv('DB_PASSWORD', '')
    
    @property
    def connect_timeout(self) -> int:
        return int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
    
    @property
    def query_timeout(self) -> int:
        return int(os.getenv('DB_QUERY_TIMEOUT', '30'))
    
    def validate(self):
        """Validate required configuration."""
        if not self.password:
            raise ValueError("DB_PASSWORD environment variable is required")
        if not self.host:
            raise ValueError("DB_HOST environment variable is required")
        if not self.database:
            raise ValueError("DB_DATABASE environment variable is required")
        if not self.user:
            raise ValueError("DB_USER environment variable is required")

    def _validate_numeric_config(self):
        """Validate that numeric config values can be parsed."""
        # Validate port
        port_str = os.getenv('DB_PORT', '5432')
        try:
            int(port_str)
        except ValueError:
            raise ValueError(f"Invalid DB_PORT value: {port_str}")

        # Validate connect_timeout
        connect_timeout_str = os.getenv('DB_CONNECT_TIMEOUT', '10')
        try:
            int(connect_timeout_str)
        except ValueError:
            raise ValueError(f"Invalid DB_CONNECT_TIMEOUT value: {connect_timeout_str}")

        # Validate query_timeout
        query_timeout_str = os.getenv('DB_QUERY_TIMEOUT', '30')
        try:
            int(query_timeout_str)
        except ValueError:
            raise ValueError(f"Invalid DB_QUERY_TIMEOUT value: {query_timeout_str}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for psycopg2."""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'connect_timeout': self.connect_timeout
        }