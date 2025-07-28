import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from main import app




client = TestClient(app)

class TestSpotifyOAuth:
    """Test Spotify OAuth endpoints"""
    
    def test_login_redirects_to_spotify(self):
        """Test that /login redirects to Spotify OAuth URL"""
        with patch('main.SpotifyOAuth') as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.get_authorize_url.return_value = "https://accounts.spotify.com/authorize?client_id=test"
            mock_oauth.return_value = mock_instance
            
            response = client.get("/login", follow_redirects=False)
            
            assert response.status_code == 307
            assert "accounts.spotify.com" in response.headers["location"]
    
    def test_callback_without_code_returns_error(self):
        """Test that /callback returns error when no code provided"""
        response = client.get("/callback")
        
        assert response.status_code == 400
        assert response.json()["error"] == "No code provided"
    
    def test_callback_with_invalid_code_returns_error(self):
        """Test that /callback returns error when code is invalid"""
        with patch('main.SpotifyOAuth') as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.get_access_token.return_value = None
            mock_oauth.return_value = mock_instance
            
            response = client.get("/callback?code=invalid_code")
            
            assert response.status_code == 400
            assert response.json()["error"] == "Failed to get access token"
    
    def test_callback_with_valid_code_stores_token(self):
        """Test that /callback stores access token when code is valid"""
        with patch('main.SpotifyOAuth') as mock_oauth, patch('main.spotipy.Spotify') as mock_spotify:
            mock_oauth_instance = MagicMock()
            mock_oauth_instance.get_access_token.return_value = {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600
            }
            mock_oauth.return_value = mock_oauth_instance
            
            # Mock Spotify client
            mock_spotify_instance = MagicMock()
            mock_spotify_instance.current_user.return_value = {
                "id": "test_user_123",
                "display_name": "Test User",
                "email": "test@example.com"
            }
            mock_spotify.return_value = mock_spotify_instance
            
            response = client.get("/callback?code=valid_code", follow_redirects=False)
            
            assert response.status_code == 307  # Redirect to frontend

class TestDownloadEndpoint:
    """Test download endpoint functionality"""
    
    @patch('main.tempfile.mkdtemp')
    @patch('main.yt_dlp.YoutubeDL')
    @patch('main.user_service')
    def test_download_uses_tempfile(self, mock_user_service, mock_yt_dlp, mock_mkdtemp):
        """Test that download endpoint uses tempfile.mkdtemp()"""
        # Mock tempfile
        mock_mkdtemp.return_value = "/tmp/test_download_dir"
        
        # Mock yt-dlp
        mock_ydl_instance = Mock()
        mock_yt_dlp.return_value.__enter__.return_value = mock_ydl_instance
        
        # Mock user service
        mock_user_service.add_song_file.return_value = True
        
        # Test data
        download_data = {
            "tracks": [
                {"name": "Test Song", "artist": "Test Artist"}
            ]
        }
        
        response = client.post("/download", json=download_data)
        
        # Verify tempfile.mkdtemp was called
        mock_mkdtemp.assert_called_once()
        
        # Verify yt-dlp was called
        mock_ydl_instance.download.assert_called_once()

class TestPlaylistEndpoints:
    """Test playlist and track endpoints"""
    
    def test_playlists_without_auth_returns_error(self):
        """Test that /playlists returns error when user not authenticated"""
        response = client.get("/playlists")
        
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"
    
    @patch('main.get_user_id_from_jwt')
    @patch('main.get_session')
    def test_playlists_with_auth_returns_playlists(self, mock_get_session, mock_get_user_id):
        """Test that /playlists returns playlists when authenticated"""
        # Mock authentication
        mock_get_user_id.return_value = 'test_user_123'
        
        # Mock database session and user
        mock_session = Mock()
        mock_user = Mock()
        mock_user.access_token = 'fake_access_token'
        mock_user.token_expires_at = datetime.utcnow() + timedelta(hours=1)  # Token not expired
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_session.return_value = mock_session
        
        with patch('main.spotipy.Spotify') as mock_spotify:
            mock_instance = MagicMock()
            mock_instance.current_user.return_value = {'id': 'test_user_123'}
            mock_instance.current_user_playlists.return_value = {
                "items": [
                    {"id": "playlist1", "name": "My Playlist 1"},
                    {"id": "playlist2", "name": "My Playlist 2"}
                ]
            }
            mock_spotify.return_value = mock_instance
            
            response = client.get("/playlists", headers={"Authorization": "Bearer fake_jwt_token"})
            
            assert response.status_code == 200
            playlists = response.json()["playlists"]
            assert len(playlists) == 2
            assert playlists[0]["id"] == "playlist1"
            assert playlists[0]["name"] == "My Playlist 1"
    
    def test_tracks_without_auth_returns_error(self):
        """Test that /playlist/{id}/tracks returns error when user not authenticated"""
        response = client.get("/playlist/test_playlist_id/tracks")
        
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"
    
    @patch('main.get_user_id_from_jwt')
    @patch('main.get_session')
    def test_tracks_with_auth_returns_tracks(self, mock_get_session, mock_get_user_id):
        """Test that /playlist/{id}/tracks returns tracks when authenticated"""
        # Mock authentication
        mock_get_user_id.return_value = 'test_user_123'
        
        # Mock database session and user
        mock_session = Mock()
        mock_user = Mock()
        mock_user.access_token = 'fake_access_token'
        mock_user.token_expires_at = datetime.utcnow() + timedelta(hours=1)  # Token not expired
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_session.return_value = mock_session
        
        with patch('main.spotipy.Spotify') as mock_spotify:
            mock_instance = MagicMock()
            mock_instance.current_user.return_value = {'id': 'test_user_123'}
            mock_instance.playlist_tracks.return_value = {
                "items": [
                    {
                        "track": {
                            "id": "track1",
                            "name": "Test Song 1",
                            "artists": [{"name": "Test Artist 1"}]
                        }
                    },
                    {
                        "track": {
                            "id": "track2", 
                            "name": "Test Song 2",
                            "artists": [{"name": "Test Artist 2"}]
                        }
                    }
                ]
            }
            mock_spotify.return_value = mock_instance
            
            response = client.get("/playlist/test_playlist_id/tracks", headers={"Authorization": "Bearer fake_jwt_token"})
            
            assert response.status_code == 200
            tracks = response.json()["tracks"]
            assert len(tracks) == 2
            assert tracks[0]["id"] == "track1"
            assert tracks[0]["name"] == "Test Song 1"
            assert tracks[0]["artist"] == "Test Artist 1"

if __name__ == "__main__":
    pytest.main([__file__]) 