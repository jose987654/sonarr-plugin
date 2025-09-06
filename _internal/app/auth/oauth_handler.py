"""
OAuth device flow authentication handler for Seedr.
"""
import os
import time
import json
import webbrowser
from typing import Optional, Dict, Any
import requests
from ..config import SeedrConfig

class OAuthHandler:
    def __init__(self, config: SeedrConfig):
        self.config = config
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_file = os.path.join(os.path.dirname(__file__), "..", "..", "config", "seedr_token.json")

    def load_token(self) -> bool:
        """Load saved token from file if it exists."""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    if token_data.get('expires_at', 0) > time.time():
                        self.access_token = token_data['access_token']
                        self.refresh_token = token_data.get('refresh_token')
                        return True
                    elif token_data.get('refresh_token'):
                        # Try to refresh the token if it's expired
                        new_token = self.refresh_access_token(token_data['refresh_token'])
                        if new_token:
                            return True
        except Exception as e:
            print(f"Error loading token: {e}")
        return False

    def save_token(self, token_data: Dict[str, Any]) -> None:
        """Save token data to file."""
        try:
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
        except Exception as e:
            print(f"Error saving token: {e}")

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh the access token using a refresh token."""
        try:
            response = requests.post(
                f"{self.config.api_base_url}/api/v0.1/p/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.config.client_id
                }
            )
            data = response.json()

            if "access_token" in data:
                self.access_token = data["access_token"]
                # Update refresh token if a new one is provided
                if "refresh_token" in data:
                    self.refresh_token = data["refresh_token"]
                
                # Save the new tokens
                self.save_token({
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expires_at": time.time() + data.get("expires_in", 3600)
                })
                return self.access_token
            else:
                print(f"Failed to refresh token: {data.get('error', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return None

    def start_device_flow(self) -> Dict[str, str]:
        """Start the OAuth2 device flow."""
        if not self.config.client_id:
            raise ValueError("SEEDR_CLIENT_ID not set in environment variables")

        response = requests.post(
            f"{self.config.api_base_url}/api/v0.1/p/oauth/device/code",
            data={
                "client_id": self.config.client_id,
                "scope": "files.read profile files.write files.delete files.list tasks.write tasks.read"
            }
        )
        response.raise_for_status()
        device_data = response.json()
        
        # Get the Seedr API base URL from config
        seedr_base_url = self.config.api_base_url
        # Extract just the domain part (e.g., "https://v2.seedr.cc")
        if seedr_base_url.count('/') >= 3:
            seedr_domain = '/'.join(seedr_base_url.split('/')[:3])
        else:
            seedr_domain = seedr_base_url
            
        # Always use the Seedr API base URL for verification
        device_data["verification_uri"] = f"{seedr_domain}/api/v0.1/p/oauth/device/verify"
        
        print(f"Verification URI: {device_data['verification_uri']}")
        return device_data

    def open_verification_url(self, verification_uri: str, user_code: str) -> None:
        """Open the verification URL in the default browser."""
        try:
            # Ensure verification URI has the base URL
            if verification_uri.startswith('/'):
                # Extract domain from api_base_url
                base_url_parts = self.config.api_base_url.split('/')
                domain = '/'.join(base_url_parts[:3])  # Get "https://domain.com" part
                verification_uri = f"{domain}{verification_uri}"
            
            # Print information for manual verification
            print(f"\nVerification URL: {verification_uri}")
            print(f"User Code: {user_code}")
            
            # Construct the verification URL with user code
            if "?" in verification_uri:
                full_url = f"{verification_uri}?code={user_code}"
            else:
                full_url = f"{verification_uri}?code={user_code}"
                
            print(f"Opening browser to: {full_url}")
            
            # Try to open the browser
            browser_opened = webbrowser.open(full_url)
            
            if not browser_opened:
                print("\nCould not open browser automatically.")
                print("Please manually visit the URL and enter the code:")
                print(f"URL: {verification_uri}")
                print(f"Code: {user_code}")
        except Exception as e:
            print(f"Error opening browser: {e}")
            print("\nPlease manually visit this URL and enter the code:")
            print(f"URL: {verification_uri}")
            print(f"Code: {user_code}")

    def poll_for_token(self, device_code: str, interval: int = 5) -> Optional[str]:
        """Poll for the access token."""
        start_time = time.time()
        expires_in = 900  # 15 minutes

        while time.time() - start_time < expires_in:
            try:
                response = requests.post(
                    f"{self.config.api_base_url}/api/v0.1/p/oauth/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": device_code,
                        "client_id": self.config.client_id
                    }
                )
                data = response.json()

                if "access_token" in data:
                    self.access_token = data["access_token"]
                    # Store refresh token if provided
                    self.refresh_token = data.get("refresh_token")
                    
                    # Save token with expiration and refresh token
                    self.save_token({
                        "access_token": self.access_token,
                        "refresh_token": self.refresh_token,
                        "expires_at": time.time() + data.get("expires_in", 3600)
                    })
                    return self.access_token
                elif data.get("error") == "authorization_pending":
                    time.sleep(interval)
                    continue
                elif data.get("error") == "slow_down":
                    interval = min(interval * 2, 60)
                    time.sleep(interval)
                    continue
                else:
                    print(f"Error: {data.get('error')}")
                    return None

            except Exception as e:
                print(f"Error polling for token: {e}")
                return None

        print("Device code expired")
        return None

    def authenticate(self) -> bool:
        """Main authentication method."""
        if self.load_token():
            return True

        try:
            # Start device flow
            print("Starting Seedr device authorization flow...")
            flow_data = self.start_device_flow()
            device_code = flow_data["device_code"]
            user_code = flow_data["user_code"]
            
            # Get the verification URI
            verification_uri = flow_data.get("verification_uri")
            if not verification_uri and "verification_url" in flow_data:
                verification_uri = flow_data["verification_url"]  # Some APIs use this name
                
            if not verification_uri:
                print("Error: No verification URI found in the response")
                print(f"Full response: {flow_data}")
                return False
                
            # If there's a verification_uri_complete, use that instead
            if flow_data.get("verification_uri_complete"):
                verification_uri = flow_data["verification_uri_complete"]
                user_code = ""  # No need for user code if URI is complete
            
            # Open browser for verification
            self.open_verification_url(verification_uri, user_code)
            
            # Poll for token
            interval = flow_data.get("interval", 5)
            if self.poll_for_token(device_code, interval):
                return True
                
        except Exception as e:
            print(f"Error authenticating with Seedr: {e}")
            
        return False

    def get_access_token(self) -> Optional[str]:
        """Get the current access token or None if not authenticated."""
        if not self.access_token and not self.load_token():
            return None
        return self.access_token

    def clear_token(self) -> None:
        """Clear the authentication token."""
        self.access_token = None
        self.refresh_token = None
        if os.path.exists(self.token_file):
            try:
                os.remove(self.token_file)
            except Exception as e:
                print(f"Error removing token file: {e}") 