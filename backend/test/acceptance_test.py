#!/usr/bin/env python3
"""
Acceptance tests for Spotify MP3 Sync app.
Run this after manually logging in to your app via browser.
"""

import requests
import zipfile
import io
import time

# Configuration
BASE_URL = "http://127.0.0.1:8000"
SESSION = requests.Session()

def test_playlist_fetching():
    """Test that we can fetch playlists from Spotify"""
    print("🔍 Testing playlist fetching...")
    response = SESSION.get(f"{BASE_URL}/playlists")
    if response.status_code == 401:
        print("❌ Not authenticated. Please log in manually first:")
        print(f"   Visit: {BASE_URL}/login")
        print("   Then run this script again.")
        return False
    assert response.status_code == 200, f"Expected 200 got {response.status_code}"
    playlists = response.json()["playlists"]
    print(f"✅ Found {len(playlists)} playlists")
    for i, playlist in enumerate(playlists[:3]):
        print(f"   {i+1}. {playlist['name']} (ID: {playlist['id']})")
    return playlists

def test_track_fetching(playlists):
    """Test that we can fetch tracks from a playlist"""
    print("\n🎵 Testing track fetching...")
    if not playlists:
        print("❌ No playlists available")
        return None
    playlist = playlists[0]
    playlist_id = playlist["id"]
    response = SESSION.get(f"{BASE_URL}/playlist/{playlist_id}/tracks")
    assert response.status_code == 200, f"Expected 200 got {response.status_code}"
    tracks = response.json()["tracks"]
    print(f"✅ Found {len(tracks)} tracks in {playlist['name']}")
    for i, track in enumerate(tracks[:3]):
        print(f"   {i+1}. {track['name']} - {track['artist']}")
    return tracks

def test_download_workflow(tracks):
    """Test the full download workflow"""
    print("\n📥 Testing download workflow...")
    if not tracks:
        print("❌ No tracks available")
        return False
    test_tracks = tracks[:2]
    print(f"Testing download with {len(test_tracks)} tracks...")
    download_data = {
        "tracks": [
            {"name": track["name"], "artist": track["artist"]}
            for track in test_tracks
        ]
    }
    print("Starting download...")
    start_time = time.time()
    response = SESSION.post(f"{BASE_URL}/download", json=download_data)
    download_time = time.time() - start_time

    print("DEBUGGING")
    print("headers",response.request.headers)
    print("body",response.request.body)
    print("url",response.request.url)
    print("method",response.request.method)
    print("status_code",response.status_code)

    print(f"Download completed in {download_time:.1f} seconds")
    assert response.status_code == 200, f"Expected 200 got {response.status_code}"
    assert "application/zip" in response.headers.get("Content-Type", ""), "Expected ZIP file"
    print("Inspecting downloaded ZIP file...")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        file_names = zf.namelist()
        print(f"✅ ZIP contains {len(file_names)} files:")
        for file_name in file_names:
            print(f"   📁 {file_name}")
        for track in test_tracks:
            expected_filename = f"{track['name']} - {track['artist']}.mp3"
            found = any(expected_filename in name for name in file_names)
            if found:
                print(f"   ✅ Found: {expected_filename}")
            else:
                print(f"   ❌ Missing: {expected_filename}")
    return True

def main():
    print("🚀 Starting Spotify MP3 Sync Acceptance Tests")
    print("=" * 50)
    try:
        playlists = test_playlist_fetching()
        if not playlists:
            return
        tracks = test_track_fetching(playlists)
        if not tracks:
            return
        success = test_download_workflow(tracks)
        if success:
            print("\n🎉 All acceptance tests passed!")
        else:
            print("\n❌ Some tests failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 