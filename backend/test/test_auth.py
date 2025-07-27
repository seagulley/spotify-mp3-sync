import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app, SECRET_KEY
import jwt
from datetime import datetime, timedelta
import json

client = TestClient(app)

class TestJWTAuth:
    def setup_method(self):
        self.user_id = "test_user_123"
        self.display_name = "Test User"
        self.email = "test@example.com"
        self.access_token = "valid_access_token"
        self.refresh_token = "valid_refresh_token"
        self.expired_access_token = "expired_access_token"
        self.token_expires_at = datetime.utcnow() - timedelta(seconds=10)  # expired
        self.valid_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.jwt_token = jwt.encode({"user_id": self.user_id, "exp": datetime.utcnow() + timedelta(days=7)}, SECRET_KEY, algorithm="HS256")
        self.invalid_jwt = "invalid.jwt.token"

    @patch("main.SpotifyOAuth")
    @patch("main.spotipy.Spotify")
    @patch("main.get_session")
    def test_callback_returns_jwt(self, mock_get_session, mock_spotify, mock_oauth):
        # Mock token exchange
        mock_oauth.return_value.get_access_token.return_value = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": 3600
        }
        # Mock user info
        mock_spotify.return_value.current_user.return_value = {
            "id": self.user_id,
            "display_name": self.display_name,
            "email": self.email
        }
        # Mock DB session
        mock_db = MagicMock()
        mock_get_session.return_value = mock_db
        response = client.get("/callback?code=valid_code")
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        decoded = jwt.decode(data["token"], SECRET_KEY, algorithms=["HS256"])
        assert decoded["user_id"] == self.user_id

    def test_playlists_requires_jwt(self):
        response = client.get("/playlists")
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    def test_playlists_invalid_jwt(self):
        response = client.get("/playlists", headers={"Authorization": f"Bearer {self.invalid_jwt}"})
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    @patch("main.spotipy.Spotify")
    def test_playlists_valid_jwt_and_token(self, mock_spotify, mock_get_session):
        # Mock DB user with valid token
        mock_user = MagicMock()
        mock_user.access_token = self.access_token
        mock_user.token_expires_at = self.valid_token_expires_at
        mock_user.refresh_token = self.refresh_token
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_user
        # Mock Spotify
        mock_spotify.return_value.current_user.return_value = {"id": self.user_id}
        mock_spotify.return_value.current_user_playlists.return_value = {"items": []}
        response = client.get("/playlists", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        assert "playlists" in response.json()

    @patch("main.get_session")
    @patch("main.spotipy.Spotify")
    @patch("main.SpotifyOAuth")
    def test_playlists_expired_token_refresh_success(self, mock_oauth, mock_spotify, mock_get_session):
        # Mock DB user with expired token
        mock_user = MagicMock()
        mock_user.access_token = self.expired_access_token
        mock_user.token_expires_at = self.token_expires_at
        mock_user.refresh_token = self.refresh_token
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_user
        # Mock token refresh
        mock_oauth.return_value.refresh_access_token.return_value = {
            "access_token": self.access_token,
            "expires_in": 3600
        }
        # Mock Spotify
        mock_spotify.return_value.current_user.return_value = {"id": self.user_id}
        mock_spotify.return_value.current_user_playlists.return_value = {"items": []}
        response = client.get("/playlists", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        assert "playlists" in response.json()

    @patch("main.get_session")
    @patch("main.SpotifyOAuth")
    def test_playlists_expired_token_refresh_fail(self, mock_oauth, mock_get_session):
        # Mock DB user with expired token
        mock_user = MagicMock()
        mock_user.access_token = self.expired_access_token
        mock_user.token_expires_at = self.token_expires_at
        mock_user.refresh_token = self.refresh_token
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_user
        # Mock token refresh failure
        mock_oauth.return_value.refresh_access_token.side_effect = Exception("refresh failed")
        response = client.get("/playlists", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 401
        assert "Session expired" in response.json()["error"]

    @patch("main.get_session")
    def test_my_songs_search_requires_jwt(self, mock_get_session):
        response = client.get("/my-songs/search?q=test")
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_my_songs_search_returns_results(self, mock_get_session):
        # Mock DB to return two songs for the user
        mock_song1 = MagicMock()
        mock_song1.Song.id = "song1"
        mock_song1.Song.name = "Test Song"
        mock_song1.Song.artist = "Test Artist"
        mock_song1.Song.s3_key = "user1/test1.mp3"
        mock_song2 = MagicMock()
        mock_song2.Song.id = "song2"
        mock_song2.Song.name = "Another Song"
        mock_song2.Song.artist = "Another Artist"
        mock_song2.Song.s3_key = "user1/test2.mp3"
        mock_get_session.return_value.query.return_value.join.return_value.filter.return_value.all.return_value = [mock_song1, mock_song2]
        response = client.get("/my-songs/search?q=Song", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["name"] == "Test Song"
        assert data["results"][1]["name"] == "Another Song"

    @patch("main.get_session")
    def test_my_songs_search_filters_by_user(self, mock_get_session):
        # Mock DB to return only songs for the correct user
        mock_song = MagicMock()
        mock_song.Song.id = "song1"
        mock_song.Song.name = "User's Song"
        mock_song.Song.artist = "User Artist"
        mock_song.Song.s3_key = "user1/song.mp3"
        mock_get_session.return_value.query.return_value.join.return_value.filter.return_value.all.return_value = [mock_song]
        response = client.get("/my-songs/search?q=User", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "User's Song" 

    @patch("main.get_session")
    def test_delete_song_requires_jwt(self, mock_get_session):
        response = client.delete("/song/song1")
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_delete_song_not_found_or_not_owned(self, mock_get_session):
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = None
        response = client.delete("/song/song1", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    @patch("main.s3_client")
    @patch("main.get_session")
    def test_delete_song_success(self, mock_get_session, mock_s3_client):
        mock_song = MagicMock()
        mock_song.s3_key = "user1/song1.mp3"
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_song
        response = client.delete("/song/song1", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["message"] == "Song deleted"
        mock_s3_client.delete_object.assert_called_once_with("user1/song1.mp3")

    @patch("main.s3_client")
    @patch("main.get_session")
    def test_delete_song_s3_failure(self, mock_get_session, mock_s3_client):
        mock_song = MagicMock()
        mock_song.s3_key = "user1/song1.mp3"
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_song
        mock_s3_client.delete_object.side_effect = Exception("S3 error")
        response = client.delete("/song/song1", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 500
        assert "Failed to delete from S3" in response.json()["error"] 

    @patch("main.get_session")
    def test_get_user_profile_requires_jwt(self, mock_get_session):
        response = client.get("/user/profile")
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_get_user_profile_success(self, mock_get_session):
        mock_user = MagicMock()
        mock_user.id = self.user_id
        mock_user.display_name = self.display_name
        mock_user.email = self.email
        mock_user.created_at = "2024-01-01T00:00:00"
        mock_user.updated_at = "2024-01-02T00:00:00"
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_user
        response = client.get("/user/profile", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == self.user_id
        assert data["display_name"] == self.display_name
        assert data["email"] == self.email

    @patch("main.get_session")
    def test_get_user_profile_not_found(self, mock_get_session):
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = None
        response = client.get("/user/profile", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 404
        assert response.json()["error"] == "User not found"

    @patch("main.get_session")
    def test_get_user_storage_requires_jwt(self, mock_get_session):
        response = client.get("/user/storage")
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_get_user_storage_success(self, mock_get_session):
        mock_user = MagicMock()
        mock_user.total_storage_used = 123456
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_session.return_value.query.return_value.filter_by.return_value.count.return_value = 5
        response = client.get("/user/storage", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["total_storage_used"] == 123456
        assert data["song_count"] == 5

    @patch("main.get_session")
    def test_get_user_storage_not_found(self, mock_get_session):
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = None
        response = client.get("/user/storage", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 404
        assert response.json()["error"] == "User not found" 

    @patch("main.get_session")
    def test_create_playlist_requires_jwt(self, mock_get_session):
        response = client.post("/playlist/create", json={"name": "My Playlist"})
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_create_playlist_success(self, mock_get_session):
        mock_playlist = MagicMock()
        mock_playlist.id = "playlist1"
        mock_get_session.return_value.add.return_value = None
        mock_get_session.return_value.commit.return_value = None
        mock_get_session.return_value.refresh.return_value = None
        mock_get_session.return_value.close.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_get_session.return_value
        mock_get_session.return_value.__exit__.return_value = None
        response = client.post("/playlist/create", json={"name": "My Playlist"}, headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert "playlist_id" in response.json()

    @patch("main.get_session")
    def test_add_song_to_playlist_requires_jwt(self, mock_get_session):
        response = client.post("/playlist/playlist1/add", json={"song_id": "song1"})
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_add_song_to_playlist_success(self, mock_get_session):
        mock_playlist = MagicMock()
        mock_song = MagicMock()
        mock_get_session.return_value.query.return_value.filter_by.side_effect = [MagicMock(first=MagicMock(return_value=mock_playlist)), MagicMock(first=MagicMock(return_value=mock_song)), MagicMock(first=MagicMock(return_value=None))]
        response = client.post("/playlist/playlist1/add", json={"song_id": "song1"}, headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("main.get_session")
    def test_add_song_to_playlist_already_in_playlist(self, mock_get_session):
        mock_playlist = MagicMock()
        mock_song = MagicMock()
        # Playlist and song found, but song already in playlist
        mock_get_session.return_value.query.return_value.filter_by.side_effect = [MagicMock(first=MagicMock(return_value=mock_playlist)), MagicMock(first=MagicMock(return_value=mock_song)), MagicMock(first=MagicMock(return_value=MagicMock()))]
        response = client.post("/playlist/playlist1/add", json={"song_id": "song1"}, headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 400
        assert "already in playlist" in response.json()["error"]

    @patch("main.get_session")
    def test_remove_song_from_playlist_requires_jwt(self, mock_get_session):
        response = client.request(
            "DELETE",
            "/playlist/playlist1/remove",
            data=json.dumps({"song_id": "song1"}),
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_remove_song_from_playlist_success(self, mock_get_session):
        mock_playlist = MagicMock()
        mock_playlist_song = MagicMock()
        mock_get_session.return_value.query.return_value.filter_by.side_effect = [MagicMock(first=MagicMock(return_value=mock_playlist)), MagicMock(first=MagicMock(return_value=mock_playlist_song))]
        response = client.request(
            "DELETE",
            "/playlist/playlist1/remove",
            data=json.dumps({"song_id": "song1"}),
            headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("main.get_session")
    def test_remove_song_from_playlist_not_in_playlist(self, mock_get_session):
        mock_playlist = MagicMock()
        # Playlist found, but song not in playlist
        mock_get_session.return_value.query.return_value.filter_by.side_effect = [MagicMock(first=MagicMock(return_value=mock_playlist)), MagicMock(first=MagicMock(return_value=None))]
        response = client.request(
            "DELETE",
            "/playlist/playlist1/remove",
            data=json.dumps({"song_id": "song1"}),
            headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
        )
        assert response.status_code == 404
        assert "not in playlist" in response.json()["error"]

    @patch("main.get_session")
    def test_delete_playlist_requires_jwt(self, mock_get_session):
        response = client.delete("/playlist/playlist1")
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"

    @patch("main.get_session")
    def test_delete_playlist_success(self, mock_get_session):
        mock_playlist = MagicMock()
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = mock_playlist
        response = client.delete("/playlist/playlist1", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("main.get_session")
    def test_delete_playlist_not_found(self, mock_get_session):
        mock_get_session.return_value.query.return_value.filter_by.return_value.first.return_value = None
        response = client.delete("/playlist/playlist1", headers={"Authorization": f"Bearer {self.jwt_token}"})
        assert response.status_code == 404
        assert "not found" in response.json()["error"] 