"""Pydantic models for MCP tool responses.

This module defines response models for database-level tools to ensure
type safety, validation, and consistent API responses.
"""

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Schema-related response models
# ============================================================================

class SchemaInfo(BaseModel):
    """Information about a database schema."""

    schema_name: str = Field(..., description="Name of the schema")
    schema_owner: str = Field(..., description="Owner of the schema")
    schema_type: Literal["System Schema", "User Schema", "Public Schema", "Extension Schema"] = Field(
        ..., description="Classification of the schema"
    )
    table_count: Optional[int] = Field(None, ge=0, description="Number of tables in schema")
    size_bytes: Optional[int] = Field(None, ge=0, description="Total size in bytes")
    size_pretty: Optional[str] = Field(None, description="Human-readable size")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schema_name": "public",
                "schema_owner": "pg_database_owner",
                "schema_type": "Public Schema",
                "table_count": 10,
                "size_bytes": 1048576,
                "size_pretty": "1 MB"
            }
        }
    )


class SchemasListResponse(BaseModel):
    """Response model for list_schemas tool."""

    database: str = Field(..., description="Database name")
    count: int = Field(..., ge=0, description="Total number of schemas")
    schemas: List[SchemaInfo] = Field(..., description="List of schema information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "database": "test_footfall",
                "count": 2,
                "schemas": [
                    {
                        "schema_name": "public",
                        "schema_owner": "pg_database_owner",
                        "schema_type": "Public Schema",
                        "table_count": 10
                    }
                ]
            }
        }
    )


# ============================================================================
# Database statistics response models
# ============================================================================

class DatabaseStatistics(BaseModel):
    """Database performance and activity statistics."""

    transactions_committed: int = Field(..., ge=0, description="Total committed transactions")
    transactions_rolled_back: int = Field(..., ge=0, description="Total rolled back transactions")
    blocks_read: int = Field(..., ge=0, description="Disk blocks read")
    blocks_hit: int = Field(..., ge=0, description="Buffer cache hits")
    cache_hit_ratio: float = Field(..., ge=0, le=100, description="Cache hit percentage")
    temp_files: int = Field(..., ge=0, description="Number of temporary files created")
    temp_bytes: int = Field(..., ge=0, description="Total bytes written to temp files")
    deadlocks: int = Field(..., ge=0, description="Number of deadlocks detected")

    @field_validator('cache_hit_ratio')
    @classmethod
    def validate_percentage(cls, v):
        """Ensure cache hit ratio is a valid percentage."""
        if not 0 <= v <= 100:
            raise ValueError('cache_hit_ratio must be between 0 and 100')
        return round(v, 2)


class DatabaseStatsResponse(BaseModel):
    """Response model for get_database_stats tool."""

    database_name: str = Field(..., description="Name of the database")
    size_bytes: int = Field(..., ge=0, description="Database size in bytes")
    size_pretty: str = Field(..., description="Human-readable database size")
    connection_limit: int = Field(..., description="Connection limit (-1 for unlimited)")
    current_connections: int = Field(..., ge=0, description="Current active connections")
    max_connections: int = Field(..., gt=0, description="Maximum allowed connections")
    version: str = Field(..., description="PostgreSQL version")
    server_start_time: Optional[str] = Field(None, description="Server start timestamp")
    uptime: Optional[str] = Field(None, description="Server uptime in human-readable format")
    statistics: DatabaseStatistics = Field(..., description="Performance statistics")

    @field_validator('connection_limit')
    @classmethod
    def validate_connection_limit(cls, v):
        """Connection limit must be -1 (unlimited) or positive."""
        if v != -1 and v < 0:
            raise ValueError('connection_limit must be -1 or positive')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "database_name": "test_footfall",
                "size_bytes": 7934767,
                "size_pretty": "7749 kB",
                "connection_limit": -1,
                "current_connections": 5,
                "max_connections": 100,
                "version": "15.14",
                "uptime": "2 days 04:15",
                "statistics": {
                    "transactions_committed": 12345,
                    "transactions_rolled_back": 10,
                    "blocks_read": 5000,
                    "blocks_hit": 495000,
                    "cache_hit_ratio": 99.0,
                    "temp_files": 0,
                    "temp_bytes": 0,
                    "deadlocks": 0
                }
            }
        }
    )


# ============================================================================
# Connection information response models
# ============================================================================

class ConnectionsByState(BaseModel):
    """Connection counts grouped by state."""

    active: int = Field(..., ge=0, description="Actively executing queries")
    idle: int = Field(..., ge=0, description="Idle connections")
    idle_in_transaction: int = Field(..., ge=0, description="Idle in transaction")
    idle_in_transaction_aborted: int = Field(..., ge=0, description="Idle in aborted transaction")
    fastpath_function_call: int = Field(..., ge=0, description="Executing fast-path function")
    disabled: int = Field(..., ge=0, description="Disabled connections")


class ConnectionByDatabase(BaseModel):
    """Connection count for a specific database."""

    database: Optional[str] = Field(None, description="Database name (None for background workers)")
    count: int = Field(..., ge=0, description="Number of connections")


class ConnectionInfoResponse(BaseModel):
    """Response model for get_connection_info tool."""

    current_connections: int = Field(..., ge=0, description="Current total connections")
    max_connections: int = Field(..., gt=0, description="Maximum allowed connections")
    idle_connections: int = Field(..., ge=0, description="Number of idle connections")
    active_queries: int = Field(..., ge=0, description="Number of active queries")
    connection_usage_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of max connections in use"
    )
    connections_by_state: Optional[ConnectionsByState] = Field(
        None, description="Connections grouped by state"
    )
    connections_by_database: Optional[List[ConnectionByDatabase]] = Field(
        None, description="Connections grouped by database"
    )
    warnings: Optional[List[str]] = Field(None, description="Connection-related warnings")

    @field_validator('connection_usage_percent')
    @classmethod
    def validate_usage_percent(cls, v):
        """Ensure usage percentage is valid."""
        if v is not None and not 0 <= v <= 100:
            raise ValueError('connection_usage_percent must be between 0 and 100')
        return round(v, 2) if v is not None else v

    @field_validator('current_connections')
    @classmethod
    def validate_current_vs_max(cls, v, info):
        """Ensure current connections don't exceed max."""
        if hasattr(info, 'data') and info.data:
            max_conn = info.data.get('max_connections')
            if max_conn and v > max_conn:
                raise ValueError(f'current_connections ({v}) cannot exceed max_connections ({max_conn})')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_connections": 25,
                "max_connections": 100,
                "idle_connections": 20,
                "active_queries": 5,
                "connection_usage_percent": 25.0,
                "connections_by_state": {
                    "active": 5,
                    "idle": 20,
                    "idle_in_transaction": 0,
                    "idle_in_transaction_aborted": 0,
                    "fastpath_function_call": 0,
                    "disabled": 0
                },
                "warnings": ["WARNING: Connection usage at 75% - monitor for potential saturation"]
            }
        }
    )


# ============================================================================
# Error response models
# ============================================================================

class ErrorDetails(BaseModel):
    """Detailed error information."""

    query: Optional[str] = Field(None, description="Query that caused the error")
    params: Optional[List] = Field(None, description="Query parameters")
    timeout: Optional[int] = Field(None, description="Query timeout in seconds")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error code or type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[ErrorDetails] = Field(None, description="Additional error details")
    recoverable: bool = Field(..., description="Whether the error is recoverable")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ConnectionError",
                "message": "Failed to connect to database",
                "details": {
                    "suggestion": "Check database credentials and network connectivity"
                },
                "recoverable": True
            }
        }
    )


# ============================================================================
# Export all response models
# ============================================================================

__all__ = [
    # Schema models
    'SchemaInfo',
    'SchemasListResponse',
    # Database stats models
    'DatabaseStatistics',
    'DatabaseStatsResponse',
    # Connection info models
    'ConnectionsByState',
    'ConnectionByDatabase',
    'ConnectionInfoResponse',
    # Error models
    'ErrorDetails',
    'ErrorResponse'
]