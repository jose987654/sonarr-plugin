"""
Sonarr API client for handling series and episodes.
"""
import os
from typing import Optional, Dict, Any, List
import requests
from ..config import SonarrConfig

class SonarrClient:
    def __init__(self, config: SonarrConfig):
        self.config = config
        self.host = config.host.rstrip('/')
        self.api_key = config.api_key
        self.verbose_logging = False
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with API key."""
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
    def get_series(self) -> List[Dict[str, Any]]:
        """Get all series from Sonarr."""
        url = f"{self.host}/api/v3/series"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting series: {e}")
            return []
            
    def get_series_by_id(self, series_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific series by ID."""
        url = f"{self.host}/api/v3/series/{series_id}"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting series {series_id}: {e}")
            return None
            
    def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get all root folders from Sonarr."""
        url = f"{self.host}/api/v3/rootfolder"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting root folders: {e}")
            return []
            
    def get_missing_episodes(self) -> List[Dict[str, Any]]:
        """Get all missing episodes."""
        url = f"{self.host}/api/v3/wanted/missing"
        
        try:
            # Get first page
            response = requests.get(
                url,
                headers=self._get_headers(),
                params={
                    "pageSize": 100,
                    "page": 1
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Get all pages
            total_pages = data.get("totalPages", 1)
            records = data.get("records", [])
            
            for page in range(2, total_pages + 1):
                response = requests.get(
                    url,
                    headers=self._get_headers(),
                    params={
                        "pageSize": 100,
                        "page": page
                    },
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                records.extend(data.get("records", []))
                
            return records
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting missing episodes: {e}")
            return []
    
    def command_download_scan(self, path: str) -> Dict[str, Any]:
        """
        Trigger a download scan command in Sonarr.
        This tells Sonarr to look for completed downloads in the provided path.
        """
        url = f"{self.host}/api/v3/command"
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json={
                    "name": "DownloadedEpisodesScan",
                    "path": path
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if self.verbose_logging:
                print(f"Error triggering download scan: {e}")
            return {"status": "error", "message": str(e)} 