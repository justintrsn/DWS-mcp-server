import os
from typing import Dict, Any
import json
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        
        # Model configuration
        self.model_name = os.getenv("MAAS_MODEL_NAME")
        self.api_url = os.getenv("MAAS_API_URL", "")
        if self.api_url.endswith("/chat/completions"):
            self.api_url = self.api_url[:-16]  # Remove "/chat/completions"
            
        # SSL configuration
        self.ssl_verify = os.getenv("MAAS_SSL_VERIFY", "true").lower() == "true"
        
        # MCP configuration
        self.mcp_servers_config = self._parse_mcp_servers_config()
        
        # Sampling configuration
        self.sampling_config = self._parse_sampling_config()
        
        # User prompt
        self.user_prompt = os.getenv("MAAS_USER_PROMPT", "")
    
    def _parse_mcp_servers_config(self) -> Dict[str, Any]:
        """Parse MCP servers configuration from environment variable."""
        config_str = os.getenv("MAAS_MCP_SERVERS")
        if not config_str:
            return {}
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            return {}
    
    def _parse_sampling_config(self) -> Dict[str, Any]:
        """Parse sampling configuration from environment variable."""
        config_str = os.getenv("MAAS_SAMPLING_CONFIG", "{}")
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            return {}

# Create a global config instance
config = Config() 