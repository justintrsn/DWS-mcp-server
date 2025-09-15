"""Database service for PostgreSQL connections."""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from models.error_types import ConnectionError, MCPError


class DatabaseService:
    """Service for managing PostgreSQL database connections."""
    
    def __init__(self, config: Dict[str, Any], pool_size: int = 5):
        """Initialize database service.
        
        Args:
            config: Database configuration dictionary
            pool_size: Maximum number of connections in pool
        """
        self.config = config
        self.pool_size = pool_size
        self.pool = None
        self.query_timeout = config.get('query_timeout', 30) * 1000  # Convert to ms
    
    def connect(self) -> bool:
        """Establish database connection pool.
        
        Returns:
            True if connection successful
            
        Raises:
            ConnectionError: If connection fails
        """
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=self.pool_size,
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password'],
                connect_timeout=self.config.get('connect_timeout', 10)
            )
            return True
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to database: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {str(e)}")
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool.
        
        Yields:
            psycopg2 connection object
            
        Raises:
            ConnectionError: If no connection available
        """
        if not self.pool:
            raise ConnectionError("Database connection pool not initialized")
        
        conn = None
        try:
            conn = self.pool.getconn()
            if conn:
                yield conn
            else:
                raise ConnectionError("Failed to get connection from pool")
        except psycopg2.pool.PoolError as e:
            raise ConnectionError(f"Connection pool exhausted: {str(e)}")
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results.
        
        Args:
            query: SQL query to execute
            params: Query parameters for parameterized queries
            
        Returns:
            List of dictionaries containing query results
            
        Raises:
            MCPError: If query execution fails
        """
        with self.get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set statement timeout
                    cursor.execute(f"SET statement_timeout = {self.query_timeout}")
                    
                    # Execute the actual query
                    cursor.execute(query, params)
                    
                    # Fetch all results
                    results = cursor.fetchall()
                    
                    # Convert RealDictRow to regular dict
                    return [dict(row) for row in results]
                    
            except psycopg2.errors.UndefinedTable as e:
                raise MCPError(f"Table does not exist: {str(e)}", recoverable=False)
            except psycopg2.errors.SyntaxError as e:
                raise MCPError(f"SQL syntax error: {str(e)}", recoverable=False)
            except psycopg2.errors.InsufficientPrivilege as e:
                raise MCPError(f"Permission denied: {str(e)}", recoverable=False)
            except psycopg2.errors.QueryCanceled as e:
                raise MCPError(f"Query timeout exceeded: {str(e)}", recoverable=True)
            except psycopg2.Error as e:
                raise MCPError(f"Database error: {str(e)}", recoverable=True)
            except Exception as e:
                raise MCPError(f"Unexpected error: {str(e)}", recoverable=False)
    
    def close(self):
        """Close all database connections."""
        if self.pool:
            self.pool.closeall()
            self.pool = None