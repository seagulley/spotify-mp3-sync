#!/usr/bin/env python3
"""
Unit tests for sync functionality
Tests playlist sync, S3 upload, and database operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from user_service import UserService
from models import User, Song, Playlist, PlaylistSong, get_session
import json
import os
from datetime import datetime, timedelta

client = TestClient(app)

class TestPlaylistSync:
    """Test playlist sync functionality"""
    
    @patch('main.spotipy.Spotify')
    @patch('main.user_service')
    @patch('main.get_session')
    @patch('main.get_user_id_from_jwt')
    def test_playlists_endpoint_syncs_to_database(self, mock_get_user_id, mock_get_session, mock_user_service, mock_spotify):
        """Test that /playlists endpoint syncs data to database"""
        # Mock authentication
        mock_get_user_id.return_value = 'test_user_123'
        
        # Mock database session and user
        mock_session = Mock()
        mock_user = Mock()
        mock_user.access_token = 'fake_access_token'
        mock_user.token_expires_at = datetime.utcnow() + timedelta(hours=1)  # Token not expired
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_session.return_value = mock_session
        
        # Mock Spotify API responses
        mock_spotify_instance = Mock()
        mock_spotify_instance.current_user.return_value = {'id': 'test_user_123'}
        mock_spotify_instance.current_user_playlists.return_value = {
            'items': [
                {'id': 'playlist1', 'name': 'My Playlist 1'},
                {'id': 'playlist2', 'name': 'My Playlist 2'}
            ]
        }
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock user service sync
        mock_user_service.sync_user_playlists.return_value = {
            'playlists_added': 2,
            'playlists_updated': 0,
            'songs_added': 5,
            'songs_removed': 0
        }
        
        response = client.get("/playlists", headers={"Authorization": "Bearer fake_jwt_token"})
        
        assert response.status_code == 200
        data = response.json()
        assert "playlists" in data
        assert data["synced"] == True
        assert len(data["playlists"]) == 2
        
        # Verify sync was called with auto_download=True
        mock_user_service.sync_user_playlists.assert_called_once_with('test_user_123', mock_spotify_instance, auto_download=True)
    
    @patch('main.spotipy.Spotify')
    @patch('main.user_service')
    @patch('main.get_session')
    @patch('main.get_user_id_from_jwt')
    def test_playlist_tracks_endpoint_syncs_to_database(self, mock_get_user_id, mock_get_session, mock_user_service, mock_spotify):
        """Test that /playlist/{id}/tracks endpoint syncs data to database"""
        # Mock authentication
        mock_get_user_id.return_value = 'test_user_123'
        
        # Mock database session and user
        mock_session = Mock()
        mock_user = Mock()
        mock_user.access_token = 'fake_access_token'
        mock_user.token_expires_at = datetime.utcnow() + timedelta(hours=1)  # Token not expired
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_session.return_value = mock_session
        
        # Mock Spotify API responses
        mock_spotify_instance = Mock()
        mock_spotify_instance.current_user.return_value = {'id': 'test_user_123'}
        mock_spotify_instance.playlist_tracks.return_value = {
            'items': [
                {
                    'track': {
                        'id': 'track1',
                        'name': 'Song 1',
                        'artists': [{'name': 'Artist 1'}]
                    }
                },
                {
                    'track': {
                        'id': 'track2', 
                        'name': 'Song 2',
                        'artists': [{'name': 'Artist 2'}]
                    }
                }
            ]
        }
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock user service sync
        mock_user_service.sync_user_playlists.return_value = {
            'playlists_added': 0,
            'playlists_updated': 1,
            'songs_added': 2,
            'songs_removed': 0
        }
        
        response = client.get("/playlist/playlist1/tracks", headers={"Authorization": "Bearer fake_jwt_token"})
        
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data
        assert data["synced"] == True
        assert len(data["tracks"]) == 2
        
        # Verify sync was called with auto_download=True
        mock_user_service.sync_user_playlists.assert_called_once_with('test_user_123', mock_spotify_instance, auto_download=True)
    
    @patch('main.spotipy.Spotify')
    @patch('main.user_service')
    @patch('main.get_session')
    @patch('main.get_user_id_from_jwt')
    def test_sync_failure_doesnt_break_endpoint(self, mock_get_user_id, mock_get_session, mock_user_service, mock_spotify):
        """Test that endpoint still works if sync fails"""
        # Mock authentication
        mock_get_user_id.return_value = 'test_user_123'
        
        # Mock database session and user
        mock_session = Mock()
        mock_user = Mock()
        mock_user.access_token = 'fake_access_token'
        mock_user.token_expires_at = datetime.utcnow() + timedelta(hours=1)  # Token not expired
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_session.return_value = mock_session
        
        # Mock Spotify API responses
        mock_spotify_instance = Mock()
        mock_spotify_instance.current_user.return_value = {'id': 'test_user_123'}
        mock_spotify_instance.current_user_playlists.return_value = {
            'items': [{'id': 'playlist1', 'name': 'My Playlist'}]
        }
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock user service sync to fail
        mock_user_service.sync_user_playlists.side_effect = Exception("Sync failed")
        
        response = client.get("/playlists", headers={"Authorization": "Bearer fake_jwt_token"})
        
        assert response.status_code == 200
        data = response.json()
        assert "playlists" in data
        assert len(data["playlists"]) == 1

class TestDownloadWithS3AndDatabase:
    """Test download endpoint with S3 upload and database storage"""
    
    @patch('main.yt_dlp.YoutubeDL')
    @patch('main.user_service')
    @patch('main.s3_client')
    @patch('main.os.path.exists')
    def test_download_uploads_to_s3_and_updates_db(self, mock_exists, mock_s3_client, mock_user_service, mock_yt_dlp):
        """Test that download endpoint uploads to S3 and updates database"""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock user service
        mock_user_service.add_song_file.return_value = True
        mock_user_service.update_last_listened.return_value = None
        
        # Mock S3 client
        mock_s3_client.upload_file.return_value = True
        mock_s3_client.generate_presigned_url.return_value = "https://example.com/presigned-url"
        
        # Create test request
        download_data = {
            "tracks": [
                {"name": "Test Song", "artist": "Test Artist"}
            ]
        }
        
        response = client.post("/download", json=download_data)
        
        assert response.status_code == 200  # Success for single download
        data = response.json()
        
        # Check if we have results or errors
        if "results" in data:
            assert len(data["results"]) == 1
            result = data["results"][0]
            assert result["name"] == "Test Song"
            assert result["artist"] == "Test Artist"
            assert "download_url" in result
        else:
            # If there are errors, check that structure
            assert "errors" in data
            assert len(data["errors"]) > 0
        
        # Verify S3 upload was attempted
        mock_user_service.add_song_file.assert_called_once()
        
        # Verify last listened was updated
        mock_user_service.update_last_listened.assert_called_once()
        
        # Verify S3 client was called
        mock_s3_client.generate_presigned_url.assert_called_once()
    
    @patch('main.yt_dlp.YoutubeDL')
    @patch('main.user_service')
    def test_download_handles_s3_upload_failure(self, mock_user_service, mock_yt_dlp):
        """Test that download endpoint handles S3 upload failures gracefully"""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
        
        # Mock user service to fail
        mock_user_service.add_song_file.return_value = False
        
        # Create test request
        download_data = {
            "tracks": [
                {"name": "Test Song", "artist": "Test Artist"}
            ]
        }
        
        response = client.post("/download", json=download_data)
        
        assert response.status_code == 207
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
    
    @patch('main.yt_dlp.YoutubeDL')
    @patch('main.user_service')
    def test_download_handles_yt_dlp_failure(self, mock_user_service, mock_yt_dlp):
        """Test that download endpoint handles yt-dlp failures gracefully"""
        # Mock yt-dlp to fail
        mock_yt_dlp.return_value.__enter__.side_effect = Exception("Download failed")
        
        # Create test request
        download_data = {
            "tracks": [
                {"name": "Test Song", "artist": "Test Artist"}
            ]
        }
        
        response = client.post("/download", json=download_data)
        
        assert response.status_code == 207
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0

class TestUserService:
    """Test UserService methods"""
    
    @patch('user_service.get_session')
    def test_auto_download_playlist_songs(self, mock_get_session):
        """Test auto-download functionality"""
        user_service = UserService()
        
        # Mock session and songs
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        
        mock_song = Mock()
        mock_song.id = 'song123'
        mock_song.name = 'Test Song'
        mock_song.artist = 'Test Artist'
        mock_song.s3_key = ''  # No S3 file yet
        
        mock_playlist = Mock()
        mock_playlist.name = 'Test Playlist'
        
        # Mock query to return songs to download
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = [mock_song]
        mock_session.query.return_value = mock_query
        
        changes = {'songs_downloaded': 0}
        
        with patch.object(user_service, '_download_and_upload_directly', return_value=True):
            user_service._auto_download_playlist_songs(mock_session, mock_playlist, 'user123', changes)
            
            assert changes['songs_downloaded'] == 1
            user_service._download_and_upload_directly.assert_called_once()
    
    @patch('user_service.get_session')
    def test_auto_download_playlist_songs(self, mock_get_session):
        """Test auto-download functionality"""
        user_service = UserService()
        
        # Mock session and songs
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        
        mock_song = Mock()
        mock_song.id = 'song123'
        mock_song.name = 'Test Song'
        mock_song.artist = 'Test Artist'
        mock_song.s3_key = ''  # No S3 file yet
        
        mock_playlist = Mock()
        mock_playlist.name = 'Test Playlist'
        
        # Mock query to return songs to download
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = [mock_song]
        mock_session.query.return_value = mock_query
        
        changes = {'songs_downloaded': 0}
        
        with patch.object(user_service, '_download_and_upload_directly', return_value=True):
            user_service._auto_download_playlist_songs(mock_session, mock_playlist, 'user123', changes)
            
            assert changes['songs_downloaded'] == 1
            user_service._download_and_upload_directly.assert_called_once()
    
    @patch('user_service.get_session')
    def test_get_or_create_user_creates_new_user(self, mock_get_session):
        """Test creating a new user"""
        # Mock session
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        # Mock user object
        mock_user = Mock()
        mock_user.id = "test_user_123"
        mock_user.display_name = "Test User"
        
        # Create service and test
        service = UserService()
        result = service.get_or_create_user("test_user_123", "Test User", "test@example.com")
        
        # Verify user was added to session
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
    
    @patch('user_service.get_session')
    def test_get_or_create_user_returns_existing_user(self, mock_get_session):
        """Test returning existing user"""
        # Mock session
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        
        # Mock existing user
        mock_user = Mock()
        mock_user.id = "test_user_123"
        mock_user.display_name = "Test User"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Create service and test
        service = UserService()
        result = service.get_or_create_user("test_user_123", "Test User", "test@example.com")
        
        # Verify no new user was added
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()
    
    @patch('user_service.get_session')
    def test_update_last_listened(self, mock_get_session):
        """Test updating last_listened timestamp"""
        # Mock session
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        
        # Mock song
        mock_song = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_song
        
        # Create service and test
        service = UserService()
        service.update_last_listened("test_user_123", "test_song_123")
        
        # Verify timestamp was updated
        assert mock_song.last_listened is not None
        mock_session.commit.assert_called_once()
    
    @patch('user_service.get_session')
    def test_get_user_storage_info(self, mock_get_session):
        """Test getting user storage information"""
        # Mock session
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        
        # Mock user
        mock_user = Mock()
        mock_user.total_storage_used = 1024 * 1024 * 1024  # 1GB
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock song counts
        mock_session.query.return_value.filter.return_value.count.return_value = 10
        
        # Create service and test
        service = UserService()
        result = service.get_user_storage_info("test_user_123")
        
        assert result is not None
        assert result['total_storage_used'] == 1024 * 1024 * 1024
        assert result['storage_percentage'] == 12.5  # 1GB / 8GB * 100

def setup_fake_user_and_songs(session, user_id, num_songs, song_size=1024*1024):
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=num_songs*song_size)
    session.add(user)
    session.commit()
    now = datetime.now()
    for i in range(num_songs):
        song = Song(
            id=f"song_{i}",
            user_id=user_id,
            name=f"Song {i}",
            artist="Artist",
            s3_key=f"{user_id}/song_{i}.mp3",
            size=song_size,
            in_playlist=False,
            last_listened=now - timedelta(days=i)
        )
        session.add(song)
    session.commit()

@patch('user_service.s3_client')
def test_evict_cache_for_user_deletes_s3_and_db(mock_s3_client):
    session = get_session()
    user_id = "evict_user"
    try:
        # Clean up if exists
        session.query(Song).filter(Song.user_id == user_id).delete()
        session.query(User).filter(User.id == user_id).delete()
        session.commit()
        # Add 3 cached songs
        setup_fake_user_and_songs(session, user_id, 3, song_size=1024)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

    # Set up mock
    mock_s3_client.delete_file.return_value = True

    service = UserService()
    # Evict enough to remove 2 songs (2*1024 bytes)
    result = service.evict_cache_for_user(user_id, 2048)
    assert result is True
    # S3 delete should be called for 2 oldest songs
    assert mock_s3_client.delete_file.call_count == 2
    deleted_keys = [call.args[0] for call in mock_s3_client.delete_file.call_args_list]
    assert f"{user_id}/song_2.mp3" in deleted_keys  # oldest
    assert f"{user_id}/song_1.mp3" in deleted_keys  # next oldest
    # Only 1 song should remain in DB
    session = get_session()
    remaining = session.query(Song).filter(Song.user_id == user_id).all()
    assert len(remaining) == 1
    assert remaining[0].id == "song_0"
    # User storage should be updated
    user = session.query(User).filter(User.id == user_id).first()
    assert user.total_storage_used == 1024
    # Clean up
    session = get_session()
    try:
        session.query(Song).filter(Song.user_id == user_id).delete()
        session.query(User).filter(User.id == user_id).delete()
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

@patch('user_service.s3_client')
def test_evict_cache_not_enough_space(mock_s3_client):
    session = get_session()
    user_id = "evict_edge1"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    # Add 1 cached song (1KB)
    setup_fake_user_and_songs(session, user_id, 1, song_size=1024)
    session.close()
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    # Try to evict 2KB (not enough in cache)
    result = service.evict_cache_for_user(user_id, 2048)
    assert result is False
    # S3 delete should not be called
    assert mock_s3_client.delete_file.call_count == 0
    # Song should remain in DB
    session = get_session()
    assert session.query(Song).filter(Song.user_id == user_id).count() == 1
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_evict_cache_empty_cache(mock_s3_client):
    session = get_session()
    user_id = "evict_edge2"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=0)
    session.add(user)
    session.commit()
    session.close()
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    # Try to evict 1KB (cache is empty)
    result = service.evict_cache_for_user(user_id, 1024)
    assert result is False
    assert mock_s3_client.delete_file.call_count == 0
    session = get_session()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_evict_cache_exact_fit(mock_s3_client):
    session = get_session()
    user_id = "evict_edge3"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    setup_fake_user_and_songs(session, user_id, 2, song_size=1024)
    session.close()
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    # Evict exactly 2KB
    result = service.evict_cache_for_user(user_id, 2048)
    assert result is True
    assert mock_s3_client.delete_file.call_count == 2
    session = get_session()
    assert session.query(Song).filter(Song.user_id == user_id).count() == 0
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_evict_cache_ignores_in_playlist(mock_s3_client):
    session = get_session()
    user_id = "evict_edge4"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=2048)
    session.add(user)
    session.commit()
    now = datetime.now()
    # Add 1 cached song (1KB)
    song1 = Song(id="song_c", user_id=user_id, name="Cached Song", artist="A", s3_key=f"{user_id}/song_c.mp3", size=1024, in_playlist=False, last_listened=now)
    # Add 1 in-playlist song (1KB)
    song2 = Song(id="song_p", user_id=user_id, name="Playlist Song", artist="A", s3_key=f"{user_id}/song_p.mp3", size=1024, in_playlist=True, last_listened=now)
    session.add_all([song1, song2])
    session.commit()
    session.close()
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    # Try to evict 2KB (only 1KB in cache)
    result = service.evict_cache_for_user(user_id, 2048)
    assert result is False
    # No cached song should be deleted since not enough space can be freed
    assert mock_s3_client.delete_file.call_count == 0
    session = get_session()
    # Both songs should remain
    remaining = session.query(Song).filter(Song.user_id == user_id).all()
    assert len(remaining) == 2
    ids = {s.id for s in remaining}
    assert "song_c" in ids and "song_p" in ids
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_get_cache_stats(mock_s3_client):
    """Test cache statistics calculation"""
    session = get_session()
    user_id = "cache_stats_user"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    
    # Create user and songs with different ages
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=3072)
    session.add(user)
    session.commit()
    
    now = datetime.now()
    # Recent song (1 day ago)
    song1 = Song(id="song1", user_id=user_id, name="Recent Song", artist="A", 
                s3_key=f"{user_id}/song1.mp3", size=1024, in_playlist=False, 
                last_listened=now - timedelta(days=1))
    # Old song (10 days ago)
    song2 = Song(id="song2", user_id=user_id, name="Old Song", artist="A", 
                s3_key=f"{user_id}/song2.mp3", size=1024, in_playlist=False, 
                last_listened=now - timedelta(days=10))
    # Never listened song
    song3 = Song(id="song3", user_id=user_id, name="Never Listened", artist="A", 
                s3_key=f"{user_id}/song3.mp3", size=1024, in_playlist=False, 
                last_listened=None)
    
    session.add_all([song1, song2, song3])
    session.commit()
    session.close()
    
    service = UserService()
    stats = service.get_cache_stats(user_id)
    
    assert stats['cache_song_count'] == 3
    assert stats['cache_size_bytes'] == 3072
    assert stats['cache_size_mb'] == 3072 / (1024 * 1024)
    assert stats['avg_song_size_mb'] == 1024 / (1024 * 1024)
    assert stats['recent_songs_count'] == 1  # Only song1 is recent
    assert stats['cache_efficiency'] == 1/3  # 1 out of 3 songs are recent
    assert stats['max_cache_songs'] == 100
    assert stats['eviction_threshold'] == 0.8
    
    # Clean up
    session = get_session()
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_smart_evict_cache(mock_s3_client):
    """Test smart cache eviction with scoring"""
    session = get_session()
    user_id = "smart_evict_user"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=4096)
    session.add(user)
    session.commit()
    
    now = datetime.now()
    # Large, old song (should be evicted first)
    song1 = Song(id="song1", user_id=user_id, name="Large Old", artist="A", 
                s3_key=f"{user_id}/song1.mp3", size=2048, in_playlist=False, 
                last_listened=now - timedelta(days=30))
    # Small, recent song (should be evicted last)
    song2 = Song(id="song2", user_id=user_id, name="Small Recent", artist="A", 
                s3_key=f"{user_id}/song2.mp3", size=512, in_playlist=False, 
                last_listened=now - timedelta(days=1))
    # Never listened song (should be evicted second)
    song3 = Song(id="song3", user_id=user_id, name="Never Listened", artist="A", 
                s3_key=f"{user_id}/song3.mp3", size=1024, in_playlist=False, 
                last_listened=None)
    
    session.add_all([song1, song2, song3])
    session.commit()
    session.close()
    
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    
    # Evict 2 songs (should evict song1 and song3 based on scoring)
    result = service._smart_evict_cache(session, user_id, 2)
    
    assert result['songs_evicted'] == 2
    assert result['bytes_freed'] == 3072  # 2048 + 1024
    
    # Verify S3 deletions
    assert mock_s3_client.delete_file.call_count == 2
    deleted_keys = [call.args[0] for call in mock_s3_client.delete_file.call_args_list]
    assert f"{user_id}/song1.mp3" in deleted_keys  # Large old song
    assert f"{user_id}/song3.mp3" in deleted_keys  # Never listened song
    
    # Verify only small recent song remains
    session = get_session()
    remaining = session.query(Song).filter(Song.user_id == user_id).all()
    assert len(remaining) == 1
    assert remaining[0].id == "song2"
    
    # Clean up
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_optimize_cache_for_user_size_limit(mock_s3_client):
    """Test cache optimization when cache exceeds size limit"""
    session = get_session()
    user_id = "optimize_size_user"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=102400)
    session.add(user)
    session.commit()
    
    # Create more than max_cache_songs (100) songs
    now = datetime.now()
    songs = []
    for i in range(105):  # 5 over the limit
        song = Song(id=f"song{i}", user_id=user_id, name=f"Song {i}", artist="A", 
                   s3_key=f"{user_id}/song{i}.mp3", size=1024, in_playlist=False, 
                   last_listened=now - timedelta(days=i))
        songs.append(song)
    
    session.add_all(songs)
    session.commit()
    session.close()
    
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    
    result = service.optimize_cache_for_user(user_id)
    
    assert result['songs_evicted'] == 5
    assert result['reason'] == 'cache_size_limit'
    
    # Verify 5 songs were deleted from S3
    assert mock_s3_client.delete_file.call_count == 5
    
    # Clean up
    session = get_session()
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_optimize_cache_for_user_low_efficiency(mock_s3_client):
    """Test cache optimization when cache efficiency is low"""
    session = get_session()
    user_id = "optimize_efficiency_user"
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=10240)
    session.add(user)
    session.commit()
    
    now = datetime.now()
    # Create 10 songs, only 2 recent (20% efficiency, below 30% threshold)
    songs = []
    for i in range(10):
        if i < 2:
            # Recent songs
            last_listened = now - timedelta(days=1)
        else:
            # Old songs
            last_listened = now - timedelta(days=30)
        
        song = Song(id=f"song{i}", user_id=user_id, name=f"Song {i}", artist="A", 
                   s3_key=f"{user_id}/song{i}.mp3", size=1024, in_playlist=False, 
                   last_listened=last_listened)
        songs.append(song)
    
    session.add_all(songs)
    session.commit()
    session.close()
    
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    
    result = service.optimize_cache_for_user(user_id)
    
    # Should evict 20% of songs (2 out of 10)
    assert result['songs_evicted'] == 2
    assert result['reason'] == 'low_efficiency'
    
    # Clean up
    session = get_session()
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

@patch('user_service.s3_client')
def test_invalidate_cache_for_playlist(mock_s3_client):
    """Test cache invalidation when songs are removed from playlist"""
    session = get_session()
    user_id = "invalidate_user"
    playlist_id = "playlist1"
    
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(PlaylistSong).filter(PlaylistSong.playlist_id == playlist_id).delete()
    session.query(Playlist).filter(Playlist.id == playlist_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    
    # Create user and playlist
    user = User(id=user_id, display_name="Test User", email="test@example.com", total_storage_used=2048)
    playlist = Playlist(id=playlist_id, user_id=user_id, name="Test Playlist", description="Test")
    session.add_all([user, playlist])
    session.commit()
    
    # Create songs in playlist
    song1 = Song(id="song1", user_id=user_id, name="Song 1", artist="A", 
                s3_key=f"{user_id}/song1.mp3", size=1024, in_playlist=True)
    song2 = Song(id="song2", user_id=user_id, name="Song 2", artist="A", 
                s3_key=f"{user_id}/song2.mp3", size=1024, in_playlist=True)
    
    # Create playlist-song relationships
    ps1 = PlaylistSong(playlist_id=playlist_id, song_id="song1")
    ps2 = PlaylistSong(playlist_id=playlist_id, song_id="song2")
    
    session.add_all([song1, song2, ps1, ps2])
    session.commit()
    
    # Now remove song2 from playlist (simulate playlist update)
    session.delete(ps2)
    session.commit()
    
    # Move song2 to cache
    song2.in_playlist = False
    session.commit()
    session.close()
    
    mock_s3_client.delete_file.return_value = True
    service = UserService()
    
    # Invalidate cache - should remove song2 from cache
    result = service.invalidate_cache_for_playlist(user_id, playlist_id)
    
    assert result == 1  # 1 song removed from cache
    
    # Verify S3 deletion
    assert mock_s3_client.delete_file.call_count == 1
    mock_s3_client.delete_file.assert_called_with(f"{user_id}/song2.mp3")
    
    # Clean up
    session = get_session()
    session.query(Song).filter(Song.user_id == user_id).delete()
    session.query(PlaylistSong).filter(PlaylistSong.playlist_id == playlist_id).delete()
    session.query(Playlist).filter(Playlist.id == playlist_id).delete()
    session.query(User).filter(User.id == user_id).delete()
    session.commit()
    session.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 