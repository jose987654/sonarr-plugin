from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
import os

# Import the auth module from parent package
from ..auth.oauth_handler import OAuthHandler
from ..config import Config

router = APIRouter(tags=["Web Interface"])
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Helper function to get watcher settings
def get_watcher_settings():
    """Get the watcher settings from the config file"""
    config_file = Path(__file__).parents[2] / "config" / "watcher_config.json"
    watcher_settings = {}
    
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                watcher_settings = json.loads(f.read())
        except Exception as e:
            print(f"Error reading watcher config: {e}")
    
    return watcher_settings

# Helper function to check authentication
def is_authenticated():
    """Check if user is authenticated with Seedr"""
    config = Config.from_env()
    auth = OAuthHandler(config.seedr)
    return auth.get_access_token() is not None

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the dashboard page"""
    # Check authentication
    if not is_authenticated():
        return RedirectResponse(url="/reauth", status_code=303)
    
    # Get downloads from the integration for display
    from ..service.seedr_sonarr_integration import SeedrSonarrIntegration
    from ..config import Config
    
    config = Config.from_env()
    integration = SeedrSonarrIntegration(config, strict_validation=False)
    
    try:
        # Get active downloads
        torrents = integration.poll_downloads()
        
        # Calculate stats
        active_count = sum(1 for t in torrents if t.get("status", {}).get("status") == "downloading")
        completed_count = sum(1 for t in torrents if t.get("status", {}).get("status") == "completed")
        
        # Get seedr account info
        account_info = integration.seedr.get_account_info()
        space_used = account_info.get("space_used", "0 MB")
        space_available = account_info.get("space_available", "0 MB")
    except Exception as e:
        print(f"Error fetching downloads or account info: {e}")
        torrents = []
        active_count = 0
        completed_count = 0
        space_used = "0 MB"
        space_available = "0 MB"
    
    # Get watcher settings
    watcher_settings = get_watcher_settings()
    
    # Get watcher status
    from ..main import watcher_thread
    watcher_status = "Running" if watcher_thread is not None and watcher_thread.is_alive() else "Not Running"
    
    # Get last check time (if available)
    last_check = "Never"
    try:
        log_file = Path(__file__).parents[2] / "folder_watcher.log"
        if log_file.exists():
            import re
            from datetime import datetime
            
            with open(log_file, "r") as f:
                # Look for the last check entry in the logs
                lines = f.readlines()[-100:]  # Get last 100 lines
                for line in reversed(lines):
                    if "Started watching" in line or "TorrentWatcher initialized" in line:
                        # Extract timestamp 
                        match = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        if match:
                            timestamp = match.group(1)
                            last_check = timestamp
                            break
    except Exception as e:
        print(f"Error getting last check time: {e}")
    
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request,
            "torrents": torrents,
            "active_count": active_count,
            "completed_count": completed_count,
            "space_used": space_used,
            "space_available": space_available,
            "watcher_settings": watcher_settings,
            "watcher_status": watcher_status,
            "last_check": last_check,
            "messages": []
        }
    )

@router.get("/torrents", response_class=HTMLResponse)
async def torrents(request: Request):
    """Render the torrents page"""
    # Check authentication
    if not is_authenticated():
        return RedirectResponse(url="/reauth", status_code=303)
    
    # Get downloads for display
    from ..service.seedr_sonarr_integration import SeedrSonarrIntegration
    from ..config import Config
    
    config = Config.from_env()
    integration = SeedrSonarrIntegration(config, strict_validation=False)
    
    try:
        torrents = integration.poll_downloads()
        messages = []
        error_403 = False
        error_413 = False
    except Exception as e:
        torrents = []
        messages = [f"Error fetching downloads: {str(e)}"]
        error_403 = "403" in str(e)
        error_413 = "413" in str(e)
    
    return templates.TemplateResponse(
        "torrents.html", 
        {
            "request": request,
            "torrents": torrents,
            "messages": messages,
            "error_403": error_403,
            "error_413": error_413
        }
    )

@router.get("/config", response_class=HTMLResponse)
async def config(request: Request, success: bool = False):
    """Render the config page"""
    # Check authentication
    if not is_authenticated():
        return RedirectResponse(url="/reauth", status_code=303)
    
    # Get watcher settings
    watcher_settings = get_watcher_settings()
    
    # Pass success message if provided
    messages = []
    if success:
        messages.append("Configuration saved successfully!")
    
    return templates.TemplateResponse(
        "config.html", 
        {
            "request": request, 
            "watcher_settings": watcher_settings,
            "messages": messages
        }
    )

@router.get("/folder-watcher", response_class=HTMLResponse)
async def folder_watcher(request: Request):
    """Render the folder watcher page"""
    # Check authentication
    if not is_authenticated():
        return RedirectResponse(url="/reauth", status_code=303)
    
    # Get watcher settings
    watcher_settings = get_watcher_settings()
    
    # Get watcher status
    from ..main import watcher_thread
    is_running = watcher_thread is not None and watcher_thread.is_alive()
    
    # Get recent logs
    log_file = Path(__file__).parents[2] / "folder_watcher.log"
    activity_log = ""
    
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                # Get the last 50 lines
                lines = f.readlines()[-50:]
                activity_log = "".join(lines)
        except Exception as e:
            print(f"Error reading log file: {e}")
    
    return templates.TemplateResponse(
        "folder_watcher.html", 
        {
            "request": request,
            "settings": watcher_settings,
            "is_running": is_running,
            "activity_log": activity_log
        }
    )

@router.get("/reauth", response_class=HTMLResponse)
async def reauth(request: Request):
    """Render the re-authentication page"""
    return templates.TemplateResponse("reauth.html", {"request": request})

@router.get("/auth-polling", response_class=HTMLResponse)
async def auth_polling(request: Request, user_code: str, verification_uri: str):
    """Render the auth polling page"""
    return templates.TemplateResponse(
        "auth_polling.html", 
        {
            "request": request,
            "user_code": user_code,
            "verification_uri": verification_uri
        }
    )

@router.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """Render the success page"""
    return templates.TemplateResponse("success.html", {"request": request})

@router.get("/dashboard", response_class=RedirectResponse)
async def redirect_dashboard():
    """Redirect dashboard to root path"""
    return RedirectResponse(url="/", status_code=303) 