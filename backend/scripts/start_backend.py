#!/usr/bin/env python3
"""
Startup script for Spotify MP3 Sync Backend
Automatically sets up localtunnel and starts the backend
"""

import subprocess
import time
import json
import requests
import os
import sys
from pathlib import Path

def get_localtunnel_url():
    """Get the localtunnel URL from the API"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        if response.status_code == 200:
            tunnels = response.json()["tunnels"]
            # Find the HTTPS tunnel
            for tunnel in tunnels:
                if tunnel["proto"] == "https":
                    return tunnel["public_url"]
    except:
        pass
    return "https://spotisync.loca.lt"

def update_backend_urls(https_url):
    """Update the backend URLs in main.py"""
    main_py_path = Path("backend/main.py")
    
    if not main_py_path.exists():
        print("❌ backend/main.py not found!")
        return False
    
    # Read the current file
    with open(main_py_path, 'r') as f:
        content = f.read()
    
    # Update the URLs
    new_content = content.replace(
        'DYNAMIC_REDIRECT_URI = "https://spotisync.loca.lt/callback"',
        f'DYNAMIC_REDIRECT_URI = "{https_url}/callback"'
    ).replace(
        'BASE_URL = "https://spotisync.loca.lt"',
        f'BASE_URL = "{https_url}"'
    )
    
    # Write back
    with open(main_py_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Updated backend URLs to use: {https_url}")
    return True

def update_frontend_urls(https_url):
    """Update the frontend URLs"""
    files_to_update = [
        "frontend/hooks/useAuth.ts",
        "frontend/app/(tabs)/index.tsx"
    ]
    
    for file_path in files_to_update:
        path = Path(file_path)
        if not path.exists():
            print(f"⚠️  {file_path} not found, skipping...")
            continue
        
        with open(path, 'r') as f:
            content = f.read()
        
        # Replace the old URL with the new one
        new_content = content.replace(
            'const BACKEND_URL = \'https://spotisync.loca.lt\';',
            f'const BACKEND_URL = \'{https_url}\';'
        )
        
        with open(path, 'w') as f:
            f.write(new_content)
        
        print(f"✅ Updated {file_path}")

def main():
    print("🚀 Starting Spotify MP3 Sync Backend...")
    
    # Kill any existing processes
    print("🔄 Cleaning up existing processes...")
    subprocess.run(["pkill", "-f", "uvicorn main:app"], capture_output=True)
    subprocess.run(["pkill", "-f", "lt --port 8000"], capture_output=True)
    
    # Start localtunnel with custom subdomain
    print("🌐 Starting localtunnel with custom subdomain...")
    lt_process = subprocess.Popen(
        ["lt", "--port", "8000", "--subdomain", "spotisync"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for localtunnel to start and get URL
    print("⏳ Waiting for localtunnel to start...")
    time.sleep(5)
    
    https_url = get_localtunnel_url()
    print(f"✅ LocalTunnel URL: {https_url}")
    
    # Update backend and frontend URLs
    if not update_backend_urls(https_url):
        return
    
    update_frontend_urls(https_url)
    
    # Start the backend
    print("🔧 Starting backend...")
    backend_process = subprocess.Popen(
        ["cd", "backend", "&&", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        shell=True
    )
    
    print("\n🎉 Setup complete!")
    print(f"📱 Backend URL: {https_url}")
    print(f"🔗 Spotify Redirect URI: {https_url}/callback")
    print("\n⚠️  Don't forget to add the redirect URI to your Spotify app!")
    print("   Go to: https://developer.spotify.com/dashboard")
    print(f"   Add: {https_url}/callback")
    
    try:
        # Keep the script running
        backend_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        lt_process.terminate()
        backend_process.terminate()

if __name__ == "__main__":
    main() 