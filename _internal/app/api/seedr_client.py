"""
Seedr API client for handling torrents and downloads.
"""
import os
from typing import Optional, Dict, Any, List
import requests
from ..auth.oauth_handler import OAuthHandler
from ..config import SeedrConfig
import json
import time

class SeedrClient:
    def __init__(self, config: SeedrConfig):
        self.auth = OAuthHandler(config)
        self.api_base_url = config.api_base_url
        self.verbose_logging = False  # Default to false to reduce terminal clutter

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token."""
        token = self.auth.get_access_token()
        if not token:
            raise ValueError("Not authenticated with Seedr")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get user account information.
        
        Endpoint: GET /user
        """
        url = f"{self.api_base_url}/api/v0.1/p/user"
        
        try:
            response = requests.get(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            self._log_get_response(url, response, self.verbose_logging)
            
            response.raise_for_status()
            return response.json() or {}
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting account info: {e}")
            return {}
            
    def get_tasks(self) -> List[Dict[str, Any]]:
        """
        Get list of all torrent tasks.
        
        Endpoint: GET /tasks
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks"
        
        try:
            response = requests.get(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            self._log_get_response(url, response, self.verbose_logging)
            
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting tasks: {e}")
            return []
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get details for a specific task.
        
        Endpoint: GET /tasks/{id}
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks/{task_id}"
        
        try:
            response = requests.get(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            self._log_get_response(url, response, self.verbose_logging)
            
            if self.verbose_logging:
                self._debug_print_response("GET", url, response, self.verbose_logging)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting task {task_id}: {e}")
            return {"status": "unknown", "message": f"Error: {str(e)}"}
    
    def get_task_contents(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get contents of a torrent task.
        
        Endpoint: GET /tasks/{id}/contents
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks/{task_id}/contents"
        
        try:
            response = requests.get(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            self._log_get_response(url, response, self.verbose_logging)
            
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting task contents for {task_id}: {e}")
            return []
    
    def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """
        Get progress URL for a task.
        
        Endpoint: GET /tasks/{id}/progress
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks/{task_id}/progress"
        
        try:
            response = requests.get(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            self._log_get_response(url, response, self.verbose_logging)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting task progress for {task_id}: {e}")
            return {"status": "unknown", "message": f"Error: {str(e)}"}
    
    def pause_task(self, task_id: str) -> bool:
        """
        Pause an active task.
        
        Endpoint: POST /tasks/{id}/pause
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks/{task_id}/pause"
        
        try:
            response = requests.post(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            if self.verbose_logging:
                self._debug_print_response("POST", url, response, self.verbose_logging)
            
            response.raise_for_status()
            return True
        except Exception as e:
            if self.verbose_logging:
                print(f"Error pausing task {task_id}: {e}")
            return False
    
    def resume_task(self, task_id: str) -> bool:
        """
        Resume a paused task.
        
        Endpoint: POST /tasks/{id}/resume
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks/{task_id}/resume"
        
        try:
            response = requests.post(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            if self.verbose_logging:
                self._debug_print_response("POST", url, response, self.verbose_logging)
            
            response.raise_for_status()
            return True
        except Exception as e:
            if self.verbose_logging:
                print(f"Error resuming task {task_id}: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a torrent task.
        
        Endpoint: DELETE /tasks/{id}
        Note: This does not delete downloaded files, only the task.
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks/{task_id}"
        
        try:
            response = requests.delete(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            if self.verbose_logging:
                self._debug_print_response("DELETE", url, response, self.verbose_logging)
            
            response.raise_for_status()
            return True
        except Exception as e:
            if self.verbose_logging:
                print(f"Error deleting task {task_id}: {e}")
            return False
    
    def add_torrent(self, torrent_url: str) -> Dict[str, Any]:
        """
        Add a torrent to Seedr.
        
        Endpoint: POST /tasks
        """
        url = f"{self.api_base_url}/api/v0.1/p/tasks"
        
        try:
            # Check if this is a magnet link
            is_magnet = torrent_url.startswith('magnet:')
            
            if is_magnet:
                # If it's a magnet link, send directly
                payload = {
                    "magnet": torrent_url
                }
            else:
                # Try to get magnet from torrent link if it's a YTS URL 
                if "yts" in torrent_url.lower():
                    try:
                        magnet = self._extract_magnet_from_torrent(torrent_url)
                        if magnet:
                            payload = {"magnet": magnet}
                        else:
                            payload = {"url": torrent_url}
                    except:
                        payload = {"url": torrent_url}
                else:
                    # Otherwise send as URL
                    payload = {
                        "url": torrent_url
                    }
            
            response = requests.post(
                url,
                headers={
                    **self._get_headers(),
                    'Accept': 'application/json'
                },
                json=payload,
                timeout=30
            )
            
            if self.verbose_logging:
                self._debug_print_response("POST", url, response, self.verbose_logging)
                
            # API might return 4XX status code but still have useful info
            try:
                return response.json()
            except:
                response.raise_for_status()
                return {"success": True}
            
        except Exception as e:
            if self.verbose_logging:
                print(f"Error adding torrent: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    def _log_get_response(self, url: str, response, verbose=False) -> None:
        """Log API response details for debugging."""
        if not verbose:
            return
            
        try:
            status_code = response.status_code
            content_length = len(response.content)
            content_type = response.headers.get('content-type', 'unknown')
            
            print(f"GET {url}: Status={status_code}, Length={content_length}, Type={content_type}")
            
            # If it's JSON and not too large, print it
            if content_type.startswith('application/json') and content_length < 1000:
                print(f"Response: {response.json()}")
        except:
            pass
    
    def get_torrent_status(self, torrent_id: str) -> Dict[str, Any]:
        """
        Check the status of a torrent download.
        This is a fallback for the deprecated API - use get_task() instead when possible.
        """
        try:
            # First try the Tasks API
            task = self.get_task(torrent_id)
            if task.get("status") != "unknown":
                return {
                    "status": task.get("status"),
                    "progress": task.get("progress", 0),
                    "message": task.get("message", ""),
                    "task_id": torrent_id
                }
            
            # If tasks API fails, check for a folder with matching torrent_hash
            # This could mean the download completed and was moved to a folder
            folders = self.get_folder_contents("0")  # Root folder
            for folder in folders:
                if folder.get("torrent_hash", "").lower() == torrent_id.lower():
                    return {
                        "status": "completed",
                        "progress": 100,
                        "message": "Download completed and moved to folder",
                        "folder_id": folder.get("id")
                    }
            
            # If we can't find any trace of it, return unknown
            return {
                "status": "unknown",
                "message": "Torrent not found"
            }
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting torrent status: {e}")
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }
    
    def get_folder_contents(self, folder_id: str = "0") -> List[Dict[str, Any]]:
        """
        Get contents of a folder.
        folder_id "0" is the root folder.
        """
        url = f"{self.api_base_url}/api/v0.1/p/folder/{folder_id}"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Return all folders and files
            result = []
            
            # Add folders
            if "folders" in data:
                for folder in data["folders"]:
                    folder["type"] = "folder"
                    result.append(folder)
            
            # Add files
            if "files" in data:
                for file in data["files"]:
                    file["type"] = "file"
                    result.append(file)
                    
            return result
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting folder contents: {e}")
            return []

    def download_file(self, file_id: str, save_path: str) -> bool:
        """
        Download a file from Seedr to the local machine.
        
        Args:
            file_id: ID of the file to download
            save_path: Path where the file should be saved
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the download URL
            download_url = self.get_download_url(file_id)
            if not download_url:
                return False
                
            # Create directory if needed
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            
            # Download the file
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            return True
        except Exception as e:
            if self.verbose_logging:
                print(f"Error downloading file: {e}")
            return False
    
    def delete_torrent(self, torrent_id: str) -> bool:
        """
        Delete a torrent from Seedr.
        This is an alias for delete_task for backward compatibility.
        """
        return self.delete_task(torrent_id)
    
    def get_download_url(self, file_id: str) -> Optional[str]:
        """
        Get a download URL for a file.
        
        Args:
            file_id: ID of the file to download
        
        Returns:
            Optional[str]: Download URL or None if failed
        """
        url = f"{self.api_base_url}/api/v0.1/p/file/{file_id}"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Check if the response contains a download URL
            if "url" in data:
                return data["url"]
            else:
                if self.verbose_logging:
                    print(f"No download URL in response: {data}")
                return None
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting download URL: {e}")
            return None

    def _extract_magnet_from_torrent(self, torrent_url: str) -> str:
        """
        Try to extract a magnet link from a YTS torrent page.
        
        This is a workaround for Seedr issues with certain torrent files.
        """
        try:
            # Only attempt for YTS URLs
            if "yts" not in torrent_url.lower():
                return ""
                
            # We're going to fetch the YTS page and extract the magnet link
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(torrent_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Look for the magnet link in the HTML
            html = response.text
            
            # Regex pattern for magnet links
            magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]*'
            
            import re
            matches = re.findall(magnet_pattern, html)
            
            if matches:
                # Return the first match
                return matches[0]
                
            return ""
        except Exception as e:
            if self.verbose_logging:
                print(f"Error extracting magnet link: {e}")
            return ""
    
    def init_archive(self, folder_id: str) -> Optional[str]:
        """
        Initialize an archive for a folder.
        
        Args:
            folder_id: ID of the folder to archive
        
        Returns:
            Optional[str]: Archive unique ID or None if failed
        """
        url = f"{self.api_base_url}/api/v0.1/p/folder/{folder_id}/archive"
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if self.verbose_logging:
                self._debug_print_response("POST", url, response, self.verbose_logging)
            
            response.raise_for_status()
            data = response.json()
            
            # Check if the response contains the archive unique ID
            if "uniq" in data:
                return data["uniq"]
            else:
                if self.verbose_logging:
                    print(f"No uniq in response: {data}")
                return None
        except Exception as e:
            if self.verbose_logging:
                print(f"Error initializing archive: {e}")
            return None
    
    def get_archive_url(self, uniq: str) -> Optional[str]:
        """
        Get the download URL for an archive.
        
        Args:
            uniq: Archive unique ID from init_archive
        
        Returns:
            Optional[str]: Archive download URL or None if failed
        """
        url = f"{self.api_base_url}/api/v0.1/p/folder/archive/{uniq}"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if self.verbose_logging:
                self._log_get_response(url, response, self.verbose_logging)
            
            response.raise_for_status()
            data = response.json()
            
            # Check if the archive is ready
            if "status" in data and data["status"] == "ready" and "url" in data:
                return data["url"]
            elif "status" in data and data["status"] == "generating":
                # Archive is still being generated, wait and retry
                if self.verbose_logging:
                    print(f"Archive still generating, progress: {data.get('progress', 'unknown')}")
                
                # Wait a bit and try again (up to 3 times)
                for _ in range(3):
                    time.sleep(5)
                    
                    response = requests.get(
                        url,
                        headers=self._get_headers(),
                        timeout=10
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if "status" in data and data["status"] == "ready" and "url" in data:
                        return data["url"]
                
                # If we get here, the archive is still not ready
                if self.verbose_logging:
                    print(f"Archive still not ready after waiting: {data}")
                return None
            else:
                if self.verbose_logging:
                    print(f"Archive not ready or no URL in response: {data}")
                return None
        except Exception as e:
            if self.verbose_logging:
                print(f"Error getting archive URL: {e}")
            return None
    
    def download_folder_as_archive(self, folder_id: str, save_path: str) -> bool:
        """
        Download a folder as an archive.
        
        Args:
            folder_id: ID of the folder to download
            save_path: Path where the archive should be saved
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize the archive
            uniq = self.init_archive(folder_id)
            if not uniq:
                return False
                
            # Get the download URL for the archive
            download_url = self.get_archive_url(uniq)
            if not download_url:
                return False
                
            # Create directory if needed
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            
            # Download the file
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            return True
        except Exception as e:
            if self.verbose_logging:
                print(f"Error downloading folder as archive: {e}")
            return False
    
    def _debug_print_response(self, method: str, url: str, response, verbose=False) -> None:
        """Print response details for debugging."""
        if not verbose:
            return
            
        try:
            status_code = response.status_code
            content_length = len(response.content)
            content_type = response.headers.get('content-type', 'unknown')
            
            print(f"{method} {url}: Status={status_code}, Length={content_length}, Type={content_type}")
            
            # If it's JSON and not too large, print it
            if content_type.startswith('application/json') and content_length < 1000:
                try:
                    print(f"Response: {response.json()}")
                except:
                    print(f"Response is not valid JSON: {response.text[:100]}...")
        except:
            pass 