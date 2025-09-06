"""
Configuration management for Sonarr-Seedr integration.
"""
import os
import json
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables (optional since client ID is hardcoded)
load_dotenv()

class SeedrConfig(BaseModel):
    """Seedr configuration settings."""
    client_id: str = Field(
        ...,
        description="Seedr OAuth Client ID"
    )
    api_base_url: str = Field(
        default="https://v2.seedr.cc",
        description="Seedr API base URL"
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure API base URL doesn't have trailing slash
        if self.api_base_url.endswith('/'):
            self.api_base_url = self.api_base_url.rstrip('/')

class SonarrConfig(BaseModel):
    """Sonarr configuration settings."""
    host: str = Field(
        default="http://localhost:8989",
        description="Sonarr host address"
    )
    api_key: Optional[str] = Field(
        default="",
        description="Sonarr API key"
    )

class DownloadConfig(BaseModel):
    """Download configuration settings."""
    download_dir: Optional[str] = Field(
        default="",
        description="Directory for downloaded files"
    )
    root_folder: Optional[str] = Field(
        default="",
        description="Sonarr root folder for media"
    )

class Config(BaseModel):
    """Main configuration model."""
    seedr: SeedrConfig
    sonarr: SonarrConfig
    download: DownloadConfig

    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables."""
        return cls(
            seedr=SeedrConfig(
                client_id=os.getenv("SEEDR_CLIENT_ID", "EKp43IJEBXiGjaRg6cd7F17R3z3zv6VL"),
                api_base_url=os.getenv("SEEDR_API_BASE_URL", "https://v2.seedr.cc")
            ),
            sonarr=SonarrConfig(
                host=os.getenv("SONARR_HOST", "http://localhost:8989"),
                api_key=os.getenv("SONARR_API_KEY", "")
            ),
            download=DownloadConfig(
                download_dir=os.getenv("DOWNLOAD_DIR", ""),
                root_folder=os.getenv("ROOT_FOLDER", "")
            )
        )

    @classmethod
    def from_file(cls, file_path: str) -> 'Config':
        """Load configuration from a JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls(**data)

    def save_to_file(self, file_path: str) -> None:
        """Save configuration to a JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.dict(), f, indent=2)

    def validate(self, strict: bool = True) -> None:
        """Validate configuration values.
        
        Args:
            strict: If False, only warn about missing required values instead of raising errors
        """
        # SEEDR_CLIENT_ID is now hardcoded, so no validation needed
        
        # Optional directory creation if paths are provided
        if self.download.download_dir:
            os.makedirs(self.download.download_dir, exist_ok=True)
        if self.download.root_folder:
            os.makedirs(self.download.root_folder, exist_ok=True) 