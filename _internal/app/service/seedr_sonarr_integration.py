"""
Integration service for Seedr and Sonarr.
"""
import os
import json
import re
import time
from typing import Dict, Any, Optional, List
from ..api.seedr_client import SeedrClient
from ..api.sonarr_client import SonarrClient
from ..config import Config

class SeedrSonarrIntegration:
    def __init__(self, config: Optional[Config] = None, strict_validation: bool = True):
        self.config = config or Config.from_env()
        self.config.validate(strict=strict_validation)
        self.seedr = SeedrClient(self.config.seedr)
        self.sonarr = SonarrClient(self.config.sonarr)
        # Set up download directory and mapping file
        if self.config.download.download_dir:
            self.mapping_file = os.path.join(self.config.download.download_dir, "download_mappings.json")
            # Ensure download directory exists
            os.makedirs(self.config.download.download_dir, exist_ok=True)
        else:
            # Use a default location if not configured
            default_dir = os.path.join(os.getcwd(), "downloads")
            self.mapping_file = os.path.join(default_dir, "download_mappings.json")
            os.makedirs(default_dir, exist_ok=True)

    def add_download(self, title: str, download_url: str, series_id: Optional[int] = None) -> Dict[str, Any]:
        """Add a download to Seedr and return the response."""
        try:
            # Normalize YTS URLs to match the working example format
            if "yts" in download_url.lower() and "/torrent/download/" in download_url.lower():
                # Extract the hash from the URL if possible
                hash_match = re.search(r'/download/([A-F0-9]+)', download_url, re.IGNORECASE)
                if hash_match:
                    torrent_hash = hash_match.group(1)
                    # Format it exactly like the working example
                    download_url = f"https://yts.mx/torrent/download/{torrent_hash}"

            # Add torrent to Seedr using the Tasks API
            result = self.seedr.add_torrent(download_url)
            
            # The API might return a 413 status with a wishlist item (not enough space)
            if result.get("reason_phrase") == "not_enough_space_added_to_wishlist" and result.get("wt"):
                wishlist_item = result.get("wt", {})
                task_id = wishlist_item.get("id")
                if task_id:
                    self._store_download_mapping(title, task_id, series_id)
                    return {
                        "success": True,
                        "message": f"Added {title} to Seedr wishlist (not enough space)",
                        "download_id": task_id
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to get wishlist ID from Seedr response"
                    }
            
            # For a regular successful addition - check all possible ID fields
            task_id = result.get("task_id") or result.get("id") or result.get("user_torrent_id")

            if not task_id:
                # If we have success=true but no ID, use the torrent_hash as ID
                if result.get("success") and result.get("torrent_hash"):
                    task_id = result.get("torrent_hash")
                else:
                    return {
                        "success": False,
                            "message": "Failed to get task ID from Seedr response",
                            "response": result
                    }
            
            # Store mapping of Sonarr title to Seedr task ID
            self._store_download_mapping(title, task_id, series_id)
            
            return {
                "success": True,
                "message": f"Added {title} to Seedr",
                "download_id": task_id
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to add download: {str(e)}"
            }

    def _store_download_mapping(self, title: str, torrent_id: str, series_id: Optional[int] = None) -> None:
        """Store mapping between Sonarr title and Seedr torrent ID."""
        try:
            mappings = {}
            if os.path.exists(self.mapping_file):
                with open(self.mapping_file, 'r') as f:
                    mappings = json.load(f)
            
            mappings[title] = {
                "torrent_id": torrent_id,
                "series_id": series_id,
                "added_at": time.time()
            }
            
            with open(self.mapping_file, 'w') as f:
                json.dump(mappings, f)
        except Exception as e:
            print(f"Error storing download mapping: {e}")

    def check_download_status(self, title: str) -> Dict[str, Any]:
        """Check the status of a download."""
        try:
            if not os.path.exists(self.mapping_file):
                return {"status": "unknown", "message": "No download mapping found"}

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            if title not in mappings:
                return {"status": "unknown", "message": "Download not found"}

            torrent_id = mappings[title]["torrent_id"]

            # Try to get status using the Tasks API
            try:
                status = self.seedr.get_task(torrent_id)
                if status.get("status") != "unknown":
                    # Also try to get progress information
                    try:
                        progress_info = self.seedr.get_task_progress(torrent_id)
                        if progress_info and isinstance(progress_info, dict):
                            # Merge progress info with status
                            status.update(progress_info)
                    except:
                        pass

                return {
                    "status": status.get("status", "unknown"),
                    "progress": status.get("progress", 0),
                    "message": status.get("message", "")
                }
            except Exception as e:
                if self.seedr.verbose_logging:
                    print(f"Error getting task status with tasks API: {e}")
            
            # If the tasks API fails, fall back to the old methods
            try:
                status = self.seedr.get_torrent_status(torrent_id)
                
                # If successful, return the status
                return {
                    "status": status.get("status", "unknown"),
                    "progress": status.get("progress", 0),
                    "message": status.get("message", "")
                }
            except Exception as e:
                # If the ID is a hash, the torrent might be completed and moved to a folder
                if len(torrent_id) == 40:  # SHA-1 hash length
                    # Try to find the folder by listing root folders
                    try:
                        folders = self.seedr.get_folder_contents("0")  # Root folder
                        for folder in folders:
                            if folder.get("torrent_hash") == torrent_id.lower():
                                return {
                                    "status": "completed",
                                    "progress": 100,
                                    "message": "Torrent completed and moved to folder",
                                    "folder_id": folder.get("id")
                                }
                    except:
                        pass
                
                # If we can't find it, return error
                return {"status": "error", "message": str(e)}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_downloaded_files(self, title: str) -> Dict[str, Any]:
        """Get downloaded files for a title."""
        try:
            if not os.path.exists(self.mapping_file):
                return {"success": False, "message": "No download mapping found"}

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            if title not in mappings:
                return {"success": False, "message": "Download not found"}

            torrent_id = mappings[title]["torrent_id"]
            
            # First try to get contents using the Tasks API
            try:
                task_status = self.seedr.get_task(torrent_id)
                
                # If the task is completed, get its contents
                if task_status.get("status") == "completed":
                    contents = self.seedr.get_task_contents(torrent_id)
                    if contents:
                        return {
                            "success": True,
                            "files": contents
                        }
            except Exception as e:
                if self.seedr.verbose_logging:
                    print(f"Error getting task contents with tasks API: {e}")
            
            # If the tasks API fails, check if the torrent has been moved to a folder
            try:
                status = self.seedr.get_torrent_status(torrent_id)
                
                # If the torrent has been moved to a folder, get the folder contents
                if status.get("status") == "completed" and status.get("folder_id"):
                    folder_id = status.get("folder_id")
                    contents = self.seedr.get_folder_contents(folder_id)
                    
                    if contents:
                        return {
                            "success": True,
                            "files": contents
                        }
            except Exception as e:
                if self.seedr.verbose_logging:
                    print(f"Error getting folder contents: {e}")
            
            return {"success": False, "message": "No files found or download not completed"}
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def download_completed_files(self, title: str, save_path: Optional[str] = None) -> Dict[str, Any]:
        """Download completed files for a title."""
        try:
            if not save_path:
                save_path = self.config.download.download_dir
            
            # Get downloaded files
            files_result = self.get_downloaded_files(title)
            
            if not files_result.get("success"):
                return files_result
            
            files = files_result.get("files", [])
            
            if not files:
                return {"success": False, "message": "No files to download"}
            
            # Create the save directory if it doesn't exist
            os.makedirs(save_path, exist_ok=True)
            
            # Track downloaded files
            downloaded_files = []
            
            # Process files and folders
            for item in files:
                if item.get("type") == "file":
                    # Download file
                    file_id = item.get("id")
                    file_name = item.get("name")
                    file_path = os.path.join(save_path, file_name)
                    
                    if self.seedr.download_file(file_id, file_path):
                        downloaded_files.append(file_path)
                elif item.get("type") == "folder":
                    # Download folder as archive
                    folder_id = item.get("id")
                    folder_name = item.get("name")
                    archive_path = os.path.join(save_path, f"{folder_name}.zip")
                    
                    if self.seedr.download_folder_as_archive(folder_id, archive_path):
                        downloaded_files.append(archive_path)
            
            return {
                "success": True,
                "downloaded_files": downloaded_files,
                "message": f"Downloaded {len(downloaded_files)} files"
            }
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def notify_sonarr(self, title: str) -> Dict[str, Any]:
        """Notify Sonarr of downloaded files."""
        try:
            if not os.path.exists(self.mapping_file):
                return {"success": False, "message": "No download mapping found"}

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            if title not in mappings:
                return {"success": False, "message": "Download not found"}
            
            # Download the files if needed
            download_path = self.config.download.download_dir
            
            # Check if download directory is set
            if not download_path:
                return {"success": False, "message": "Download directory not set"}
            
            # Download files
            download_result = self.download_completed_files(title, download_path)
            
            if not download_result.get("success"):
                return download_result
            
            # Trigger Sonarr scan
            scan_result = self.sonarr.command_download_scan(download_path)
            
            return {
                "success": True,
                "message": "Notified Sonarr of downloaded files",
                "sonarr_response": scan_result,
                "downloaded_files": download_result.get("downloaded_files", [])
            }
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def pause_download(self, title: str) -> Dict[str, Any]:
        """Pause a download."""
        try:
            if not os.path.exists(self.mapping_file):
                return {"success": False, "message": "No download mapping found"}

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            if title not in mappings:
                return {"success": False, "message": "Download not found"}

            torrent_id = mappings[title]["torrent_id"]
            
            # Check if the download is active
            status = self.check_download_status(title)
            
            if status.get("status") == "downloading":
                # Pause the download
                if self.seedr.pause_task(torrent_id):
                    return {
                        "success": True,
                        "message": f"Paused download for {title}"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to pause download"
                    }
            else:
                return {
                    "success": False,
                    "message": f"Download not in progress (status: {status.get('status')})"
                }
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def resume_download(self, title: str) -> Dict[str, Any]:
        """Resume a paused download."""
        try:
            if not os.path.exists(self.mapping_file):
                return {"success": False, "message": "No download mapping found"}

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            if title not in mappings:
                return {"success": False, "message": "Download not found"}

            torrent_id = mappings[title]["torrent_id"]
            
            # Check if the download is paused
            status = self.check_download_status(title)
            
            if status.get("status") == "paused":
                # Resume the download
                if self.seedr.resume_task(torrent_id):
                    return {
                        "success": True,
                        "message": f"Resumed download for {title}"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to resume download"
                    }
            else:
                return {
                    "success": False,
                    "message": f"Download not paused (status: {status.get('status')})"
                }
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_download(self, title: str) -> Dict[str, Any]:
        """Delete a download."""
        try:
            if not os.path.exists(self.mapping_file):
                return {"success": False, "message": "No download mapping found"}

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            if title not in mappings:
                return {"success": False, "message": "Download not found"}

            torrent_id = mappings[title]["torrent_id"]
            
            # Delete the torrent
            if self.seedr.delete_torrent(torrent_id):
                # Remove from mappings
                del mappings[title]
                
                # Save updated mappings
                with open(self.mapping_file, 'w') as f:
                    json.dump(mappings, f)
                
                return {
                    "success": True,
                    "message": f"Deleted download for {title}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to delete download"
                }
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def poll_downloads(self) -> List[Dict[str, Any]]:
        """Poll all downloads and return their status."""
        try:
            if not os.path.exists(self.mapping_file):
                return []

            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)

            results = []
            
            for title, mapping in mappings.items():
                torrent_id = mapping["torrent_id"]
                series_id = mapping.get("series_id")
                added_at = mapping.get("added_at", 0)
                
                # Get status
                status = self.check_download_status(title)
                
                # Add to results
                results.append({
                    "title": title,
                    "torrent_id": torrent_id,
                    "series_id": series_id,
                    "added_at": added_at,
                    "status": status.get("status", "unknown"),
                    "progress": status.get("progress", 0),
                    "message": status.get("message", "")
                })
            
            return results
            
        except Exception as e:
            print(f"Error polling downloads: {e}")
            return [] 