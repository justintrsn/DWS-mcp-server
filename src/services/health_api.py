"""Health monitoring API service."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException
import uvicorn

from models.database_profiles import (
    DatabaseSwitchRequest,
    DatabaseConnectionTest,
    DatabaseSwitchResponse,
    DatabaseConnectionTestResponse,
    DatabaseListResponse,
    database_manager
)

logger = logging.getLogger(__name__)


class HealthAPI:
    """Health monitoring API service running independently from MCP."""

    def __init__(self, db_service=None, db_config=None, host: str = "0.0.0.0", port: int = 8080):
        """Initialize health API service.

        Args:
            db_service: Database service instance for health checks
            db_config: Database configuration instance for profile management
            host: Host to bind the health API to
            port: Port to bind the health API to
        """
        self.db_service = db_service
        self.db_config = db_config
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP Health API", version="1.0.0")
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0

        # Set up database manager
        if db_config:
            database_manager.set_config(db_config, db_service)

        self._setup_routes()
        
    def _setup_routes(self):
        """Set up FastAPI routes for health monitoring."""
        
        @self.app.get("/health")
        async def health_check() -> Dict[str, Any]:
            """Overall system health status."""
            try:
                # Basic health check
                uptime = (datetime.now() - self.start_time).total_seconds()
                
                # Check database if available
                db_healthy = await self._check_database_health()
                
                return {
                    "status": "healthy" if db_healthy else "degraded",
                    "timestamp": datetime.now().isoformat(),
                    "uptime_seconds": uptime,
                    "version": "1.0.0"
                }
            except Exception as e:
                logger.error(f"Health check error: {e}")
                raise HTTPException(status_code=503, detail=str(e))
        
        @self.app.get("/health/database")
        async def database_health() -> Dict[str, Any]:
            """Database connection pool status."""
            if not self.db_service:
                return {
                    "status": "unavailable",
                    "message": "Database service not configured"
                }
            
            try:
                # Test database connection
                result = self.db_service.execute_query("SELECT 1 as health")
                is_healthy = result[0]['health'] == 1
                
                # Get pool stats
                pool_stats = {
                    "initialized": self.db_service.pool is not None,
                    "max_connections": self.db_service.pool_size,
                    "database": self.db_service.config.get('database', 'unknown')
                }
                
                if self.db_service.pool:
                    # Get connection pool metrics
                    pool_stats.update({
                        "min_connections": self.db_service.pool.minconn,
                        "max_connections": self.db_service.pool.maxconn
                    })
                
                return {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "connection_pool": pool_stats,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Database health check error: {e}")
                return {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        @self.app.get("/health/metrics")
        async def health_metrics() -> Dict[str, Any]:
            """Request rates and performance metrics."""
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            return {
                "metrics": {
                    "total_requests": self.request_count,
                    "total_errors": self.error_count,
                    "error_rate": self.error_count / max(self.request_count, 1),
                    "uptime_seconds": uptime,
                    "requests_per_second": self.request_count / max(uptime, 1)
                },
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/health/ready")
        async def readiness_check() -> Dict[str, Any]:
            """Readiness probe for container orchestration."""
            # Check if all services are ready
            db_ready = await self._check_database_health()
            
            if not db_ready:
                raise HTTPException(
                    status_code=503,
                    detail="Service not ready: database connection unavailable"
                )
            
            return {
                "ready": True,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/health/live")
        async def liveness_check() -> Dict[str, Any]:
            """Liveness probe for container orchestration."""
            # Simple check that the service is running
            return {
                "alive": True,
                "timestamp": datetime.now().isoformat()
            }

        # Database profile management endpoints
        @self.app.get("/api/database/list", response_model=DatabaseListResponse)
        async def list_database_profiles() -> DatabaseListResponse:
            """List all available database profiles."""
            try:
                return database_manager.list_profiles()
            except Exception as e:
                logger.error(f"Failed to list database profiles: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/database/current")
        async def get_current_profile() -> Dict[str, Any]:
            """Get information about the current database profile."""
            try:
                profile_info = database_manager.get_current_profile_info()
                if profile_info:
                    return profile_info.dict()
                else:
                    return {"status": "no_profile", "message": "No database profile configured"}
            except Exception as e:
                logger.error(f"Failed to get current profile: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/database/switch", response_model=DatabaseSwitchResponse)
        async def switch_database_profile(request: DatabaseSwitchRequest) -> DatabaseSwitchResponse:
            """Switch to a different database profile."""
            try:
                # Validate profile exists and is available
                can_switch, message = database_manager.can_switch_to_profile(request.profile)
                if not can_switch:
                    return DatabaseSwitchResponse(
                        success=False,
                        message=message
                    )

                # Get current profile for tracking
                previous_profile = None
                if database_manager.config and database_manager.config.current_profile:
                    previous_profile = database_manager.config.current_profile.name

                # Test connection if requested
                validation_performed = False
                if request.validate_connection:
                    test_result = await self._test_profile_connection(request.profile)
                    validation_performed = True
                    if not test_result.success:
                        return DatabaseSwitchResponse(
                            success=False,
                            message=f"Connection validation failed: {test_result.message}",
                            previous_profile=previous_profile,
                            validation_performed=validation_performed
                        )

                # Perform the switch
                if not database_manager.config:
                    return DatabaseSwitchResponse(
                        success=False,
                        message="No database configuration available"
                    )

                database_manager.config.switch_profile(request.profile)

                # Update database service if available
                if self.db_service and hasattr(self.db_service, 'update_config'):
                    self.db_service.update_config(database_manager.config)

                return DatabaseSwitchResponse(
                    success=True,
                    message=f"Successfully switched to profile '{request.profile}'",
                    previous_profile=previous_profile,
                    current_profile=request.profile,
                    switched_at=datetime.now().isoformat(),
                    validation_performed=validation_performed
                )

            except Exception as e:
                logger.error(f"Failed to switch database profile: {e}")
                return DatabaseSwitchResponse(
                    success=False,
                    message=f"Profile switch failed: {str(e)}"
                )

        @self.app.post("/api/database/test", response_model=DatabaseConnectionTestResponse)
        async def test_database_connection(request: DatabaseConnectionTest) -> DatabaseConnectionTestResponse:
            """Test connection to a specific database profile."""
            try:
                return await self._test_profile_connection(request.profile, request.timeout)
            except Exception as e:
                logger.error(f"Database connection test failed: {e}")
                return DatabaseConnectionTestResponse(
                    profile=request.profile,
                    success=False,
                    message=f"Connection test failed: {str(e)}",
                    tested_at=datetime.now().isoformat()
                )
    
    async def _check_database_health(self) -> bool:
        """Check if database is healthy.

        Returns:
            True if database is healthy, False otherwise
        """
        if not self.db_service:
            return False

        try:
            result = self.db_service.execute_query("SELECT 1 as health")
            return result[0]['health'] == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def _test_profile_connection(self, profile_name: str, timeout: int = 10) -> DatabaseConnectionTestResponse:
        """Test connection to a specific database profile.

        Args:
            profile_name: Name of the database profile to test
            timeout: Connection timeout in seconds

        Returns:
            DatabaseConnectionTestResponse with test results
        """
        start_time = datetime.now()

        try:
            # Check if profile exists
            if not database_manager.validate_profile_exists(profile_name):
                return DatabaseConnectionTestResponse(
                    profile=profile_name,
                    success=False,
                    message=f"Profile '{profile_name}' does not exist or is disabled",
                    tested_at=start_time.isoformat()
                )

            # Get profile configuration
            if not database_manager.config:
                return DatabaseConnectionTestResponse(
                    profile=profile_name,
                    success=False,
                    message="No database configuration available",
                    tested_at=start_time.isoformat()
                )

            profile = database_manager.config.profiles[profile_name]

            # Test connection using psycopg2
            import psycopg2
            import psycopg2.extras

            conn_params = profile.to_dict()
            conn_params['connect_timeout'] = min(timeout, 60)

            with psycopg2.connect(**conn_params) as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # Test basic query
                    cursor.execute("SELECT version() as version, current_database() as database")
                    result = cursor.fetchone()

                    connection_time = (datetime.now() - start_time).total_seconds() * 1000

                    return DatabaseConnectionTestResponse(
                        profile=profile_name,
                        success=True,
                        message="Connection successful",
                        connection_time_ms=connection_time,
                        database_info={
                            "version": result['version'],
                            "database": result['database'],
                            "host": profile.host,
                            "port": profile.port
                        },
                        tested_at=start_time.isoformat()
                    )

        except psycopg2.OperationalError as e:
            return DatabaseConnectionTestResponse(
                profile=profile_name,
                success=False,
                message=f"Connection failed: {str(e)}",
                tested_at=start_time.isoformat()
            )
        except Exception as e:
            logger.error(f"Profile connection test failed for '{profile_name}': {e}")
            return DatabaseConnectionTestResponse(
                profile=profile_name,
                success=False,
                message=f"Connection test error: {str(e)}",
                tested_at=start_time.isoformat()
            )
    
    def update_metrics(self, request_success: bool = True):
        """Update request metrics.
        
        Args:
            request_success: Whether the request was successful
        """
        self.request_count += 1
        if not request_success:
            self.error_count += 1
    
    def run(self):
        """Run the health API server."""
        logger.info(f"Starting Health API on {self.host}:{self.port}")
        
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
        except KeyboardInterrupt:
            logger.info("Health API shutdown requested")
        except Exception as e:
            logger.error(f"Health API error: {e}")
            raise
    
    async def run_async(self):
        """Run the health API server asynchronously."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def stop(self):
        """Stop the health API server."""
        logger.info("Stopping Health API")