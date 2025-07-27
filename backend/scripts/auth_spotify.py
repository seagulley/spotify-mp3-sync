#!/usr/bin/env python3
"""
Simple script to authenticate with Spotify and get an access token.
This avoids the port conflict issues with the OAuth flow.
"""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv(".env")

def authenticate_spotify():
    """Authenticate with Spotify and cache the token"""
    try:
        print("Authenticating with Spotify...")
        print("This will open a browser window for you to log in.")
        print("If the browser doesn't open, check the terminal for a URL to visit.")
        
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri="http://localhost:8889/callback",  # Use different port
            scope="playlist-modify-public playlist-read-private",
            cache_path=".spotify_cache"
        ))
        
        # Test the authentication
        user = sp.current_user()
        print(f"✅ Successfully authenticated as: {user['display_name']} ({user['id']})")
        print("Token has been cached in .spotify_cache")
        
        return True
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your .env file has SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI")
        print("2. Make sure port 8888 is not in use")
        print("3. Try running: lsof -i :8888 && kill <PID>")
        return False

if __name__ == "__main__":
    authenticate_spotify() 