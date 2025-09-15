"""Health monitoring API service."""

import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
import uvicorn

logger = logging.getLogger(__name__)


class HealthAPI:
    """Health monitoring API service running independently from MCP."""
    
    def __init__(self, db_service=None, host: str = "0.0.0.0", port: int = 8080):
        """Initialize health API service.
        
        Args:
            db_service: Database service instance for health checks
            host: Host to bind the health API to
            port: Port to bind the health API to
        """
        self.db_service = db_service
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP Health API", version="1.0.0")
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0
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