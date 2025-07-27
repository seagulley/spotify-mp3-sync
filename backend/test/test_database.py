#!/usr/bin/env python3
"""
Test script to verify database setup and basic functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import create_tables, get_session, User, Song, Playlist
from user_service import user_service

def test_database_creation():
    """Test that we can create tables and add basic data"""
    print("🔧 Creating database tables...")
    create_tables()
    print("✅ Tables created successfully!")
    
    # Test adding a user
    session = get_session()
    try:
        # Create test user
        test_user = User(
            id="test_user_123",
            display_name="Test User",
            email="test@example.com",
            total_storage_used=0
        )
        session.add(test_user)
        session.commit()
        print("✅ Test user created successfully!")
        
        # Create test playlist
        test_playlist = Playlist(
            id="test_playlist_123",
            user_id="test_user_123",
            name="Test Playlist",
            description="A test playlist"
        )
        session.add(test_playlist)
        session.commit()
        print("✅ Test playlist created successfully!")
        
        # Create test song
        test_song = Song(
            id="test_song_123",
            user_id="test_user_123",
            name="Test Song",
            artist="Test Artist",
            s3_key="test/song.mp3",
            size=1024000,  # 1MB
            in_playlist=True
        )
        session.add(test_song)
        session.commit()
        print("✅ Test song created successfully!")
        
        # Query and verify
        user = session.query(User).filter(User.id == "test_user_123").first()
        print(f"📊 User storage: {user.total_storage_used} bytes")
        
        playlists = session.query(Playlist).filter(Playlist.user_id == "test_user_123").all()
        print(f"📋 Found {len(playlists)} playlists")
        
        songs = session.query(Song).filter(Song.user_id == "test_user_123").all()
        print(f"🎵 Found {len(songs)} songs")
        
        print("✅ All database operations successful!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

def test_user_service():
    """Test the user service functionality"""
    print("\n🧪 Testing user service...")
    
    # Test user creation
    user = user_service.get_or_create_user(
        spotify_user_id="service_test_user",
        display_name="Service Test User",
        email="service@example.com"
    )
    print(f"✅ User service created user: {user.display_name}")
    
    # Test storage info
    storage_info = user_service.get_user_storage_info("service_test_user")
    if storage_info:
        print(f"📊 Storage info: {storage_info['storage_percentage']:.1f}% used")
    else:
        print("❌ Could not get storage info")

if __name__ == "__main__":
    print("🚀 Testing Database Setup")
    print("=" * 40)
    
    test_database_creation()
    test_user_service()
    
    print("\n🎉 Database tests completed!") 