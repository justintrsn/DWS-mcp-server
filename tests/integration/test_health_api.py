"""Integration tests for health API service."""

import pytest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.health_api import HealthAPI
from services.database_service import DatabaseService


class TestHealthAPI:
    """Integration tests for health API service."""
    
    @pytest.fixture
    def mock_db_service(self):
        """Create a mock database service."""
        mock = Mock(spec=DatabaseService)
        mock.pool = Mock()
        mock.pool.minconn = 2
        mock.pool.maxconn = 10
        mock.pool_size = 10
        mock.config = {'database': 'test_db'}
        mock.execute_query = Mock(return_value=[{'health': 1}])
        return mock
    
    def test_health_api_initialization(self, mock_db_service):
        """Test health API initializes correctly."""
        health_api = HealthAPI(
            db_service=mock_db_service,
            host="127.0.0.1",
            port=8081
        )
        
        assert health_api.db_service == mock_db_service
        assert health_api.host == "127.0.0.1"
        assert health_api.port == 8081
        assert health_api.app is not None
        assert health_api.request_count == 0
        assert health_api.error_count == 0
    
    def test_health_check_endpoint(self, mock_db_service):
        """Test /health endpoint."""
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert data["version"] == "1.0.0"
    
    def test_health_check_degraded(self, mock_db_service):
        """Test /health endpoint when database is unhealthy."""
        mock_db_service.execute_query.side_effect = Exception("DB Error")
        
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
    
    def test_database_health_endpoint(self, mock_db_service):
        """Test /health/database endpoint."""
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health/database")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "connection_pool" in data
        assert data["connection_pool"]["initialized"] is True
        assert data["connection_pool"]["max_connections"] == 10
        assert data["connection_pool"]["database"] == "test_db"
        assert data["connection_pool"]["min_connections"] == 2
    
    def test_database_health_no_service(self):
        """Test /health/database endpoint without database service."""
        health_api = HealthAPI(db_service=None)
        client = TestClient(health_api.app)
        
        response = client.get("/health/database")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unavailable"
        assert "message" in data
    
    def test_database_health_error(self, mock_db_service):
        """Test /health/database endpoint with database error."""
        mock_db_service.execute_query.side_effect = Exception("Connection failed")
        
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health/database")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data
        assert "Connection failed" in data["error"]
    
    def test_metrics_endpoint(self, mock_db_service):
        """Test /health/metrics endpoint."""
        health_api = HealthAPI(db_service=mock_db_service)
        
        # Update some metrics
        health_api.update_metrics(request_success=True)
        health_api.update_metrics(request_success=True)
        health_api.update_metrics(request_success=False)
        
        client = TestClient(health_api.app)
        response = client.get("/health/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert data["metrics"]["total_requests"] == 3
        assert data["metrics"]["total_errors"] == 1
        assert data["metrics"]["error_rate"] == 1/3
        assert "uptime_seconds" in data["metrics"]
        assert "requests_per_second" in data["metrics"]
    
    def test_readiness_check_ready(self, mock_db_service):
        """Test /health/ready endpoint when ready."""
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert "timestamp" in data
    
    def test_readiness_check_not_ready(self, mock_db_service):
        """Test /health/ready endpoint when not ready."""
        mock_db_service.execute_query.side_effect = Exception("DB not ready")
        
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health/ready")
        
        assert response.status_code == 503
        assert "database connection unavailable" in response.json()["detail"]
    
    def test_liveness_check(self, mock_db_service):
        """Test /health/live endpoint."""
        health_api = HealthAPI(db_service=mock_db_service)
        client = TestClient(health_api.app)
        
        response = client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True
        assert "timestamp" in data
    
    def test_update_metrics(self, mock_db_service):
        """Test metrics update functionality."""
        health_api = HealthAPI(db_service=mock_db_service)
        
        assert health_api.request_count == 0
        assert health_api.error_count == 0
        
        # Update with successful request
        health_api.update_metrics(request_success=True)
        assert health_api.request_count == 1
        assert health_api.error_count == 0
        
        # Update with failed request
        health_api.update_metrics(request_success=False)
        assert health_api.request_count == 2
        assert health_api.error_count == 1
    
    @patch('uvicorn.run')
    def test_health_api_run(self, mock_uvicorn, mock_db_service):
        """Test health API run method."""
        health_api = HealthAPI(
            db_service=mock_db_service,
            host="0.0.0.0",
            port=8082
        )
        
        health_api.run()
        
        # Verify uvicorn.run was called with correct parameters
        mock_uvicorn.assert_called_once_with(
            health_api.app,
            host="0.0.0.0",
            port=8082,
            log_level="info"
        )
    
    @patch('uvicorn.run')
    def test_health_api_keyboard_interrupt(self, mock_uvicorn, mock_db_service):
        """Test health API handles keyboard interrupt."""
        health_api = HealthAPI(db_service=mock_db_service)
        
        # Mock uvicorn to raise KeyboardInterrupt
        mock_uvicorn.side_effect = KeyboardInterrupt()
        
        # Should not raise exception
        health_api.run()
    
    def test_health_api_stop(self, mock_db_service):
        """Test health API stop method."""
        health_api = HealthAPI(db_service=mock_db_service)
        
        # Should not raise exception
        health_api.stop()
    
    @pytest.mark.asyncio
    async def test_check_database_health(self, mock_db_service):
        """Test internal database health check."""
        health_api = HealthAPI(db_service=mock_db_service)
        
        # Test healthy database
        result = await health_api._check_database_health()
        assert result is True
        
        # Test unhealthy database
        mock_db_service.execute_query.side_effect = Exception("DB Error")
        result = await health_api._check_database_health()
        assert result is False
        
        # Test no database service
        health_api.db_service = None
        result = await health_api._check_database_health()
        assert result is False