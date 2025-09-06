"""
FastAPI application for Sonarr-Seedr integration.
"""
import os
import json
import threading
import logging
from typing import Dict, Any, List, Optional
import shutil
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from .config import Config
from .auth.oauth_handler import OAuthHandler
from .service.seedr_sonarr_integration import SeedrSonarrIntegration
from .api.seedr_client import SeedrClient
from .api.sonarr_client import SonarrClient
from .utils.torrent_watcher import watch_folder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'folder_watcher.log'))
    ]
)
logger = logging.getLogger("sonarr_seedr")

# Initialize FastAPI app
app = FastAPI(
    title="Sonarr-Seedr Integration",
    description="API for integrating Sonarr with Seedr cloud torrent service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "web", "templates"))

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "web", "static")), name="static")

# OAuth2 password bearer for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Global variables
config = Config.from_env()
# Use non-strict validation for portable deployment - allows startup without full config
integration = SeedrSonarrIntegration(config, strict_validation=False)
seedr_client = SeedrClient(config.seedr)
sonarr_client = SonarrClient(config.sonarr)
watcher_thread = None

# Import web routes
from app.web import routes as web_routes

# Include web routes
app.include_router(web_routes.router)

# Add startup event handler for auto-starting the watcher
@app.on_event("startup")
async def startup_event():
    """Auto-start the watcher on application startup if enabled in config."""
    print("\n" + "="*80)
    print("TORRENT WATCHER AUTO-START INITIALIZATION")
    print("="*80)
    
    try:
        print("\n[STEP 1] Loading or creating watcher configuration...")
        
        base_dir = os.path.dirname(os.path.dirname(__file__))
        config_dir = os.path.join(base_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        
        # Get or create watcher config
        watcher_config_file = os.path.join(config_dir, "watcher_config.json")
        
        # Check if config exists
        if os.path.exists(watcher_config_file):
            with open(watcher_config_file, "r") as f:
                try:
                    settings = json.load(f)
                    print(f"✓ Successfully loaded existing watcher config from: {watcher_config_file}")
                    logger.info(f"Loaded watcher config: {settings}")
                except json.JSONDecodeError:
                    # Invalid JSON, create empty config
                    settings = {
                        "watch_interval": 30,
                        "save_magnet_files": True,
                        "magnet_extension": ".magnet",
                        "auto_start": True
                    }
                    print(f"! Invalid JSON in config file. Created minimal configuration without directories.")
                    logger.info(f"Created minimal config due to invalid JSON: {settings}")
        else:
            # Create minimal config without directories
            settings = {
                "watch_interval": 30,
                "save_magnet_files": True,
                "magnet_extension": ".magnet",
                "auto_start": True
            }
            print(f"+ Created new minimal configuration file without directories: {watcher_config_file}")
            logger.info(f"Created minimal config without directories: {settings}")
            
            # Create config directory if needed
            os.makedirs(config_dir, exist_ok=True)
            
            # Save minimal config
            with open(watcher_config_file, "w") as f:
                json.dump(settings, f, indent=4)
        
        # User preference for auto-start 
        auto_start = settings.get("auto_start", True)
        
        print("\n[STEP 2] Checking watcher directories...")
            
        # Get torrent and download directories
        torrent_dir = settings.get("torrent_dir")
        download_dir = settings.get("download_dir")
        
        # Check if user has configured directories
        if not torrent_dir or not download_dir:
            print("\n⚠️ User has not configured both directories yet")
            print("Watcher will not start until user selects both directories in settings")
            logger.info("Watcher not started - missing user-configured directories")
            return
            
        # Check if directories exist
        if not os.path.exists(torrent_dir):
            print(f"⚠️ Configured torrent directory does not exist: {torrent_dir}")
            print("Watcher will not start until directory exists")
            logger.info(f"Watcher not started - torrent directory doesn't exist: {torrent_dir}")
            return
            
        if not os.path.exists(download_dir):
            print(f"⚠️ Configured download directory does not exist: {download_dir}")
            print("Watcher will not start until directory exists")
            logger.info(f"Watcher not started - download directory doesn't exist: {download_dir}")
            return
            
        print(f"✓ Using configured torrent directory: {torrent_dir}")
        print(f"✓ Using configured download directory: {download_dir}")
        
        # Check if auto-start is enabled
        if not auto_start:
            print("\n⚠️ Auto-start is disabled in configuration")
            print("Watcher will not start automatically")
            logger.info("Watcher not started - auto-start disabled")
            return
            
        print("\n[STEP 3] Starting torrent watcher service...")
        
        # Initialize and start watcher in a separate thread
        def start_watcher_thread():
            global watcher_thread
            
            # Don't start if already running
            if watcher_thread and watcher_thread.is_alive():
                print("! Watcher is already running, not starting a new instance")
                logger.info("Watcher already running, not starting a new instance")
                return
                
            try:
                # Create event handler and observer
                event_handler = TorrentWatcher(config, integration, download_dir)
                observer = Observer()
                
                # Schedule directory to watch
                observer.schedule(event_handler, torrent_dir, recursive=False)
                observer.start()
                
                print(f"✓ Now watching directory for torrent files: {torrent_dir}")
                logger.info(f"Started watching {torrent_dir} for torrent files")
                
                # Store the observer in the thread
                def watcher_task(observer):
                    try:
                        while True:
                            time.sleep(1)
                    except Exception as e:
                        print(f"\n❌ ERROR IN WATCHER THREAD: {str(e)}")
                        logger.exception(f"Error in watcher thread: {str(e)}")
                    finally:
                        observer.stop()
                        observer.join()
                        print("! Torrent watcher stopped")
                        logger.info("Stopped watching for torrent files")
                
                watcher_thread = threading.Thread(target=watcher_task, args=(observer,))
                watcher_thread.daemon = True
                watcher_thread.start()
                
                print("✓ Watcher thread started successfully")
                logger.info("Watcher thread started successfully")
            except Exception as e:
                print(f"\n❌ ERROR STARTING WATCHER: {str(e)}")
                logger.exception(f"Error starting watcher: {str(e)}")
        
        # Start the watcher thread
        start_watcher_thread()
        
        print("\n✅ TORRENT WATCHER STARTED SUCCESSFULLY")
        print("-"*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR IN STARTUP EVENT: {str(e)}")
        logger.exception(f"Error in startup event: {str(e)}")
        print("\nSee log file for detailed error information")
        print("-"*80 + "\n")

# Pydantic models for request/response
class DownloadRequest(BaseModel):
    """Request model for adding a download."""
    title: str = Field(..., description="Title of the download")
    download_url: str = Field(..., description="URL or magnet link to download")
    series_id: Optional[int] = Field(None, description="Sonarr series ID")


class DownloadResponse(BaseModel):
    """Response model for download operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    download_id: Optional[str] = Field(None, description="ID of the download")


class StatusResponse(BaseModel):
    """Response model for status operations."""
    status: str = Field(..., description="Status of the download")
    progress: Optional[float] = Field(None, description="Download progress (0-100)")
    message: Optional[str] = Field(None, description="Status message")


class GenericResponse(BaseModel):
    """Generic response model."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")


# Authentication Middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    
    # Exclude API docs from authentication
    if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi.json"):
        return await call_next(request)
    
    # Exclude static files from authentication
    if request.url.path.startswith("/static"):
        return await call_next(request)
    
    # Exclude auth endpoints from authentication
    if request.url.path.startswith("/api/auth") or request.url.path == "/reauth":
        return await call_next(request)
    
    # Check if authenticated - only for web UI routes
    if (request.url.path == "/" or 
        request.url.path == "/config" or 
        request.url.path == "/torrents" or 
        request.url.path == "/folder-watcher"):
        is_authenticated = seedr_client.auth.get_access_token() is not None
        if not is_authenticated:
            return RedirectResponse(url="/reauth", status_code=303)
    
    # Continue with the request
    return await call_next(request)


# Dependency to get the current config
def get_config():
    """Get the current configuration."""
    return config


# Dependency to get the integration service
def get_integration():
    """Get the integration service."""
    return integration


# Torrent Watcher class for file system events
class TorrentWatcher(FileSystemEventHandler):
    """Handles torrent file events for auto-uploading to Seedr."""
    
    def __init__(self, config, integration, download_dir=None):
        """Initialize the watcher with config and dirs."""
        self.config = config
        self.integration = integration
        
        # Set up directories
        base_dir = os.path.dirname(os.path.dirname(__file__))
        self.download_dir = download_dir or os.path.join(base_dir, 'completed')
        self.processed_dir = os.path.join(base_dir, 'processed')
        self.error_dir = os.path.join(base_dir, 'error')
        
        # Create directories
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.error_dir, exist_ok=True)
        
        # Set up logging
        self.logger = logger
        self.logger.info(f"TorrentWatcher initialized. Watching for .torrent files")
        self.logger.info(f"Downloads will be saved to: {self.download_dir}")
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._is_torrent_file(event.src_path):
            self.logger.info(f"New torrent file detected: {event.src_path}")
            self._process_torrent_file(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and self._is_torrent_file(event.src_path):
            self.logger.info(f"Modified torrent file detected: {event.src_path}")
            self._process_torrent_file(event.src_path)
    
    def _is_torrent_file(self, file_path):
        """Check if file is a torrent file."""
        _, ext = os.path.splitext(file_path)
        return ext.lower() in ['.torrent', '.magnet']
    
    def _process_torrent_file(self, file_path):
        """Process a torrent file by adding it to Seedr."""
        file_name = os.path.basename(file_path)
        try:
            self.logger.info(f"Processing file: {file_path}")
            
            # Read file content - handle both magnet links and torrent files
            if file_path.endswith('.magnet'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    magnet_link = f.read().strip()
                
                # Add to Seedr
                result = self.integration.add_download(file_name, magnet_link)
            else:
                # For .torrent files, use the file upload API
                result = self.integration.add_torrent_file(file_path)
            
            if result.get("success", False):
                self.logger.info(f"Successfully added {file_name} to Seedr")
                # Move to processed folder
                processed_path = os.path.join(self.processed_dir, file_name)
                shutil.copy2(file_path, processed_path)
                self.logger.info(f"Moved {file_name} to processed directory")
            else:
                self.logger.error(f"Failed to add {file_name} to Seedr: {result.get('message', 'Unknown error')}")
                # Move to error folder
                error_path = os.path.join(self.error_dir, file_name)
                shutil.copy2(file_path, error_path)
                self.logger.error(f"Moved {file_name} to error directory")
                
        except Exception as e:
            self.logger.exception(f"Error processing {file_name}: {str(e)}")
            try:
                # Move to error folder
                error_path = os.path.join(self.error_dir, file_name)
                shutil.copy2(file_path, error_path)
                self.logger.error(f"Moved {file_name} to error directory")
            except Exception:
                self.logger.exception(f"Failed to move {file_name} to error directory")


# Routes
@app.get("/", response_class=RedirectResponse)
async def root():
    """Redirect to dashboard page."""
    return RedirectResponse(url="/dashboard")


@app.get("/api/config", response_model=Dict[str, Any])
async def get_config_api(config: Config = Depends(get_config)):
    """Get the current configuration."""
    # Return only non-sensitive parts of the config
    return {
        "seedr": {
            "api_base_url": config.seedr.api_base_url
        },
        "sonarr": {
            "host": config.sonarr.host
        },
        "download": {
            "download_dir": config.download.download_dir,
            "root_folder": config.download.root_folder
        }
    }


@app.post("/api/downloads", response_model=DownloadResponse)
async def add_download(
    request: DownloadRequest,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Add a new download to Seedr.
    
    This endpoint accepts a torrent URL or magnet link and adds it to Seedr.
    """
    result = integration.add_download(request.title, request.download_url, request.series_id)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to add download"))
    return result


@app.get("/api/downloads", response_model=List[Dict[str, Any]])
async def get_downloads(integration: SeedrSonarrIntegration = Depends(get_integration)):
    """
    Get all current downloads.
    
    Returns a list of all downloads being tracked by the integration.
    """
    return integration.poll_downloads()


@app.get("/api/downloads/{title}/status", response_model=StatusResponse)
async def get_download_status(
    title: str,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Get the status of a download.
    
    This endpoint returns the current status of a download.
    """
    result = integration.check_download_status(title)
    if result.get("status") == "unknown":
        raise HTTPException(status_code=404, detail=f"Download '{title}' not found")
    return result


@app.get("/api/downloads/{title}/files", response_model=Dict[str, Any])
async def get_download_files(
    title: str,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Get the files for a completed download.
    
    This endpoint returns the files for a completed download.
    """
    result = integration.get_downloaded_files(title)
    if not result.get("success", False):
        raise HTTPException(status_code=404, detail=result.get("message", f"Files for '{title}' not found"))
    return result


@app.post("/api/downloads/{title}/download", response_model=Dict[str, Any])
async def download_files(
    title: str,
    save_path: Optional[str] = None,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Download files for a completed download.
    
    This endpoint downloads the files for a completed download.
    """
    result = integration.download_completed_files(title, save_path)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message", f"Failed to download files for '{title}'"))
    return result


@app.post("/api/downloads/{title}/notify-sonarr", response_model=Dict[str, Any])
async def notify_sonarr(
    title: str,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Notify Sonarr of completed download.
    
    This endpoint downloads the files and notifies Sonarr of the completed download.
    """
    result = integration.notify_sonarr(title)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message", f"Failed to notify Sonarr for '{title}'"))
    return result


@app.post("/api/downloads/{title}/pause", response_model=GenericResponse)
async def pause_download(
    title: str,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Pause a download.
    
    This endpoint pauses a download in progress.
    """
    result = integration.pause_download(title)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message", f"Failed to pause download '{title}'"))
    return result


@app.post("/api/downloads/{title}/resume", response_model=GenericResponse)
async def resume_download(
    title: str,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Resume a paused download.
    
    This endpoint resumes a paused download.
    """
    result = integration.resume_download(title)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message", f"Failed to resume download '{title}'"))
    return result


@app.delete("/api/downloads/{title}", response_model=GenericResponse)
async def delete_download(
    title: str,
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Delete a download.
    
    This endpoint deletes a download from Seedr.
    """
    result = integration.delete_download(title)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message", f"Failed to delete download '{title}'"))
    return result


@app.get("/api/auth/status")
async def auth_status():
    """
    Check authentication status with Seedr.
    
    This endpoint returns whether authentication with Seedr is active.
    """
    is_authenticated = seedr_client.auth.get_access_token() is not None
    redirect = "/"
    return {"authenticated": is_authenticated, "redirect": redirect}


@app.post("/api/auth/login")
async def auth_login(background_tasks: BackgroundTasks):
    """
    Initiate authentication with Seedr.
    
    This endpoint starts the OAuth2 device flow for authentication with Seedr.
    """
    # Clear any existing tokens
    seedr_client.auth.clear_token()
    
    # Start device flow
    flow_data = seedr_client.auth.start_device_flow()
    
    # Get user code for authentication
    user_code = flow_data.get("user_code")
    verification_uri = flow_data.get("verification_uri")
    
    # Make sure we have a verification URI
    if not verification_uri:
        raise HTTPException(status_code=500, detail="Failed to get verification URI from Seedr")
    
    # Start polling for token in background
    device_code = flow_data.get("device_code")
    interval = flow_data.get("interval", 5)
    
    def poll_token():
        seedr_client.auth.poll_for_token(device_code, interval)
    
    background_tasks.add_task(poll_token)
    
    return {
        "success": True,
        "verification_uri": verification_uri,
        "user_code": user_code,
        "expires_in": flow_data.get("expires_in", 900)
    }


@app.post("/api/auth/logout")
async def auth_logout():
    """
    Log out from Seedr.
    
    This endpoint clears the authentication token for Seedr.
    """
    seedr_client.auth.clear_token()
    return {"success": True}


@app.get("/api/auth/poll")
async def auth_poll():
    """
    Poll for authentication status.
    
    This endpoint checks if authentication has been completed.
    """
    is_authenticated = seedr_client.auth.get_access_token() is not None
    if is_authenticated:
        return {"success": True, "redirect": "/config"}
    else:
        return {"success": False}


@app.get("/api/user")
async def get_user_profile():
    """
    Get authenticated user profile information.
    
    This endpoint returns profile information for the currently authenticated Seedr user.
    """
    if not seedr_client.auth.get_access_token():
        raise HTTPException(status_code=401, detail="Not authenticated with Seedr")
    
    user_info = seedr_client.get_account_info()
    if not user_info:
        raise HTTPException(status_code=500, detail="Failed to get user profile information")
    
    return user_info


@app.get("/api/sonarr/series")
async def get_series():
    """
    Get all series from Sonarr.
    
    This endpoint returns all series from Sonarr.
    """
    return sonarr_client.get_series()


@app.get("/api/sonarr/missing")
async def get_missing():
    """
    Get missing episodes from Sonarr.
    
    This endpoint returns all missing episodes from Sonarr.
    """
    return sonarr_client.get_missing_episodes()


@app.get("/api/sonarr/rootfolders")
async def get_rootfolders():
    """
    Get root folders from Sonarr.
    
    This endpoint returns all root folders from Sonarr.
    """
    return sonarr_client.get_root_folders()


@app.post("/api/watcher/start")
async def start_watcher(
    torrent_dir: Optional[str] = Query(None, description="Directory to watch for torrent files"),
    download_dir: Optional[str] = Query(None, description="Directory for completed downloads"),
    config: Config = Depends(get_config)
):
    """
    Start the torrent watcher.
    
    This endpoint starts the torrent watcher to monitor a directory for new torrent files.
    If no directories are specified, it will use the configured directories or create defaults.
    """
    # Log that the watcher is being started manually
    logger.info("Manual watcher start requested via API")
    global watcher_thread
    
    # Check if watcher is already running
    if watcher_thread and watcher_thread.is_alive():
        return {"success": False, "message": "Watcher is already running"}
    
    # Get config if it exists
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "watcher_config.json")
    settings = {}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                settings = json.load(f)
        except Exception as e:
            logger.error(f"Error loading watcher config: {str(e)}")
    
    # Use provided directories or get from config or use defaults
    if not torrent_dir:
        torrent_dir = settings.get("torrent_dir")
        if not torrent_dir:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            torrent_dir = os.path.join(base_dir, "torrents")
    
    if not download_dir:
        download_dir = settings.get("download_dir")
        if not download_dir:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            download_dir = os.path.join(base_dir, "completed")
    
    # Create torrent directory if it doesn't exist
    os.makedirs(torrent_dir, exist_ok=True)
    
    # Create download directory if specified and it doesn't exist
    if download_dir:
        os.makedirs(download_dir, exist_ok=True)
    
    # Start watcher in a separate thread
    def watcher_task():
        # Create event handler and observer
        event_handler = TorrentWatcher(config, integration, download_dir)
        observer = Observer()
        
        # Schedule directory to watch
        observer.schedule(event_handler, torrent_dir, recursive=False)
        observer.start()
        
        logger.info(f"Started watching {torrent_dir} for torrent files")
        
        try:
            # Run forever until the thread is stopped
            while True:
                time.sleep(1)
        except Exception as e:
            logger.exception(f"Error in watcher thread: {str(e)}")
        finally:
            observer.stop()
            observer.join()
            logger.info("Stopped watching for torrent files")
    
    watcher_thread = threading.Thread(target=watcher_task)
    watcher_thread.daemon = True
    watcher_thread.start()
    
    # Save current settings back to config file
    watch_interval = settings.get("watch_interval", 30)
    save_magnet_files = settings.get("save_magnet_files", True)
    magnet_extension = settings.get("magnet_extension", ".magnet")
    auto_start = settings.get("auto_start", True)
    
    # Also save the watcher configuration
    watcher_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
    os.makedirs(watcher_config_path, exist_ok=True)
    watcher_config_file = os.path.join(watcher_config_path, "watcher_config.json")
    
    with open(watcher_config_file, "w") as f:
        json.dump({
            "torrent_dir": torrent_dir,
            "download_dir": download_dir,
            "watch_interval": watch_interval,
            "save_magnet_files": save_magnet_files,
            "magnet_extension": magnet_extension,
            "auto_start": auto_start
        }, f, indent=4)
    
    return {"success": True, "message": f"Started watching {torrent_dir}"}


@app.post("/api/watcher/config")
async def save_watcher_config(
    request: Request,
    config: Config = Depends(get_config)
):
    """
    Save watcher configuration.
    
    This endpoint saves the watcher configuration settings.
    """
    # Parse form data
    form_data = await request.form()
    
    # Extract values with defaults
    torrent_dir = form_data.get("torrent_dir", "")
    download_dir = form_data.get("download_dir", "")
    watch_interval = int(form_data.get("watch_interval", 30))
    
    # Checkboxes only appear in form data if checked
    save_magnet_files = "save_magnet_files" in form_data
    auto_start = "auto_start" in form_data
    magnet_extension = form_data.get("magnet_extension", ".magnet")
    
    # Update config
    settings = {
        "torrent_dir": torrent_dir,
        "download_dir": download_dir,
        "watch_interval": watch_interval,
        "save_magnet_files": save_magnet_files,
        "magnet_extension": magnet_extension,
        "auto_start": auto_start
    }
    
    # Validate both directories are provided
    if not torrent_dir or not download_dir:
        # Redirect back to config page with error message
        return RedirectResponse(url="/config?error=true&message=Both torrent and download directories must be specified", status_code=303)
    
    # Create directories if they don't exist
    os.makedirs(torrent_dir, exist_ok=True)
    os.makedirs(download_dir, exist_ok=True)
    
    # Save settings to file
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "watcher_config.json")
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    with open(config_file, "w") as f:
        json.dump(settings, f, indent=4)
    
    # Always start the watcher after saving configuration (unless explicitly specified not to)
    should_start = True
    
    # Only check for explicit "start_watcher=false" to avoid starting
    if "start_watcher" in form_data and form_data.get("start_watcher").lower() == "false":
        should_start = False
    
    if should_start:
        # Log that we're starting the watcher after config save
        logger.info(f"Starting watcher after configuration save for directories: {torrent_dir} and {download_dir}")
        
        # Start the watcher non-async by calling the synchronous parts directly
        try:
            # Create event handler and observer
            event_handler = TorrentWatcher(config, integration, download_dir)
            observer = Observer()
            
            # Schedule directory to watch
            observer.schedule(event_handler, torrent_dir, recursive=False)
            observer.start()
            
            logger.info(f"Started watching {torrent_dir} for torrent files")
            
            # Store observer in thread
            def watcher_task(observer):
                try:
                    while True:
                        time.sleep(1)
                except Exception as e:
                    logger.exception(f"Error in watcher thread: {str(e)}")
                finally:
                    observer.stop()
                    observer.join()
                    logger.info("Stopped watching for torrent files")
            
            global watcher_thread
            watcher_thread = threading.Thread(target=watcher_task, args=(observer,))
            watcher_thread.daemon = True
            watcher_thread.start()
            
            logger.info("Watcher thread started successfully after config save")
        except Exception as e:
            logger.exception(f"Error starting watcher after config save: {str(e)}")
    
    # Redirect to dashboard instead of back to config
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/watcher/stop")
async def stop_watcher():
    """
    Stop the torrent watcher.
    
    This endpoint stops the torrent watcher.
    """
    global watcher_thread
    
    # Check if watcher is running
    if not watcher_thread or not watcher_thread.is_alive():
        return {"success": False, "message": "Watcher is not running"}
    
    # Set watcher_thread to None to signal it to stop
    watcher_thread = None
    
    logger.info("Stopped torrent watcher")
    return {"success": True, "message": "Watcher stopped"}


@app.get("/api/watcher/status")
async def watcher_status():
    """
    Get the status of the torrent watcher.
    
    This endpoint returns whether the torrent watcher is running.
    """
    global watcher_thread
    is_running = watcher_thread is not None and watcher_thread.is_alive()
    return {"running": is_running}


@app.get("/api/watcher/scan")
async def scan_torrents():
    """
    Scan for torrent files in the watched folder.
    
    This endpoint scans the torrent directory configured in the watcher settings
    and returns a list of torrent files found.
    """
    # Get the watcher settings
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "watcher_config.json")
    
    if not os.path.exists(config_file):
        return {"success": False, "message": "Watcher not configured"}
    
    try:
        with open(config_file, "r") as f:
            settings = json.load(f)
        
        torrent_dir = settings.get("torrent_dir")
        if not torrent_dir or not os.path.exists(torrent_dir):
            return {"success": False, "message": "Torrent directory not found"}
        
        # Scan for torrent files
        torrents = []
        for file_name in os.listdir(torrent_dir):
            file_path = os.path.join(torrent_dir, file_name)
            if not os.path.isfile(file_path):
                continue
                
            _, ext = os.path.splitext(file_name)
            if ext.lower() not in ['.torrent', '.magnet']:
                continue
            
            file_stat = os.stat(file_path)
            
            torrents.append({
                "name": file_name,
                "path": file_path,
                "size": f"{file_stat.st_size / 1024:.1f} KB",
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(file_stat.st_mtime))
            })
        
        return {"success": True, "torrents": torrents}
        
    except Exception as e:
        logger.exception(f"Error scanning for torrents: {str(e)}")
        return {"success": False, "message": f"Error scanning folder: {str(e)}"}


@app.get("/api/watcher/logs")
async def get_watcher_logs(lines: int = 50):
    """
    Get the watcher log entries.
    
    This endpoint returns the most recent log entries from the watcher log file.
    """
    log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "folder_watcher.log")
    
    if not os.path.exists(log_file):
        return {"success": False, "message": "Log file not found"}
    
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            # Get the specified number of lines from the end
            log_lines = all_lines[-lines:] if lines < len(all_lines) else all_lines
        
        return {"success": True, "logs": log_lines}
        
    except Exception as e:
        logger.exception(f"Error reading log file: {str(e)}")
        return {"success": False, "message": f"Error reading log file: {str(e)}"}


@app.post("/api/watcher/upload")
async def upload_torrent(
    payload: dict, 
    config: Config = Depends(get_config),
    integration: SeedrSonarrIntegration = Depends(get_integration)
):
    """
    Upload a torrent file to Seedr.
    
    This endpoint uploads a torrent file to Seedr for processing.
    """
    file_path = payload.get("path")
    
    if not file_path or not os.path.exists(file_path):
        return {"success": False, "message": "File not found"}
    
    try:
        # Create a torrent handler
        from .utils.torrent_watcher import TorrentWatcher
        handler = TorrentWatcher(config, integration)
        
        # Get the download directory from config
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "watcher_config.json")
        download_dir = None
        
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                settings = json.load(f)
                download_dir = settings.get("download_dir")
        
        # If download_dir is specified, update handler
        if download_dir:
            handler.download_dir = download_dir
        
        # Process the torrent file
        result = handler._process_torrent_file(file_path)
        
        if result:
            # Log successful upload
            logger.info(f"[MANUAL] Successfully uploaded torrent file: {os.path.basename(file_path)}")
            return {"success": True, "message": "Torrent file uploaded successfully"}
        else:
            return {"success": False, "message": "Failed to upload torrent file"}
        
    except Exception as e:
        logger.exception(f"Error uploading torrent file: {str(e)}")
        return {"success": False, "message": f"Error uploading torrent file: {str(e)}"}


@app.post("/api/watcher/delete-file")
async def delete_torrent_file(payload: dict):
    """
    Delete a torrent file.
    
    This endpoint deletes a torrent file from the filesystem.
    """
    file_path = payload.get("path")
    
    if not file_path or not os.path.exists(file_path):
        return {"success": False, "message": "File not found"}
    
    try:
        # Delete the file
        os.remove(file_path)
        
        # Log deletion
        logger.info(f"[MANUAL] Deleted torrent file: {os.path.basename(file_path)}")
        
        return {"success": True, "message": "Torrent file deleted successfully"}
        
    except Exception as e:
        logger.exception(f"Error deleting torrent file: {str(e)}")
        return {"success": False, "message": f"Error deleting torrent file: {str(e)}"}


# Filesystem related endpoints
@app.get("/api/filesystem/folders")
async def get_folders(path: str = ""):
    """
    Get folders at a given path.
    
    This endpoint returns all folders at the specified path.
    """
    try:
        if not path:
            # List drives on Windows
            if os.name == 'nt':
                import string
                from ctypes import windll
                
                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drives.append(f"{letter}:")
                    bitmask >>= 1
                return {"folders": drives}
            else:
                # List root directory on Unix-like systems
                path = "/"
        
        # Get all subdirectories
        folders = []
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir() and not entry.name.startswith('.'):
                    folders.append(entry.name)
        
        return {"folders": sorted(folders)}
    except Exception as e:
        logger.error(f"Error getting folders at {path}: {str(e)}")
        return {"folders": [], "error": str(e)}


@app.post("/api/browse_folders")
async def browse_folders(payload: dict):
    """
    Browse folders at a given path.
    
    This endpoint returns folders at the specified path.
    """
    path = payload.get("path", "")
    print(f"FOLDER BROWSER API CALLED with path: '{path}'")
    logger.info(f"Browsing folders at path: '{path}'")
    
    try:
        # If no path or path is a special keyword, list root directories/drives
        if not path or path == "ROOT":
            # List drives on Windows
            if os.name == 'nt':
                import string
                from ctypes import windll
                
                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drives.append(f"{letter}:\\")
                    bitmask >>= 1
                
                print(f"RETURNING DRIVES: {drives}")
                return {
                    "success": True, 
                    "current_path": "", 
                    "folders": drives
                }
            else:
                # List root directory on Unix-like systems
                path = "/"
        
        # Check if path exists
        if not os.path.exists(path):
            print(f"PATH DOES NOT EXIST: {path}")
            return {"success": False, "message": f"Path does not exist: {path}"}
        
        # Get all subdirectories
        print(f"LISTING DIRECTORIES in: {path}")
        folders = []
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path) and not item.startswith('.'):
                folders.append(full_path)
        
        print(f"FOUND {len(folders)} FOLDERS: {folders[:5]}...")
        return {
            "success": True,
            "current_path": path,
            "folders": sorted(folders)
        }
        
    except Exception as e:
        print(f"ERROR BROWSING FOLDERS: {str(e)}")
        logger.error(f"Error browsing folders at {path}: {str(e)}")
        return {"success": False, "message": str(e)}


@app.get("/api/test")
async def test_endpoint():
    """
    Simple test endpoint to verify API access.
    """
    print("Test endpoint called!")
    return {"success": True, "message": "API is working!"}


# Main entry point
def start():
    """Start the FastAPI application."""
    # Start the FastAPI server
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


def start_background_watcher():
    """Start the watcher in the background if it's not already running.
    This will auto-start the watcher with default directories if none are configured."""
    global watcher_thread
    
    # Don't start if watcher is already running
    if watcher_thread and watcher_thread.is_alive():
        logger.info("Watcher already running, not starting a new instance")
        return
    
    # Get watcher config if it exists
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "watcher_config.json")
    
    # Check if config exists and load settings
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                settings = json.load(f)
            
            torrent_dir = settings.get("torrent_dir")
            download_dir = settings.get("download_dir")
            auto_start = settings.get("auto_start", True)  # Default to auto-start
            
            # Don't start if auto_start is disabled
            if not auto_start:
                logger.info("Watcher auto-start is disabled in config")
                return
                
            # Create default directories if not configured
            if not torrent_dir:
                torrent_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "torrents")
                os.makedirs(torrent_dir, exist_ok=True)
                logger.info(f"Using default torrent directory: {torrent_dir}")
                
            if not download_dir:
                download_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "completed")
                os.makedirs(download_dir, exist_ok=True)
                logger.info(f"Using default download directory: {download_dir}")

            # Ensure directories exist
            if not os.path.exists(torrent_dir):
                os.makedirs(torrent_dir, exist_ok=True)
                logger.info(f"Created configured torrent directory: {torrent_dir}")
            
            if not os.path.exists(download_dir):
                os.makedirs(download_dir, exist_ok=True)
                logger.info(f"Created configured download directory: {download_dir}")
            
            # Start watcher with config directly instead of async function
            logger.info(f"Auto-starting watcher for directory: {torrent_dir}")
            
            # Create event handler and observer directly
            def start_background():
                try:
                    # Create event handler and observer
                    event_handler = TorrentWatcher(config, integration, download_dir)
                    observer = Observer()
                    
                    # Schedule directory to watch
                    observer.schedule(event_handler, torrent_dir, recursive=False)
                    observer.start()
                    
                    # Store observer in thread
                    def watcher_task(observer):
                        try:
                            while True:
                                time.sleep(1)
                        except Exception as e:
                            logger.exception(f"Error in watcher thread: {str(e)}")
                        finally:
                            observer.stop()
                            observer.join()
                            logger.info("Stopped watching for torrent files")
                    
                    global watcher_thread
                    watcher_thread = threading.Thread(target=watcher_task, args=(observer,))
                    watcher_thread.daemon = True
                    watcher_thread.start()
                    
                    logger.info(f"Watcher started automatically monitoring {torrent_dir}")
                except Exception as e:
                    logger.error(f"Error auto-starting watcher: {str(e)}")
            
            # Start in a thread to avoid blocking
            auto_start_thread = threading.Thread(target=start_background)
            auto_start_thread.daemon = True
            auto_start_thread.start()
        
        except Exception as e:
            logger.error(f"Error loading watcher config: {str(e)}")
    else:
        # Create default config with auto-start disabled
        try:
            # Set default directories
            base_dir = os.path.dirname(os.path.dirname(__file__))
            default_torrent_dir = os.path.join(base_dir, "torrents")
            default_download_dir = os.path.join(base_dir, "completed")
            
            # Create directories
            os.makedirs(default_torrent_dir, exist_ok=True)
            os.makedirs(default_download_dir, exist_ok=True)
            
            # Create config directory
            config_dir = os.path.dirname(config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            # Save default config with auto-start explicitly enabled
            with open(config_file, "w") as f:
                json.dump({
                    "torrent_dir": default_torrent_dir,
                    "download_dir": default_download_dir,
                    "watch_interval": 30,
                    "save_magnet_files": True,
                    "magnet_extension": ".magnet",
                    "auto_start": True  # Always enable auto-start by default
                }, f, indent=4)
            
            logger.info(f"Created default watcher config with auto-start enabled")
            
            # However, don't start the watcher until the user explicitly configures directories
        
        except Exception as e:
            logger.error(f"Error creating default watcher config: {str(e)}")


if __name__ == "__main__":
    start() 