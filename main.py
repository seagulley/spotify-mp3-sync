import os
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pydantic import BaseModel
from typing import List
import yt_dlp
import zipfile
import uuid

load_dotenv()

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SCOPE = "playlist-read-private playlist-read-collaborative"

app = FastAPI(debug=True)

# In-memory store for the access token (for demo purposes only)
user_token = {"access_token": None}

@app.get("/login")
def login():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE
    )
    auth_url = sp_oauth.get_authorize_url()
    return RedirectResponse(auth_url)

@app.get("/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No code provided"}, status_code=400)
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE
    )
    token_info = sp_oauth.get_access_token(code)
    if not token_info or "access_token" not in token_info:
        return JSONResponse({"error": "Failed to get access token"}, status_code=400)
    # Store the access token in memory
    user_token["access_token"] = token_info["access_token"]
    return JSONResponse({"message": "Authentication successful! You can now fetch playlists."})

@app.get("/playlists")
def get_playlists():
    access_token = user_token.get("access_token")
    if not access_token:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    sp = spotipy.Spotify(auth=access_token)
    playlists = sp.current_user_playlists()
    # Return simplified playlist info
    result = [
        {"id": pl["id"], "name": pl["name"]}
        for pl in playlists["items"]
    ]
    return {"playlists": result}

@app.get("/playlist/{playlist_id}/tracks")
def get_tracks(playlist_id: str):
    access_token = user_token.get("access_token")
    if not access_token:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    sp = spotipy.Spotify(auth=access_token)
    tracks = sp.playlist_tracks(playlist_id)
    # Return simplified track info
    result = [
        {
            "id": t["track"]["id"],
            "name": t["track"]["name"],
            "artist": t["track"]["artists"][0]["name"]
        }
        for t in tracks["items"]
    ]
    return {"tracks": result}

# --- YouTube Download and ZIP Endpoint ---
class Track(BaseModel):
    name: str
    artist: str

class DownloadRequest(BaseModel):
    tracks: List[Track]

@app.post("/download")
def download_tracks(request: DownloadRequest, background_tasks: BackgroundTasks):
    # 1. Create a unique temp directory for this download
    download_id = str(uuid.uuid4())
    temp_dir = f"downloads/{download_id}"
    os.makedirs(temp_dir, exist_ok=True)

    mp3_files = []
    for track in request.tracks:
        query = f"{track.name} {track.artist}"
        output_path = os.path.join(temp_dir, f"{track.name} - {track.artist}.mp3")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search and download the first result
            ydl.download([f"ytsearch1:{query}"])
        mp3_files.append(output_path)

    # 2. Zip the MP3 files
    zip_path = f"{temp_dir}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for mp3 in mp3_files:
            zipf.write(mp3, os.path.basename(mp3))

    # 3. Optionally, clean up the temp_dir after download
    background_tasks.add_task(lambda: os.system(f"rm -rf {temp_dir}"))

    # 4. Return the ZIP file as a download
    return FileResponse(zip_path, filename="playlist.zip", media_type="application/zip") 