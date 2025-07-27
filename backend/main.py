import os
import socket
from fastapi import FastAPI, Request, BackgroundTasks, Header, Body
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pydantic import BaseModel
from typing import List
import yt_dlp
import zipfile
import uuid
import requests
from user_service import user_service
from s3_client import s3_client
from datetime import datetime, timedelta
from models import get_session, User, Song, Playlist, PlaylistSong
import jwt
from sqlalchemy import or_
from concurrent.futures import ThreadPoolExecutor, as_completed
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_secret_key")

load_dotenv()

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SCOPE = "playlist-read-private playlist-read-collaborative"

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

# Use HTTPS tunnel for Spotify OAuth (required for production)
def get_localtunnel_url():
    """Get the current localtunnel URL"""
    try:
        import requests
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if response.status_code == 200:
            tunnels = response.json()["tunnels"]
            for tunnel in tunnels:
                if tunnel["proto"] == "https":
                    return tunnel["public_url"]
    except:
        pass
    # Fallback to the custom subdomain
    return "https://spotisync.loca.lt"

LOCALTUNNEL_URL = get_localtunnel_url()
DYNAMIC_REDIRECT_URI = f"{LOCALTUNNEL_URL}/callback"
BASE_URL = LOCALTUNNEL_URL
SESSION = requests.Session()

app = FastAPI(debug=True)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def root():
    return {"message": "Spotify MP3 Sync Backend is running!", "endpoints": ["/login", "/playlists", "/download"]}

# Store the access token (for demo purposes)
# user_token = {"access_token": None} # This line is removed as per the edit hint.

def get_user_id_from_jwt(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except Exception:
        return None

def refresh_access_token_if_needed(user, db):
    if not user.token_expires_at or user.token_expires_at > datetime.utcnow():
        return user.access_token
    # Token expired, refresh
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=DYNAMIC_REDIRECT_URI,
        scope=SCOPE
    )
    try:
        token_info = sp_oauth.refresh_access_token(user.refresh_token)
        user.access_token = token_info["access_token"]
        user.token_expires_at = datetime.utcnow() + timedelta(seconds=token_info.get("expires_in", 3600))
        db.commit()
        return user.access_token
    except Exception:
        return None

@app.get("/login")
def login():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=DYNAMIC_REDIRECT_URI,
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
        redirect_uri=DYNAMIC_REDIRECT_URI,
        scope=SCOPE
    )
    token_info = sp_oauth.get_access_token(code)
    if not token_info or "access_token" not in token_info:
        return JSONResponse({"error": "Failed to get access token"}, status_code=400)
    access_token = token_info["access_token"]
    refresh_token = token_info.get("refresh_token")
    expires_in = token_info.get("expires_in")
    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in or 3600)
    # Fetch user info from Spotify
    sp = spotipy.Spotify(auth=access_token)
    user_info = sp.current_user()
    user_id = user_info["id"]
    display_name = user_info.get("display_name", "")
    email = user_info.get("email")
    # Upsert user in DB
    db = get_session()
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        user = User(id=user_id, display_name=display_name, email=email)
        db.add(user)
    user.access_token = access_token
    user.refresh_token = refresh_token
    user.token_expires_at = token_expires_at
    user.display_name = display_name
    user.email = email
    db.commit()
    db.close()
    # Generate JWT
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)  # Token expires in 7 days
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return JSONResponse({
        "message": f"Authentication successful! Welcome, {display_name}.",
        "token": token
    })

@app.get("/playlists")
def get_playlists(authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    user = db.query(User).filter_by(id=user_id).first()
    if not user or not user.access_token:
        db.close()
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    access_token = refresh_access_token_if_needed(user, db)
    if not access_token:
        db.close()
        return JSONResponse({"error": "Session expired, please log in again."}, status_code=401)
    
    # Get Spotify user info for database sync
    sp = spotipy.Spotify(auth=access_token)
    user_info = sp.current_user()
    user_id = user_info['id']
    
    # Sync playlists to database
    try:
        changes = user_service.sync_user_playlists(user_id, sp)
        print(f"Sync changes: {changes}")
    except Exception as e:
        print(f"Error syncing playlists: {e}")
        # Continue with Spotify data even if sync fails
    
    # Get playlists from Spotify
    playlists = sp.current_user_playlists()
    result = [
        {"id": pl["id"], "name": pl["name"]}
        for pl in playlists["items"]
    ]
    db.close()
    return {"playlists": result, "synced": True}

@app.get("/playlist/{playlist_id}/tracks")
def get_tracks(playlist_id: str, authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    user = db.query(User).filter_by(id=user_id).first()
    if not user or not user.access_token:
        db.close()
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    access_token = refresh_access_token_if_needed(user, db)
    if not access_token:
        db.close()
        return JSONResponse({"error": "Session expired, please log in again."}, status_code=401)
    
    # Get Spotify user info for database sync
    sp = spotipy.Spotify(auth=access_token)
    user_info = sp.current_user()
    user_id = user_info['id']
    
    # Sync playlists to database (this will also sync tracks for all playlists)
    try:
        changes = user_service.sync_user_playlists(user_id, sp)
        print(f"Sync changes: {changes}")
    except Exception as e:
        print(f"Error syncing playlists: {e}")
        # Continue with Spotify data even if sync fails
    
    # Get tracks from Spotify
    tracks = sp.playlist_tracks(playlist_id)
    result = [
        {
            "id": t["track"]["id"],
            "name": t["track"]["name"],
            "artist": t["track"]["artists"][0]["name"]
        }
        for t in tracks["items"]
    ]
    db.close()
    return {"tracks": result, "synced": True}

# --- YouTube Download and ZIP Endpoint ---
class Track(BaseModel):
    name: str
    artist: str

class DownloadRequest(BaseModel):
    tracks: List[Track]

@app.post("/download")
def download_tracks(request: DownloadRequest, background_tasks: BackgroundTasks):
    user_id = "test_user_123"  # TODO: Replace with real user ID from auth
    download_id = str(uuid.uuid4())
    temp_dir = f"downloads/{download_id}"
    os.makedirs(temp_dir, exist_ok=True)

    # Deduplicate tracks by (name, artist)
    unique_tracks = {(t.name, t.artist): t for t in request.tracks}.values()
    results = []
    errors = []

    def process_track(track):
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
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch1:{query}"])
            s3_key = f"{user_id}/{track.name} - {track.artist}.mp3"
            song_id = f"{track.name}-{track.artist}"
            success = user_service.add_song_file(user_id, song_id, output_path, s3_key)
            if not success:
                return (track, f"Failed to upload {track.name} - {track.artist} to S3 or DB.")
            user_service.update_last_listened(user_id, song_id)
            download_url = s3_client.generate_presigned_url(s3_key)
            return (track, {
                "name": track.name,
                "artist": track.artist,
                "s3_key": s3_key,
                "download_url": download_url
            })
        except Exception as e:
            return (track, f"Error downloading/uploading {track.name} - {track.artist}: {e}")

    # Use ThreadPoolExecutor for parallel downloads
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_track = {executor.submit(process_track, track): track for track in unique_tracks}
        for future in as_completed(future_to_track):
            track, result = future.result()
            if isinstance(result, dict):
                results.append(result)
            else:
                errors.append(result)

    background_tasks.add_task(lambda: os.system(f"rm -rf {temp_dir}"))

    if errors:
        return JSONResponse({"errors": errors, "results": results}, status_code=207)

    return JSONResponse({"results": results}) 

@app.get("/my-songs/search")
def search_my_songs(q: str, authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    # Search user's cached songs by name or artist
    songs = db.query(User, Song).join(Song, Song.user_id == User.id).filter(
        User.id == user_id,
        or_(Song.name.ilike(f"%{q}%"), Song.artist.ilike(f"%{q}%")),
        Song.in_playlist == False,
        Song.s3_key != ''
    ).all()
    db.close()
    # Format results
    results = [
        {
            "id": song.Song.id,
            "name": song.Song.name,
            "artist": song.Song.artist,
            "s3_key": song.Song.s3_key
        }
        for song in songs
    ]
    return {"results": results} 

@app.delete("/song/{song_id}")
def delete_song(song_id: str, authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    song = db.query(Song).filter_by(id=song_id, user_id=user_id).first()
    if not song:
        db.close()
        return JSONResponse({"error": "Song not found or not owned by user"}, status_code=404)
    # Remove from S3
    try:
        s3_client.delete_object(song.s3_key)
    except Exception as e:
        db.close()
        return JSONResponse({"error": f"Failed to delete from S3: {e}"}, status_code=500)
    # Remove from DB
    db.delete(song)
    db.commit()
    db.close()
    return {"status": "success", "message": "Song deleted"} 

@app.post("/playlist/create")
def create_playlist(data: dict = Body(...), authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    name = data.get("name")
    description = data.get("description", "")
    if not name:
        return JSONResponse({"error": "Playlist name required"}, status_code=400)
    db = get_session()
    playlist = Playlist(user_id=user_id, name=name, description=description)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    db.close()
    return {"status": "success", "playlist_id": playlist.id}

@app.post("/playlist/{playlist_id}/add")
def add_song_to_playlist(playlist_id: str, data: dict = Body(...), authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    song_id = data.get("song_id")
    if not song_id:
        return JSONResponse({"error": "Song ID required"}, status_code=400)
    db = get_session()
    playlist = db.query(Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    song = db.query(Song).filter_by(id=song_id, user_id=user_id).first()
    if not playlist or not song:
        db.close()
        return JSONResponse({"error": "Playlist or song not found or not owned by user"}, status_code=404)
    # Add song to playlist
    if db.query(PlaylistSong).filter_by(playlist_id=playlist_id, song_id=song_id).first():
        db.close()
        return JSONResponse({"error": "Song already in playlist"}, status_code=400)
    playlist_song = PlaylistSong(playlist_id=playlist_id, song_id=song_id)
    db.add(playlist_song)
    db.commit()
    db.close()
    return {"status": "success"}

@app.delete("/playlist/{playlist_id}/remove")
def remove_song_from_playlist(playlist_id: str, data: dict = Body(...), authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    song_id = data.get("song_id")
    if not song_id:
        return JSONResponse({"error": "Song ID required"}, status_code=400)
    db = get_session()
    playlist = db.query(Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    if not playlist:
        db.close()
        return JSONResponse({"error": "Playlist not found or not owned by user"}, status_code=404)
    playlist_song = db.query(PlaylistSong).filter_by(playlist_id=playlist_id, song_id=song_id).first()
    if not playlist_song:
        db.close()
        return JSONResponse({"error": "Song not in playlist"}, status_code=404)
    db.delete(playlist_song)
    db.commit()
    db.close()
    return {"status": "success"}

@app.delete("/playlist/{playlist_id}")
def delete_playlist(playlist_id: str, authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    playlist = db.query(Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    if not playlist:
        db.close()
        return JSONResponse({"error": "Playlist not found or not owned by user"}, status_code=404)
    # Remove all playlist-song relationships
    db.query(PlaylistSong).filter_by(playlist_id=playlist_id).delete()
    db.delete(playlist)
    db.commit()
    db.close()
    return {"status": "success"}

@app.get("/user/profile")
def get_user_profile(authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    user = db.query(User).filter_by(id=user_id).first()
    db.close()
    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@app.get("/user/storage")
def get_user_storage(authorization: str = Header(None)):
    user_id = get_user_id_from_jwt(authorization)
    if not user_id:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    db = get_session()
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        db.close()
        return JSONResponse({"error": "User not found"}, status_code=404)
    # Calculate storage info
    total_storage = user.total_storage_used
    song_count = db.query(Song).filter_by(user_id=user_id).count()
    db.close()
    return {
        "total_storage_used": total_storage,
        "song_count": song_count
    } 