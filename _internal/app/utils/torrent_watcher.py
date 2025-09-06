"""
Torrent watcher module for monitoring folders.
"""
import os
import time
import logging
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..service.seedr_sonarr_integration import SeedrSonarrIntegration
from ..config import Config

# Configure logging
logger = logging.getLogger("torrent_watcher")

class TorrentWatcher(FileSystemEventHandler):
    """File system event handler for watching and processing torrent files."""
    
    def __init__(self, config, integration, download_dir=None):
        """Initialize the torrent watcher."""
        self.config = config
        self.integration = integration
        
        # Set up directories
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.download_dir = download_dir or os.path.join(base_dir, 'completed')
        self.processed_dir = os.path.join(base_dir, 'processed')
        self.error_dir = os.path.join(base_dir, 'error')
        
        # Create necessary directories
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.error_dir, exist_ok=True)
        
        # Configure logging
        self.logger = logger
        self.logger.info(f"TorrentWatcher initialized. Watching for .torrent and .magnet files")
        self.logger.info(f"Completed downloads will be saved to: {self.download_dir}")
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._is_torrent_or_magnet(event.src_path):
            self.logger.info(f"New file detected: {event.src_path}")
            self._process_torrent_file(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and self._is_torrent_or_magnet(event.src_path):
            self.logger.info(f"Modified file detected: {event.src_path}")
            self._process_torrent_file(event.src_path)
    
    def _is_torrent_or_magnet(self, file_path):
        """Check if the file is a torrent or magnet file."""
        _, ext = os.path.splitext(file_path)
        return ext.lower() in ['.torrent', '.magnet']
    
    def _process_torrent_file(self, file_path):
        """Process a torrent file by uploading it to Seedr."""
        try:
            self.logger.info(f"Processing torrent file: {os.path.basename(file_path)}")
            
            # Read file content
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Determine if this is a magnet link or a torrent file
            _, ext = os.path.splitext(file_path)
            
            if ext.lower() == '.magnet':
                # It's a magnet link file, read the content as text
                magnet_link = file_data.decode('utf-8').strip()
                self.logger.info(f"Uploading magnet link: {magnet_link[:50]}...")
                
                # Add the magnet link to Seedr
                result = self.integration.seedr.add_torrent(magnet_link)
                
                if not result:
                    self.logger.error(f"Failed to add magnet link to Seedr")
                    # Move to error directory
                    error_path = os.path.join(self.error_dir, os.path.basename(file_path))
                    shutil.copy2(file_path, error_path)
                    return False
                
                self.logger.info(f"Successfully added magnet link to Seedr")
            else:
                # It's a torrent file
                self.logger.info(f"Uploading torrent file: {os.path.basename(file_path)}")
                
                # Add the torrent file to Seedr
                result = self.integration.seedr.add_torrent(file_data)
                
                if not result:
                    self.logger.error(f"Failed to add torrent file to Seedr")
                    # Move to error directory
                    error_path = os.path.join(self.error_dir, os.path.basename(file_path))
                    shutil.copy2(file_path, error_path)
                    return False
                
                self.logger.info(f"Successfully added torrent file to Seedr")
            
            # Move to processed directory
            processed_path = os.path.join(self.processed_dir, os.path.basename(file_path))
            shutil.copy2(file_path, processed_path)
            
            return True
            
        except Exception as e:
            self.logger.exception(f"Error processing torrent file {os.path.basename(file_path)}: {str(e)}")
            
            # Move to error directory
            try:
                error_path = os.path.join(self.error_dir, os.path.basename(file_path))
                shutil.copy2(file_path, error_path)
            except Exception as move_error:
                self.logger.error(f"Error moving file to error directory: {str(move_error)}")
            
            return False

def watch_folder(torrent_dir, download_dir=None, interval=30):
    """Watch a folder for torrent files and process them."""
    logger.info(f"Starting folder watcher for {torrent_dir}")
    
    # Ensure the torrent directory exists
    if not os.path.exists(torrent_dir):
        logger.info(f"Creating torrent directory: {torrent_dir}")
        os.makedirs(torrent_dir, exist_ok=True)
    
    # Set up the integration
    config = Config.from_env()
    integration = SeedrSonarrIntegration(config, strict_validation=False)
    
    # Start watching the folder
    event_handler = TorrentWatcher(config, integration, download_dir)
    observer = Observer()
    observer.schedule(event_handler, torrent_dir, recursive=False)
    observer.start()
    
    logger.info(f"Started watching {torrent_dir} for torrent files")
    
    try:
        # Process any existing torrent files
        existing_files = [f for f in os.listdir(torrent_dir) 
                         if os.path.isfile(os.path.join(torrent_dir, f)) and 
                            (f.endswith('.torrent') or f.endswith('.magnet'))]
        
        if existing_files:
            logger.info(f"Found {len(existing_files)} existing torrent files to process")
            for file_name in existing_files:
                file_path = os.path.join(torrent_dir, file_name)
                try:
                    event_handler._process_torrent_file(file_path)
                except Exception as e:
                    logger.exception(f"Error processing existing file {file_name}: {str(e)}")
        
        # Monitor downloads and check for new files
        while True:
            # Check for completed downloads
            try:
                downloads = integration.poll_downloads()
                completed = [d for d in downloads if d.get("status", {}).get("status") == "completed"]
                
                for download in completed:
                    title = download.get("title", "Unknown")
                    
                    # Check if we have already downloaded this
                    flag_file = os.path.join(event_handler.download_dir, f".{title}.downloaded")
                    if os.path.exists(flag_file):
                        continue
                    
                    logger.info(f"Download completed: {title}")
                    
                    # Download files
                    try:
                        result = integration.download_completed_files(title, event_handler.download_dir)
                        
                        if result.get("success"):
                            # Create flag file to mark as downloaded
                            with open(flag_file, 'w') as f:
                                f.write("downloaded")
                            
                            logger.info(f"Downloaded files for {title}: {result.get('message')}")
                        else:
                            logger.error(f"Error downloading files for {title}: {result.get('message')}")
                    except Exception as e:
                        logger.exception(f"Exception downloading files for {title}: {str(e)}")
            except Exception as e:
                logger.exception(f"Error checking downloads: {str(e)}")
            
            # Sleep for the specified interval
            time.sleep(interval)
    
    except KeyboardInterrupt:
        logger.info("Folder watcher stopped by user")
    except Exception as e:
        logger.exception(f"Folder watcher error: {str(e)}")
    finally:
        observer.stop()
        observer.join()
        logger.info("Folder watcher stopped") 