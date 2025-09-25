"""Database profile management and validation models."""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator
import os
from pathlib import Path


class DatabaseSwitchRequest(BaseModel):
    """Request model for switching database profiles."""

    profile: str = Field(..., description="Target database profile name")
    validate_connection: bool = Field(default=True, description="Test connection before switching")
    force: bool = Field(default=False, description="Force switch even if current profile is working")

    @validator('profile')
    def profile_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Profile name cannot be empty')
        return v.strip()


class DatabaseConnectionTest(BaseModel):
    """Request model for testing database connections."""

    profile: str = Field(..., description="Database profile name to test")
    timeout: int = Field(default=10, description="Connection timeout in seconds")

    @validator('profile')
    def profile_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Profile name cannot be empty')
        return v.strip()

    @validator('timeout')
    def timeout_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Timeout must be positive')
        return min(v, 60)  # Cap at 60 seconds


class DatabaseProfileInfo(BaseModel):
    """Database profile information response."""

    name: str
    description: str
    environment: str
    enabled: bool
    features: List[str]
    tags: List[str]
    database: str
    host: str
    port: int
    current: bool = False


class DatabaseSwitchResponse(BaseModel):
    """Response model for database switching operations."""

    success: bool
    message: str
    previous_profile: Optional[str] = None
    current_profile: Optional[str] = None
    switched_at: Optional[str] = None
    validation_performed: bool = False


class DatabaseConnectionTestResponse(BaseModel):
    """Response model for database connection testing."""

    profile: str
    success: bool
    message: str
    connection_time_ms: Optional[float] = None
    database_info: Optional[Dict[str, Any]] = None
    tested_at: Optional[str] = None


class DatabaseListResponse(BaseModel):
    """Response model for listing database profiles."""

    total_profiles: int
    enabled_profiles: int
    current_profile: Optional[str] = None
    profiles: Dict[str, DatabaseProfileInfo]


class DatabaseConfigManager:
    """Manager for database profile operations."""

    def __init__(self):
        self.config = None
        self._db_service = None

    def set_config(self, config, db_service=None):
        """Set the database configuration and service instances."""
        self.config = config
        self._db_service = db_service

    def list_profiles(self) -> DatabaseListResponse:
        """List all available database profiles."""
        if not self.config:
            return DatabaseListResponse(
                total_profiles=0,
                enabled_profiles=0,
                profiles={}
            )

        profiles_dict = {}
        enabled_count = 0

        for name, profile_data in self.config.list_profiles().items():
            profile_info = DatabaseProfileInfo(
                name=profile_data['name'],
                description=profile_data['description'],
                environment=profile_data['environment'],
                enabled=profile_data['enabled'],
                features=profile_data['features'],
                tags=profile_data['tags'],
                database=profile_data.get('database', 'unknown'),
                host=profile_data.get('host', 'unknown'),
                port=profile_data.get('port', 0),
                current=profile_data['current']
            )
            profiles_dict[name] = profile_info

            if profile_info.enabled:
                enabled_count += 1

        current_profile = None
        if self.config.current_profile:
            current_profile = self.config.current_profile.name

        return DatabaseListResponse(
            total_profiles=len(profiles_dict),
            enabled_profiles=enabled_count,
            current_profile=current_profile,
            profiles=profiles_dict
        )

    def get_current_profile_info(self) -> Optional[DatabaseProfileInfo]:
        """Get information about the current database profile."""
        if not self.config or not self.config.current_profile:
            return None

        profile_info = self.config.get_profile_info()
        return DatabaseProfileInfo(
            name=profile_info['profile'],
            description=profile_info['description'],
            environment=profile_info['environment'],
            enabled=profile_info.get('enabled', True),
            features=profile_info.get('features', []),
            tags=profile_info.get('tags', []),
            database=profile_info['database'],
            host=profile_info['host'],
            port=profile_info['port'],
            current=True
        )

    def validate_profile_exists(self, profile_name: str) -> bool:
        """Check if a profile exists and is enabled."""
        if not self.config:
            return False

        return (profile_name in self.config.profiles and
                self.config.profiles[profile_name].enabled)

    def can_switch_to_profile(self, profile_name: str) -> tuple[bool, str]:
        """Check if switching to a profile is allowed."""
        if not self.config:
            return False, "No database configuration available"

        if profile_name not in self.config.profiles:
            return False, f"Profile '{profile_name}' does not exist"

        profile = self.config.profiles[profile_name]
        if not profile.enabled:
            return False, f"Profile '{profile_name}' is disabled"

        return True, "Profile is available for switching"


# Global instance for use across the application
database_manager = DatabaseConfigManager()