"""Database service for PostgreSQL connections."""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from src.models.error_types import ConnectionError, MCPError
from src.utils.logger import get_logger, log_database_query, log_error_with_context

# Module logger
logger = get_logger(__name__)


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
        logger.info(f"Connecting to database: {self.config['host']}:{self.config['port']}/{self.config['database']}")
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
            logger.info(f"Database connection pool established (size: {self.pool_size})")
            return True
        except psycopg2.Error as e:
            log_error_with_context(e, {'host': self.config['host'], 'database': self.config['database']}, logger)
            raise ConnectionError(f"Failed to connect to database: {str(e)}")
        except Exception as e:
            log_error_with_context(e, {'host': self.config['host'], 'database': self.config['database']}, logger)
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
            logger.error("Attempted to get connection but pool not initialized")
            raise ConnectionError("Database connection pool not initialized")

        conn = None
        try:
            logger.debug("Getting connection from pool")
            conn = self.pool.getconn()
            if conn:
                logger.debug(f"Connection acquired from pool")
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
        log_database_query(query, params, logger)
        with self.get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set statement timeout
                    cursor.execute(f"SET statement_timeout = {self.query_timeout}")

                    # Execute the actual query
                    cursor.execute(query, params)

                    # Fetch all results
                    results = cursor.fetchall()
                    logger.debug(f"Query returned {len(results)} rows")

                    # Convert RealDictRow to regular dict
                    return [dict(row) for row in results]

            except psycopg2.errors.UndefinedTable as e:
                logger.error(f"Table does not exist: {str(e)}")
                raise MCPError(f"Table does not exist: {str(e)}", recoverable=False)
            except psycopg2.errors.SyntaxError as e:
                logger.error(f"SQL syntax error: {str(e)}")
                raise MCPError(f"SQL syntax error: {str(e)}", recoverable=False)
            except psycopg2.errors.InsufficientPrivilege as e:
                logger.error(f"Permission denied: {str(e)}")
                raise MCPError(f"Permission denied: {str(e)}", recoverable=False)
            except psycopg2.errors.QueryCanceled as e:
                logger.warning(f"Query timeout exceeded: {str(e)}")
                raise MCPError(f"Query timeout exceeded: {str(e)}", recoverable=True)
            except psycopg2.Error as e:
                logger.error(f"Database error: {str(e)}")
                raise MCPError(f"Database error: {str(e)}", recoverable=True)
            except Exception as e:
                log_error_with_context(e, {'query': query[:100], 'params': params}, logger)
                raise MCPError(f"Unexpected error: {str(e)}", recoverable=False)

    def execute_readonly_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query in a read-only transaction with automatic rollback.

        This ensures safety by preventing any modifications to the database,
        even if the query accidentally contains DML operations.

        Args:
            query: SQL query to execute
            params: Query parameters for parameterized queries

        Returns:
            List of dictionaries containing query results

        Raises:
            MCPError: If query execution fails
        """
        log_database_query(query, params, logger)
        logger.debug("Executing read-only query")
        with self.get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Start READ ONLY transaction
                    cursor.execute("BEGIN TRANSACTION READ ONLY")

                    # Set statement timeout
                    cursor.execute(f"SET statement_timeout = {self.query_timeout}")

                    # Execute the actual query
                    cursor.execute(query, params)

                    # Fetch all results
                    results = cursor.fetchall()
                    logger.debug(f"Read-only query returned {len(results)} rows")

                    # Always rollback to end the transaction
                    cursor.execute("ROLLBACK")

                    # Convert RealDictRow to regular dict
                    return [dict(row) for row in results]

            except psycopg2.errors.UndefinedTable as e:
                # Ensure rollback on error
                conn.rollback()
                raise MCPError(f"Table does not exist: {str(e)}", recoverable=False)
            except psycopg2.errors.SyntaxError as e:
                conn.rollback()
                raise MCPError(f"SQL syntax error: {str(e)}", recoverable=False)
            except psycopg2.errors.InsufficientPrivilege as e:
                conn.rollback()
                raise MCPError(f"Permission denied: {str(e)}", recoverable=False)
            except psycopg2.errors.QueryCanceled as e:
                conn.rollback()
                raise MCPError(
                    f"Query timeout exceeded. Consider refining your query to be more specific or limit the data range.",
                    recoverable=True
                )
            except psycopg2.errors.ReadOnlySqlTransaction as e:
                conn.rollback()
                raise MCPError(f"Write operation attempted in read-only mode: {str(e)}", recoverable=False)
            except psycopg2.Error as e:
                conn.rollback()
                raise MCPError(f"Database error: {str(e)}", recoverable=True)
            except Exception as e:
                conn.rollback()
                raise MCPError(f"Unexpected error: {str(e)}", recoverable=False)
    
    def close(self):
        """Close all database connections."""
        if self.pool:
            self.pool.closeall()
            self.pool = None