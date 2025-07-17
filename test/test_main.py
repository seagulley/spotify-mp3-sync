import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
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
        with patch('main.SpotifyOAuth') as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.get_access_token.return_value = {"access_token": "test_token"}
            mock_oauth.return_value = mock_instance
            
            response = client.get("/callback?code=valid_code")
            
            assert response.status_code == 200
            assert response.json()["message"] == "Authentication successful! You can now fetch playlists."
            
            # Check that token was stored
            from main import user_token
            assert user_token["access_token"] == "test_token"

class TestPlaylistEndpoints:
    """Test playlist and track endpoints"""
    
    def test_playlists_without_auth_returns_error(self):
        """Test that /playlists returns error when user not authenticated"""
        # Reset token
        from main import user_token
        user_token["access_token"] = None
        
        response = client.get("/playlists")
        
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"
    
    def test_playlists_with_auth_returns_playlists(self):
        """Test that /playlists returns playlists when authenticated"""
        with patch('main.spotipy.Spotify') as mock_spotify:
            mock_instance = MagicMock()
            mock_instance.current_user_playlists.return_value = {
                "items": [
                    {"id": "playlist1", "name": "My Playlist 1"},
                    {"id": "playlist2", "name": "My Playlist 2"}
                ]
            }
            mock_spotify.return_value = mock_instance
            
            # Set token
            from main import user_token
            user_token["access_token"] = "test_token"
            
            response = client.get("/playlists")
            
            assert response.status_code == 200
            playlists = response.json()["playlists"]
            assert len(playlists) == 2
            assert playlists[0]["id"] == "playlist1"
            assert playlists[0]["name"] == "My Playlist 1"
    
    def test_tracks_without_auth_returns_error(self):
        """Test that /playlist/{id}/tracks returns error when user not authenticated"""
        # Reset token
        from main import user_token
        user_token["access_token"] = None
        
        response = client.get("/playlist/test_playlist_id/tracks")
        
        assert response.status_code == 401
        assert response.json()["error"] == "User not authenticated"
    
    def test_tracks_with_auth_returns_tracks(self):
        """Test that /playlist/{id}/tracks returns tracks when authenticated"""
        with patch('main.spotipy.Spotify') as mock_spotify:
            mock_instance = MagicMock()
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
            
            # Set token
            from main import user_token
            user_token["access_token"] = "test_token"
            
            response = client.get("/playlist/test_playlist_id/tracks")
            
            assert response.status_code == 200
            tracks = response.json()["tracks"]
            assert len(tracks) == 2
            assert tracks[0]["id"] == "track1"
            assert tracks[0]["name"] == "Test Song 1"
            assert tracks[0]["artist"] == "Test Artist 1"

if __name__ == "__main__":
    pytest.main([__file__]) 