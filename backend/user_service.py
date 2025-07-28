from models import User, Song, Playlist, PlaylistSong, get_session
from s3_client import s3_client
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import spotipy
from sqlalchemy.orm import Session
import logging
import os

class UserService:
    """Service for managing users, playlists, and songs"""
    
    def __init__(self):
        self.max_storage_bytes = 8 * 1024 * 1024 * 1024  # 8GB
        self.max_cache_songs = 100  # Maximum number of cached songs per user
        self.cache_eviction_threshold = 0.8  # Evict when cache reaches 80% of limit
        self.cache_stats = {}  # Track cache statistics per user
    
    def get_cache_stats(self, user_id: str) -> Dict:
        """Get cache statistics for a user"""
        session = get_session()
        try:
            cache_songs = session.query(Song).filter(
                Song.user_id == user_id,
                Song.in_playlist == False,
                Song.s3_key != ''
            ).all()
            
            total_cache_size = sum(song.size for song in cache_songs)
            avg_song_size = total_cache_size / len(cache_songs) if cache_songs else 0
            
            # Calculate cache efficiency (songs with recent last_listened)
            now = datetime.now()
            recent_threshold = now - timedelta(days=7)
            recent_songs = [s for s in cache_songs if s.last_listened and s.last_listened > recent_threshold]
            
            return {
                'cache_song_count': len(cache_songs),
                'cache_size_bytes': total_cache_size,
                'cache_size_mb': total_cache_size / (1024 * 1024),
                'avg_song_size_mb': avg_song_size / (1024 * 1024),
                'recent_songs_count': len(recent_songs),
                'cache_efficiency': len(recent_songs) / len(cache_songs) if cache_songs else 0,
                'max_cache_songs': self.max_cache_songs,
                'eviction_threshold': self.cache_eviction_threshold
            }
        finally:
            session.close()
    
    def optimize_cache_for_user(self, user_id: str) -> Dict:
        """Proactively optimize cache for a user"""
        session = get_session()
        try:
            cache_stats = self.get_cache_stats(user_id)
            optimizations = {
                'songs_evicted': 0,
                'bytes_freed': 0,
                'reason': 'none'
            }
            
            # Check if cache is too large
            if cache_stats['cache_song_count'] > self.max_cache_songs:
                songs_to_evict = cache_stats['cache_song_count'] - self.max_cache_songs
                freed = self._smart_evict_cache(session, user_id, songs_to_evict)
                optimizations['songs_evicted'] = freed['songs_evicted']
                optimizations['bytes_freed'] = freed['bytes_freed']
                optimizations['reason'] = 'cache_size_limit'
            
            # Check if cache efficiency is low (too many old songs)
            elif cache_stats['cache_efficiency'] < 0.3:  # Less than 30% recent songs
                # Evict oldest 20% of songs
                songs_to_evict = max(1, int(cache_stats['cache_song_count'] * 0.2))
                freed = self._smart_evict_cache(session, user_id, songs_to_evict)
                optimizations['songs_evicted'] = freed['songs_evicted']
                optimizations['bytes_freed'] = freed['bytes_freed']
                optimizations['reason'] = 'low_efficiency'
            
            return optimizations
        finally:
            session.close()
    
    def _smart_evict_cache(self, session: Session, user_id: str, songs_to_evict: int) -> Dict:
        """Smart cache eviction considering multiple factors"""
        # Get cached songs with scoring
        cached_songs = session.query(Song).filter(
            Song.user_id == user_id,
            Song.in_playlist == False,
            Song.s3_key != ''
        ).all()
        
        # Score songs based on multiple factors
        scored_songs = []
        now = datetime.now()
        
        for song in cached_songs:
            score = 0
            
            # Factor 1: Age (older = higher score for eviction)
            if song.last_listened:
                days_old = (now - song.last_listened).days
                score += days_old * 10  # 10 points per day old
            
            # Factor 2: Size (larger = higher score for eviction)
            score += song.size / (1024 * 1024)  # 1 point per MB
            
            # Factor 3: Never listened (very high score)
            if not song.last_listened:
                score += 1000
            
            scored_songs.append((song, score))
        
        # Sort by score (highest = evict first)
        scored_songs.sort(key=lambda x: x[1], reverse=True)
        
        # Evict top songs
        songs_to_delete = []
        bytes_freed = 0
        
        for song, score in scored_songs[:songs_to_evict]:
            songs_to_delete.append(song)
            bytes_freed += song.size
        
        # Delete from S3 and database
        user = session.query(User).filter(User.id == user_id).first()
        
        for song in songs_to_delete:
            s3_client.delete_file(song.s3_key)
            user.total_storage_used -= song.size
            session.delete(song)
        
        session.commit()
        
        return {
            'songs_evicted': len(songs_to_delete),
            'bytes_freed': bytes_freed
        }
    
    def invalidate_cache_for_playlist(self, user_id: str, playlist_id: str) -> int:
        """Remove songs from cache when they're removed from a playlist"""
        session = get_session()
        try:
            # Find songs that were in this playlist but are no longer there
            # (This would be called when a playlist is updated)
            playlist_songs = session.query(PlaylistSong).filter(
                PlaylistSong.playlist_id == playlist_id
            ).all()
            
            current_song_ids = {ps.song_id for ps in playlist_songs}
            
            # Find cached songs that were in this playlist but are no longer
            cached_songs = session.query(Song).filter(
                Song.user_id == user_id,
                Song.in_playlist == False,
                Song.s3_key != ''
            ).all()
            
            songs_to_remove = []
            for song in cached_songs:
                # Check if this song was in the playlist but is no longer
                # (This is a simplified check - in reality you'd need to track playlist history)
                if song.id not in current_song_ids:
                    songs_to_remove.append(song)
            
            # Remove from cache
            user = session.query(User).filter(User.id == user_id).first()
            bytes_freed = 0
            
            for song in songs_to_remove:
                s3_client.delete_file(song.s3_key)
                user.total_storage_used -= song.size
                bytes_freed += song.size
                session.delete(song)
            
            session.commit()
            return len(songs_to_remove)
            
        finally:
            session.close()
    
    def get_or_create_user(self, spotify_user_id: str, display_name: str, email: str = None) -> User:
        """Get existing user or create new one"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == spotify_user_id).first()
            if not user:
                user = User(
                    id=spotify_user_id,
                    display_name=display_name,
                    email=email,
                    total_storage_used=0
                )
                session.add(user)
                session.commit()
                session.refresh(user)  # Refresh to get the user object
            return user
        finally:
            session.close()
    
    def sync_user_playlists(self, user_id: str, spotify_client: spotipy.Spotify, auto_download: bool = False) -> Dict:
        """Sync user's playlists from Spotify with retry logic"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            session = get_session()
            try:
                # Get user's playlists from Spotify
                spotify_playlists = spotify_client.current_user_playlists()
                
                # Get existing playlists in our database
                existing_playlists = {
                    p.id: p for p in session.query(Playlist).filter(Playlist.user_id == user_id).all()
                }
                
                # Track changes
                changes = {
                    'playlists_added': 0,
                    'playlists_updated': 0,
                    'songs_added': 0,
                    'songs_removed': 0,
                    'songs_downloaded': 0
                }
                
                # Process each playlist
                for spotify_playlist in spotify_playlists['items']:
                    playlist_id = spotify_playlist['id']
                    playlist_name = spotify_playlist['name']
                    
                    print(f"📋 Loading playlist: {playlist_name}")
                    
                    # Create or update playlist
                    if playlist_id in existing_playlists:
                        playlist = existing_playlists[playlist_id]
                        playlist.name = spotify_playlist['name']
                        playlist.description = spotify_playlist.get('description')
                        changes['playlists_updated'] += 1
                    else:
                        playlist = Playlist(
                            id=playlist_id,
                            user_id=user_id,
                            name=spotify_playlist['name'],
                            description=spotify_playlist.get('description')
                        )
                        session.add(playlist)
                        changes['playlists_added'] += 1
                    
                    # Sync playlist tracks
                    self._sync_playlist_tracks(session, playlist, spotify_client, changes)
                    
                    # Auto-download songs if enabled
                    if auto_download:
                        self._auto_download_playlist_songs(session, playlist, user_id, changes)
                
                session.commit()
                return changes
                
            except Exception as e:
                session.rollback()
                print(f"❌ Error syncing playlists (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    import time
                    print(f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"❌ Failed after {max_retries} attempts")
                    # Return partial changes instead of raising
                    return changes
            finally:
                session.close()
    
    def _sync_playlist_tracks(self, session: Session, playlist: Playlist, 
                            spotify_client: spotipy.Spotify, changes: Dict):
        """Sync tracks for a specific playlist"""
        # Get current tracks in playlist
        spotify_tracks = spotify_client.playlist_tracks(playlist.id)
        
        # Get existing playlist-song relationships
        existing_songs = {
            ps.song_id: ps for ps in session.query(PlaylistSong)
            .filter(PlaylistSong.playlist_id == playlist.id).all()
        }
        
        songs_found = 0
        # Process each track
        for item in spotify_tracks['items']:
            track = item['track']
            if not track:  # Skip null tracks
                continue
                
            songs_found += 1
            print(f"   🎵 Found song: {track['name']} - {track['artists'][0]['name']}")
                
            try:
                # Create or get song
                song = self._get_or_create_song(session, playlist.user_id, track)
                
                # Add to playlist if not already there
                if song.id not in existing_songs:
                    playlist_song = PlaylistSong(
                        playlist_id=playlist.id,
                        song_id=song.id
                    )
                    session.add(playlist_song)
                    changes['songs_added'] += 1
            except Exception as e:
                print(f"   ❌ Error processing song {track['name']}: {e}")
                # Try to commit what we have so far
                try:
                    session.commit()
                except Exception as commit_error:
                    print(f"   ❌ Error committing changes: {commit_error}")
                    session.rollback()
                continue
        
        print(f"   📊 Total songs in playlist: {songs_found}")
        
        # Mark songs as in_playlist=True
        song_ids = [item['track']['id'] for item in spotify_tracks['items'] if item['track']]
        session.query(Song).filter(
            Song.id.in_(song_ids),
            Song.user_id == playlist.user_id
        ).update({'in_playlist': True})
    
    def _get_or_create_song(self, session: Session, user_id: str, spotify_track) -> Song:
        """Get existing song or create placeholder (without S3 file yet)"""
        song_id = spotify_track['id']
        
        # Use get_or_create pattern to avoid duplicate key issues
        song, created = session.query(Song).filter(
            Song.id == song_id,
            Song.user_id == user_id
        ).first(), False
        
        if not song:
            # Create placeholder song (will be filled when downloaded)
            song = Song(
                id=song_id,
                user_id=user_id,
                name=spotify_track['name'],
                artist=spotify_track['artists'][0]['name'],
                s3_key='',  # Will be set when downloaded
                size=0,     # Will be set when downloaded
                in_playlist=True
            )
            session.add(song)
            # Commit immediately to avoid bulk insert issues
            session.commit()
            created = True
        else:
            # Update existing song to mark as in playlist
            song.in_playlist = True
        
        return song
    
    def add_song_file(self, user_id: str, song_id: str, file_path: str, s3_key: str) -> bool:
        """Add MP3 file to S3 and update song record"""
        session = get_session()
        try:
            print(f"🔍 Looking up song in database: {song_id} for user: {user_id}")
            
            # Upload to S3
            if not s3_client.upload_file(file_path, s3_key):
                print(f"❌ Failed to upload {s3_key} to S3")
                return False
            
            # Get file size
            file_size = os.path.getsize(file_path)
            print(f"📏 File size: {file_size} bytes")
            
            # Update song record
            song = session.query(Song).filter(
                Song.id == song_id,
                Song.user_id == user_id
            ).first()
            
            if song:
                print(f"✅ Found song in database: {song_id}")
                
                # Check storage limit before adding
                if not self._check_storage_limit(session, user_id, file_size):
                    print(f"⚠️ Storage limit check failed, attempting to free space...")
                    # Try to free space
                    if not self._free_storage_space(session, user_id, file_size):
                        s3_client.delete_file(s3_key)  # Clean up uploaded file
                        print(f"❌ Storage limit exceeded for user {user_id}")
                        return False
                
                song.s3_key = s3_key
                song.size = file_size
                
                # Update user's total storage
                user = session.query(User).filter(User.id == user_id).first()
                user.total_storage_used += file_size
                
                session.commit()
                print(f"✅ Successfully added song to database: {s3_key}")
                return True
            
            print(f"❌ Song not found in database: {song_id}")
            print(f"   Available songs for user {user_id}:")
            songs = session.query(Song).filter(Song.user_id == user_id).all()
            for s in songs[:5]:  # Show first 5 songs
                print(f"     - {s.id}: {s.name} by {s.artist}")
            return False
            
        except Exception as e:
            session.rollback()
            print(f"❌ Database error adding song file: {e}")
            print(f"   Error type: {type(e).__name__}")
            return False
        finally:
            session.close()
    
    def _check_storage_limit(self, session: Session, user_id: str, new_file_size: int) -> bool:
        """Check if adding new file would exceed storage limit"""
        user = session.query(User).filter(User.id == user_id).first()
        return (user.total_storage_used + new_file_size) <= self.max_storage_bytes
    
    def _free_storage_space(self, session: Session, user_id: str, needed_bytes: int) -> bool:
        """Free storage space by removing least recently listened cached songs"""
        # Get cached songs (not in any playlist) ordered by last_listened
        cached_songs = session.query(Song).filter(
            Song.user_id == user_id,
            Song.in_playlist == False,
            Song.s3_key != ''  # Has actual file
        ).order_by(Song.last_listened.asc()).all()
        
        freed_bytes = 0
        songs_to_delete = []
        
        for song in cached_songs:
            if freed_bytes >= needed_bytes:
                break
            
            freed_bytes += song.size
            songs_to_delete.append(song)
        
        if freed_bytes < needed_bytes:
            return False  # Not enough space even after clearing cache
        
        # Delete songs from S3 and database
        user = session.query(User).filter(User.id == user_id).first()
        
        for song in songs_to_delete:
            s3_client.delete_file(song.s3_key)
            user.total_storage_used -= song.size
            session.delete(song)
        
        session.commit()
        return True
    
    def evict_cache_for_user(self, user_id: str, needed_bytes: int) -> bool:
        """Public method to free up storage for a user by evicting cached songs."""
        session = get_session()
        try:
            return self._free_storage_space(session, user_id, needed_bytes)
        finally:
            session.close()
    
    def update_last_listened(self, user_id: str, song_id: str):
        """Update last_listened timestamp for a song"""
        session = get_session()
        try:
            song = session.query(Song).filter(
                Song.id == song_id,
                Song.user_id == user_id
            ).first()
            
            if song:
                song.last_listened = datetime.now()
                session.commit()
                
        except Exception as e:
            session.rollback()
            logging.error(f"Error updating last_listened: {e}")
        finally:
            session.close()
    
    def get_user_storage_info(self, user_id: str) -> Dict:
        """Get user's storage usage information"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            # Count songs in playlists vs cache
            playlist_songs = session.query(Song).filter(
                Song.user_id == user_id,
                Song.in_playlist == True
            ).count()
            
            cache_songs = session.query(Song).filter(
                Song.user_id == user_id,
                Song.in_playlist == False
            ).count()
            
            return {
                'total_storage_used': user.total_storage_used,
                'max_storage': self.max_storage_bytes,
                'storage_percentage': (user.total_storage_used / self.max_storage_bytes) * 100,
                'playlist_songs': playlist_songs,
                'cache_songs': cache_songs
            }
            
        finally:
            session.close()
    
    def _auto_download_playlist_songs(self, session: Session, playlist: Playlist, user_id: str, changes: Dict):
        """Auto-download songs that don't have S3 files yet"""
        import os
        import tempfile
        import yt_dlp
        
        # Get songs in this playlist that don't have S3 files
        songs_to_download = session.query(Song).filter(
            Song.user_id == user_id,
            Song.s3_key == '',  # No S3 file yet
            Song.in_playlist == True
        ).limit(5).all()  # Limit to 5 songs per playlist to avoid overwhelming
        
        if not songs_to_download:
            return
        
        print(f"   🎵 Auto-downloading {len(songs_to_download)} songs from playlist: {playlist.name}")
        
        for song in songs_to_download:
            try:
                query = f"{song.name} {song.artist}"
                
                print(f"   🔍 Searching for: {query}")
                
                # Download directly to memory and upload to S3
                s3_key = f"{user_id}/{song.name} - {song.artist}.mp3"
                success = self._download_and_upload_directly(query, user_id, song.id, s3_key)
                
                if success:
                    print(f"   ✅ Successfully downloaded and uploaded: {song.name} - {song.artist}")
                    changes['songs_downloaded'] += 1
                else:
                    print(f"   ❌ Failed to download/upload: {song.name} - {song.artist}")
                
            except Exception as e:
                print(f"   ❌ Error downloading {song.name} - {song.artist}: {e}")
                continue
    
    def _download_and_upload_directly(self, query: str, user_id: str, song_id: str, s3_key: str) -> bool:
        """Download from YouTube and upload directly to S3 without local storage"""
        import yt_dlp
        import tempfile
        import os
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_path,
                'quiet': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': '/opt/homebrew/bin/ffmpeg',  # Use full path to ffmpeg
                'prefer_ffmpeg': True,  # Prefer ffmpeg over other extractors
            }
            
            # Download from YouTube
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"ytsearch1:{query}"])
            except Exception as yt_error:
                print(f"   ❌ yt-dlp error: {yt_error}")
                # Try without post-processor as fallback
                ydl_opts_fallback = {
                    'format': 'bestaudio/best',
                    'outtmpl': temp_path,
                    'quiet': False,
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                        ydl.download([f"ytsearch1:{query}"])
                except Exception as fallback_error:
                    print(f"   ❌ Fallback download also failed: {fallback_error}")
                    return False
            
            # Check if file was created (yt-dlp with FFmpeg creates .mp3.mp3 files)
            final_path = temp_path
            if not os.path.exists(temp_path):
                # Check for the .mp3.mp3 version that FFmpeg creates
                mp3_path = temp_path + '.mp3'
                if os.path.exists(mp3_path):
                    final_path = mp3_path
                else:
                    print(f"   ❌ Downloaded file not found: {temp_path}")
                    print(f"   📁 Files in temp directory: {os.listdir(os.path.dirname(temp_path))}")
                    return False
            
            # Upload directly to S3
            success = self.add_song_file(user_id, song_id, final_path, s3_key)
            
            # Clean up temp file
            os.unlink(final_path)
            # Also clean up the original temp file if it's different
            if final_path != temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            
            return success
            
        except Exception as e:
            print(f"   ❌ Error in direct download/upload: {e}")
            # Clean up temp files if they exist
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            mp3_path = temp_path + '.mp3'
            if os.path.exists(mp3_path):
                os.unlink(mp3_path)
            return False


# Global user service instance
user_service = UserService() 