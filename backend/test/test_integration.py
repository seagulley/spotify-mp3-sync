import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os
import json
from datetime import datetime, timedelta

from main import app
from models import Base, User, Playlist, Song, PlaylistSong, get_session
from user_service import user_service
from s3_client import s3_client


class TestIntegrationWorkflows:
    """Integration tests for complete workflows"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Create test database"""
        # Create in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        # Override the database session in the app
        app.dependency_overrides[get_session] = override_get_db
        self.client = TestClient(app)
        
        # Mock the user_token to simulate authentication
        import main
        main.user_token["access_token"] = "test_access_token"
        
        yield
        
        app.dependency_overrides.clear()
    
    @pytest.fixture
    def mock_spotify(self):
        """Mock Spotify API responses"""
        with patch('main.spotipy.Spotify') as mock_spotify_class:
            mock_spotify = Mock()
            mock_spotify_class.return_value = mock_spotify
            
            # Mock user profile
            mock_spotify.current_user.return_value = {
                'id': 'test_user_id',
                'display_name': 'Test User',
                'email': 'test@example.com'
            }
            
            # Mock playlists
            mock_spotify.current_user_playlists.return_value = {
                'items': [
                    {
                        'id': 'playlist1',
                        'name': 'My Playlist 1',
                        'description': 'Test playlist 1',
                        'tracks': {'total': 2}
                    },
                    {
                        'id': 'playlist2', 
                        'name': 'My Playlist 2',
                        'description': 'Test playlist 2',
                        'tracks': {'total': 1}
                    }
                ]
            }
            
            # Mock playlist tracks
            def get_playlist_tracks(playlist_id):
                if playlist_id == 'playlist1':
                    return {
                        'items': [
                            {
                                'track': {
                                    'id': 'track1',
                                    'name': 'Test Song 1',
                                    'artists': [{'name': 'Artist 1'}],
                                    'album': {'name': 'Album 1'},
                                    'duration_ms': 180000
                                }
                            },
                            {
                                'track': {
                                    'id': 'track2',
                                    'name': 'Test Song 2', 
                                    'artists': [{'name': 'Artist 2'}],
                                    'album': {'name': 'Album 2'},
                                    'duration_ms': 240000
                                }
                            }
                        ]
                    }
                elif playlist_id == 'playlist2':
                    return {
                        'items': [
                            {
                                'track': {
                                    'id': 'track3',
                                    'name': 'Test Song 3',
                                    'artists': [{'name': 'Artist 3'}],
                                    'album': {'name': 'Album 3'},
                                    'duration_ms': 200000
                                }
                            }
                        ]
                    }
                return {'items': []}
            
            mock_spotify.playlist_tracks.side_effect = get_playlist_tracks
            yield mock_spotify
    
    @pytest.fixture
    def mock_yt_dlp(self):
        """Mock yt-dlp download"""
        with patch('main.yt_dlp.YoutubeDL') as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl_class.return_value = mock_ydl
            
            # Mock successful download
            mock_ydl.download.return_value = 0
            mock_ydl.extract_info.return_value = {
                'title': 'Test Song',
                'duration': 180,
                'filesize': 5000000  # 5MB
            }
            
            yield mock_ydl
    
    @pytest.fixture
    def mock_s3(self):
        """Mock S3 operations"""
        with patch('s3_client.boto3.client') as mock_boto3:
            mock_s3_client = Mock()
            mock_boto3.return_value = mock_s3_client
            
            # Mock upload
            mock_s3_client.upload_file.return_value = None
            
            # Mock presigned URL generation
            mock_s3_client.generate_presigned_url.return_value = 'https://test-bucket.s3.amazonaws.com/test-song.mp3'
            
            # Mock delete
            mock_s3_client.delete_object.return_value = None
            
            yield mock_s3_client
    
    @pytest.fixture
    def mock_oauth(self):
        """Mock OAuth flow"""
        with patch('main.spotipy.SpotifyOAuth') as mock_oauth_class:
            mock_oauth = Mock()
            mock_oauth_class.return_value = mock_oauth
            
            # Mock successful OAuth
            mock_oauth.get_access_token.return_value = {
                'access_token': 'test_access_token',
                'refresh_token': 'test_refresh_token',
                'expires_at': int((datetime.now() + timedelta(hours=1)).timestamp())
            }
            
            yield mock_oauth
    
    def test_complete_workflow_new_user(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test complete workflow for a new user"""
        # 1. OAuth flow (using existing login endpoint)
        oauth_response = self.client.get("/login")
        assert oauth_response.status_code == 307  # Redirect status
        
        # 2. OAuth callback (using existing callback endpoint)
        callback_response = self.client.get("/callback?code=test_code")
        assert callback_response.status_code == 200
        callback_data = callback_response.json()
        assert "message" in callback_data
        
        # 3. Get playlists (this will trigger sync)
        playlists_response = self.client.get("/playlists")
        assert playlists_response.status_code == 200
        playlists_data = playlists_response.json()
        assert len(playlists_data["playlists"]) == 2
        assert playlists_data["playlists"][0]["name"] == "My Playlist 1"
        assert playlists_data["playlists"][1]["name"] == "My Playlist 2"
        
        # 4. Get playlist tracks
        tracks_response = self.client.get("/playlist/playlist1/tracks")
        assert tracks_response.status_code == 200
        tracks_data = tracks_response.json()
        assert len(tracks_data["tracks"]) == 2
        assert tracks_data["tracks"][0]["name"] == "Test Song 1"
        assert tracks_data["tracks"][1]["name"] == "Test Song 2"
        
        # 5. Download a song (using existing download endpoint structure)
        download_response = self.client.post("/download", json={
            "tracks": [
                {
                    "name": "Test Song 1",
                    "artist": "Artist 1"
                }
            ]
        })
        assert download_response.status_code == 200
        download_data = download_response.json()
        assert download_data["status"] == "success"
        assert len(download_data["songs"]) == 1
        assert "download_url" in download_data["songs"][0]
        
        # 6. Verify song is in database
        db = get_session()
        try:
            # The song ID is generated based on name-artist, not track1
            song = db.query(Song).filter(Song.name == "Test Song 1").first()
            assert song is not None
            assert song.artist == "Artist 1"
            assert song.s3_key == "test_user_123/Test Song 1 - Artist 1.mp3"
        finally:
            db.close()
    
    def test_workflow_with_cache_eviction(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test workflow that triggers cache eviction"""
        # Setup user with limited storage
        db = get_session()
        try:
            user = User(
                id="test_user_cache_eviction",  # Unique user ID for this test
                display_name="Test User",
                email="test@example.com"
            )
            db.add(user)
            
            # Add some existing songs to fill cache
            for i in range(3):
                song = Song(
                    id=f"existing_track_{i}",
                    user_id="test_user_cache_eviction",
                    name=f"Existing Song {i}",
                    artist=f"Existing Artist {i}",
                    s3_key=f"test_user_cache_eviction/existing_track_{i}.mp3",
                    size=3000000,  # 3MB each
                    last_listened=datetime.now() - timedelta(hours=i)
                )
                db.add(song)
            
            db.commit()
        finally:
            db.close()
        
        # Download a new song that will trigger eviction
        download_response = self.client.post("/download", json={
            "tracks": [
                {
                    "name": "New Song",
                    "artist": "New Artist"
                }
            ]
        })
        
        assert download_response.status_code == 200
        download_data = download_response.json()
        assert download_data["status"] == "success"
        
        # Verify cache eviction occurred
        db = get_session()
        try:
            songs = db.query(Song).filter(Song.user_id == "test_user_cache_eviction").all()
            assert len(songs) == 3  # Should have evicted oldest song
            
            # Check that the oldest song was removed
            oldest_song = db.query(Song).filter(Song.id == "existing_track_2").first()
            assert oldest_song is None
            
            # Check that new song was added
            new_song = db.query(Song).filter(Song.name == "New Song").first()
            assert new_song is not None
        finally:
            db.close()
    
    def test_workflow_playlist_sync_updates(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test that playlist sync updates existing data"""
        # Setup initial data
        db = get_session()
        try:
            user = User(
                id="test_user_sync_updates",
                display_name="Test User",
                email="test@example.com"
            )
            db.add(user)
            
            # Add existing playlist with old data
            playlist = Playlist(
                id="playlist1",
                name="Old Playlist Name",
                description="Old description",
                user_id="test_user_sync_updates"
            )
            db.add(playlist)
            
            # Add existing track
            song = Song(
                id="track1",
                user_id="test_user_sync_updates",
                name="Old Song Title",
                artist="Old Artist",
                s3_key="test_user_sync_updates/track1.mp3",
                size=1000000
            )
            db.add(song)
            
            playlist_song = PlaylistSong(
                playlist_id="playlist1",
                song_id="track1"
            )
            db.add(playlist_song)
            
            db.commit()
        finally:
            db.close()
        
        # Sync playlists (should update existing data)
        sync_response = self.client.get("/playlists")
        assert sync_response.status_code == 200
        
        # Verify data was updated
        db = get_session()
        try:
            # Check playlist was updated
            playlist = db.query(Playlist).filter(Playlist.id == "playlist1").first()
            assert playlist.name == "My Playlist 1"
            assert playlist.description == "Test playlist 1"
            
            # Check song was updated
            song = db.query(Song).filter(Song.id == "track1").first()
            assert song.name == "Test Song 1"
            assert song.artist == "Artist 1"
            
            # Check new song was added
            new_song = db.query(Song).filter(Song.id == "track2").first()
            assert new_song is not None
            assert new_song.name == "Test Song 2"
        finally:
            db.close()
    
    def test_workflow_error_handling(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test workflow error handling"""
        # Mock Spotify API error
        mock_spotify.current_user_playlists.side_effect = Exception("Spotify API error")
        
        # Attempt to sync playlists
        sync_response = self.client.get("/playlists")
        assert sync_response.status_code == 500
        assert "error" in sync_response.json()
        
        # Reset mock
        mock_spotify.current_user_playlists.side_effect = None
        
        # Mock yt-dlp error
        mock_yt_dlp.download.side_effect = Exception("Download failed")
        
        # Attempt to download
        download_response = self.client.post("/download", json={
            "tracks": [
                {
                    "name": "Test Song",
                    "artist": "Test Artist"
                }
            ]
        })
        assert download_response.status_code == 500
        assert "error" in download_response.json()
        
        # Reset mock
        mock_yt_dlp.download.side_effect = None
        
        # Mock S3 error
        mock_s3.upload_file.side_effect = Exception("S3 upload failed")
        
        # Attempt to download again
        download_response = self.client.post("/download", json={
            "tracks": [
                {
                    "name": "Test Song",
                    "artist": "Test Artist"
                }
            ]
        })
        assert download_response.status_code == 500
        assert "error" in download_response.json()
    
    def test_workflow_concurrent_operations(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test concurrent operations"""
        # Setup user
        db = get_session()
        try:
            user = User(
                id="test_user_concurrent",
                display_name="Test User",
                email="test@example.com"
            )
            db.add(user)
            db.commit()
        finally:
            db.close()
        
        # Simulate concurrent playlist sync and download
        async def concurrent_operations():
            # Start playlist sync
            sync_task = asyncio.create_task(
                asyncio.to_thread(
                    self.client.get, 
                    "/playlists"
                )
            )
            
            # Start download
            download_task = asyncio.create_task(
                asyncio.to_thread(
                    self.client.post,
                    "/download",
                    json={
                        "tracks": [
                            {
                                "name": "Test Song",
                                "artist": "Test Artist"
                            }
                        ]
                    }
                )
            )
            
            # Wait for both to complete
            sync_result, download_result = await asyncio.gather(sync_task, download_task)
            
            return sync_result, download_result
        
        # Run concurrent operations
        sync_result, download_result = asyncio.run(concurrent_operations())
        
        # Both should succeed
        assert sync_result.status_code == 200
        assert download_result.status_code == 200
        
        # Verify data consistency
        db = get_session()
        try:
            # Check playlists were synced
            playlists = db.query(Playlist).filter(Playlist.user_id == "test_user_concurrent").all()
            assert len(playlists) == 2
            
            # Check song was downloaded
            song = db.query(Song).filter(Song.name == "Test Song").first()
            assert song is not None
        finally:
            db.close()
    
    def test_workflow_data_persistence(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test that data persists across requests"""
        # Setup user
        db = get_session()
        try:
            user = User(
                id="test_user_persistence",
                display_name="Test User",
                email="test@example.com"
            )
            db.add(user)
            db.commit()
        finally:
            db.close()
        
        # Sync playlists
        sync_response = self.client.get("/playlists")
        assert sync_response.status_code == 200
        
        # Download a song
        download_response = self.client.post("/download", json={
            "tracks": [
                {
                    "name": "Test Song",
                    "artist": "Test Artist"
                }
            ]
        })
        assert download_response.status_code == 200
        
        # Make another request - data should still be there
        tracks_response = self.client.get("/playlist/playlist1/tracks")
        assert tracks_response.status_code == 200
        tracks_data = tracks_response.json()
        assert len(tracks_data["tracks"]) == 2
        
        # Verify data in database
        db = get_session()
        try:
            # Check user exists
            user = db.query(User).filter(User.id == "test_user_persistence").first()
            assert user is not None
            
            # Check playlists exist
            playlists = db.query(Playlist).filter(Playlist.user_id == "test_user_persistence").all()
            assert len(playlists) == 2
            
            # Check songs exist
            songs = db.query(Song).filter(Song.user_id == "test_user_persistence").all()
            assert len(songs) >= 3  # At least 3 songs from playlists
            
            # Check downloaded song exists
            downloaded_song = db.query(Song).filter(
                Song.name == "Test Song",
                Song.s3_key.isnot(None)
            ).first()
            assert downloaded_song is not None
        finally:
            db.close()
    
    def test_workflow_cache_statistics(self, mock_spotify, mock_yt_dlp, mock_s3, mock_oauth):
        """Test cache statistics tracking"""
        # Setup user with some cached songs
        db = get_session()
        try:
            user = User(
                id="test_user_cache_stats",
                display_name="Test User",
                email="test@example.com"
            )
            db.add(user)
            
            # Add cached songs with different access patterns
            for i in range(5):
                song = Song(
                    id=f"cached_track_{i}",
                    user_id="test_user_cache_stats",
                    name=f"Cached Song {i}",
                    artist=f"Cached Artist {i}",
                    s3_key=f"test_user_cache_stats/cached_track_{i}.mp3",
                    size=1500000,  # 1.5MB each
                    last_listened=datetime.now() - timedelta(hours=i)
                )
                db.add(song)
            
            db.commit()
        finally:
            db.close()
        
        # Note: Cache statistics endpoint doesn't exist in current API
        # This test would need the endpoint to be implemented
        # For now, we'll just verify the songs exist in the database
        
        # Download another song to trigger eviction
        download_response = self.client.post("/download", json={
            "tracks": [
                {
                    "name": "New Song",
                    "artist": "New Artist"
                }
            ]
        })
        assert download_response.status_code == 200
        
        # Verify the new song was added and old song was evicted
        db = get_session()
        try:
            songs = db.query(Song).filter(Song.user_id == "test_user_cache_stats").all()
            # Should still have 5 songs (evicted one, added one)
            assert len(songs) == 5
            
            # Check that new song was added
            new_song = db.query(Song).filter(Song.name == "New Song").first()
            assert new_song is not None
        finally:
            db.close() 