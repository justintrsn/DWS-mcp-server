"""Enhanced Database configuration loader with multi-profile support."""

import os
import yaml
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv


class DatabaseProfile:
    """Represents a single database profile configuration."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.uri = config.get('uri', '')
        self.uri_local = config.get('uri_local', '')
        self.description = config.get('description', '')
        self.environment = config.get('environment', 'development')
        self.features = config.get('features', [])
        self.tags = config.get('tags', [])
        self.connection_options = config.get('connection_options', {})

        # Parse URI if provided
        if self.uri:
            self._parse_uri()

    def _parse_uri(self):
        """Parse PostgreSQL URI into components."""
        # Use local URI if we're not in Docker and it exists
        uri_to_parse = self.uri
        if self.uri_local and not os.getenv('DOCKER_ENV'):
            uri_to_parse = self.uri_local

        parsed = urlparse(uri_to_parse)
        self._host = parsed.hostname or 'localhost'
        self._port = parsed.port or 5432
        self._database = parsed.path.lstrip('/') if parsed.path else 'postgres'
        self._user = parsed.username or 'postgres'
        self._password = parsed.password or ''

    @property
    def host(self) -> str:
        return getattr(self, '_host', 'localhost')

    @property
    def port(self) -> int:
        return getattr(self, '_port', 5432)

    @property
    def database(self) -> str:
        return getattr(self, '_database', 'postgres')

    @property
    def user(self) -> str:
        return getattr(self, '_user', 'postgres')

    @property
    def password(self) -> str:
        return getattr(self, '_password', '')

    @property
    def connect_timeout(self) -> int:
        return self.connection_options.get('connect_timeout', int(os.getenv('DB_CONNECT_TIMEOUT', '10')))

    @property
    def query_timeout(self) -> int:
        return self.connection_options.get('query_timeout', int(os.getenv('DB_QUERY_TIMEOUT', '30')))

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for psycopg2."""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'connect_timeout': self.connect_timeout
        }


class DatabaseConfig:
    """Enhanced database configuration with multi-profile support."""
    
    def __init__(self, profile_name: Optional[str] = None):
        load_dotenv()

        self.profiles: Dict[str, DatabaseProfile] = {}
        self.current_profile: Optional[DatabaseProfile] = None

        # Load configuration in priority order
        self._load_configuration(profile_name)

        # Validate the current configuration
        if self.current_profile:
            self.validate()

    def _load_configuration(self, profile_name: Optional[str] = None):
        """Load database configuration from various sources."""

        # Priority 1: DATABASE_URI environment variable
        if os.getenv('DATABASE_URI'):
            self._load_from_uri()
            return

        # Priority 2: Database profile from YAML config
        if profile_name or os.getenv('DATABASE_PROFILE'):
            profile = profile_name or os.getenv('DATABASE_PROFILE')
            if self._load_from_profile(profile):
                return

        # Priority 3: YAML config default profile
        if self._load_from_yaml_default():
            return

        # Priority 4: Individual environment variables (legacy)
        self._load_from_env()

    def _load_from_uri(self):
        """Load configuration from DATABASE_URI environment variable."""
        uri = os.getenv('DATABASE_URI')
        if not uri:
            return

        # Create a temporary profile from URI
        profile_config = {
            'name': 'uri_override',
            'description': 'Configuration from DATABASE_URI environment variable',
            'uri': uri,
            'enabled': True,
            'environment': 'custom'
        }

        profile = DatabaseProfile('uri_override', profile_config)
        self.profiles['uri_override'] = profile
        self.current_profile = profile

    def _load_from_profile(self, profile_name: str) -> bool:
        """Load configuration from a specific YAML profile."""
        if self._load_yaml_config():
            if profile_name in self.profiles:
                profile = self.profiles[profile_name]
                if profile.enabled:
                    self.current_profile = profile
                    return True
                else:
                    raise ValueError(f"Database profile '{profile_name}' is disabled")
            else:
                raise ValueError(f"Database profile '{profile_name}' not found in configuration")
        return False

    def _load_from_yaml_default(self) -> bool:
        """Load default profile from YAML configuration."""
        if self._load_yaml_config():
            # Try to load default profile from YAML
            default_profile = getattr(self, '_yaml_config', {}).get('default_profile', 'anime')
            if default_profile in self.profiles:
                profile = self.profiles[default_profile]
                if profile.enabled:
                    self.current_profile = profile
                    return True
        return False

    def _load_yaml_config(self) -> bool:
        """Load database profiles from YAML configuration file."""
        if hasattr(self, '_yaml_loaded'):
            return self._yaml_loaded

        config_path = os.getenv('DATABASES_CONFIG', '/app/config/databases.yaml')

        # Try multiple possible locations
        possible_paths = [
            config_path,
            'config/databases.yaml',
            '/app/config/databases.yaml',
            Path(__file__).parent.parent.parent / 'config' / 'databases.yaml'
        ]

        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    config_data = yaml.safe_load(f)

                self._yaml_config = config_data

                # Load all database profiles
                databases = config_data.get('databases', {})
                for profile_name, profile_config in databases.items():
                    self.profiles[profile_name] = DatabaseProfile(profile_name, profile_config)

                self._yaml_loaded = True
                return True

            except (FileNotFoundError, yaml.YAMLError) as e:
                continue

        self._yaml_loaded = False
        return False

    def _load_from_env(self):
        """Load configuration from individual environment variables (legacy mode)."""
        # Create a profile from environment variables
        profile_config = {
            'name': 'env_legacy',
            'description': 'Configuration from individual environment variables',
            'enabled': True,
            'environment': 'legacy'
        }

        # Use a DatabaseProfile that will get values from properties below
        profile = DatabaseProfile('env_legacy', profile_config)

        # Override the parsed values with environment variables
        profile._host = os.getenv('DB_HOST', 'localhost')
        profile._port = int(os.getenv('DB_PORT', '5432'))
        profile._database = os.getenv('DB_DATABASE', 'footfall')
        profile._user = os.getenv('DB_USER', 'dbadmin')
        profile._password = os.getenv('DB_PASSWORD', '')

        self.profiles['env_legacy'] = profile
        self.current_profile = profile

        # Validate numeric config for legacy mode
        self._validate_numeric_config()
    
    @property
    def host(self) -> str:
        return self.current_profile.host if self.current_profile else 'localhost'

    @property
    def port(self) -> int:
        return self.current_profile.port if self.current_profile else 5432

    @property
    def database(self) -> str:
        return self.current_profile.database if self.current_profile else 'postgres'

    @property
    def user(self) -> str:
        return self.current_profile.user if self.current_profile else 'postgres'

    @property
    def password(self) -> str:
        return self.current_profile.password if self.current_profile else ''

    @property
    def connect_timeout(self) -> int:
        return self.current_profile.connect_timeout if self.current_profile else 10

    @property
    def query_timeout(self) -> int:
        return self.current_profile.query_timeout if self.current_profile else 30

    def switch_profile(self, profile_name: str) -> bool:
        """Switch to a different database profile."""
        if profile_name not in self.profiles:
            raise ValueError(f"Database profile '{profile_name}' not found")

        profile = self.profiles[profile_name]
        if not profile.enabled:
            raise ValueError(f"Database profile '{profile_name}' is disabled")

        self.current_profile = profile
        return True

    def get_profile_info(self) -> Dict[str, Any]:
        """Get information about the current profile."""
        if not self.current_profile:
            return {'profile': None, 'status': 'not_configured'}

        return {
            'profile': self.current_profile.name,
            'description': self.current_profile.description,
            'environment': self.current_profile.environment,
            'features': self.current_profile.features,
            'tags': self.current_profile.tags,
            'database': self.current_profile.database,
            'host': self.current_profile.host,
            'port': self.current_profile.port,
            'enabled': self.current_profile.enabled
        }

    def list_profiles(self) -> Dict[str, Dict[str, Any]]:
        """List all available database profiles."""
        return {
            name: {
                'name': profile.config.get('name', name),
                'description': profile.description,
                'environment': profile.environment,
                'enabled': profile.enabled,
                'features': profile.features,
                'tags': profile.tags,
                'current': profile == self.current_profile
            }
            for name, profile in self.profiles.items()
        }
    
    def validate(self):
        """Validate required configuration."""
        if not self.current_profile:
            raise ValueError("No database profile configured")

        if not self.password:
            raise ValueError(f"Password is required for database profile '{self.current_profile.name}'")
        if not self.host:
            raise ValueError(f"Host is required for database profile '{self.current_profile.name}'")
        if not self.database:
            raise ValueError(f"Database name is required for database profile '{self.current_profile.name}'")
        if not self.user:
            raise ValueError(f"User is required for database profile '{self.current_profile.name}'")

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
        """Convert current profile to dictionary for psycopg2."""
        if not self.current_profile:
            raise ValueError("No current database profile configured")

        return self.current_profile.to_dict()