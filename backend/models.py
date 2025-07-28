from sqlalchemy import create_engine, Column, String, BigInteger, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # Spotify user ID
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    total_storage_used = Column(BigInteger, default=0)  # bytes
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    # --- Spotify Auth Tokens ---
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)  # UTC timestamp when token expires
    # Relationships
    playlists = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")
    songs = relationship("Song", back_populates="user", cascade="all, delete-orphan")

class Song(Base):
    __tablename__ = "songs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)  # S3 object key for the MP3 file
    size = Column(BigInteger, nullable=False)  # file size in bytes
    last_listened = Column(DateTime, nullable=True)
    in_playlist = Column(Boolean, default=True)  # True if currently in any playlist
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="songs")
    playlist_songs = relationship("PlaylistSong", back_populates="song", cascade="all, delete-orphan")

class Playlist(Base):
    __tablename__ = "playlists"
    
    id = Column(String, primary_key=True)  # Spotify playlist ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="playlists")
    playlist_songs = relationship("PlaylistSong", back_populates="playlist", cascade="all, delete-orphan")

class PlaylistSong(Base):
    __tablename__ = "playlist_songs"
    
    playlist_id = Column(String, ForeignKey("playlists.id"), primary_key=True)
    song_id = Column(String, ForeignKey("songs.id"), primary_key=True)
    added_at = Column(DateTime, default=func.now())
    
    # Relationships
    playlist = relationship("Playlist", back_populates="playlist_songs")
    song = relationship("Song", back_populates="playlist_songs")

# Database configuration
# Global engine and session factory
_engine = None
_SessionLocal = None

def get_database_url():
    """Get database URL from environment or use SQLite for development"""
    import os
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    else:
        # Use SQLite for development with better concurrency settings
        return "sqlite:///./spotify_sync.db?timeout=30&check_same_thread=False"

def create_database_engine():
    """Create database engine with better concurrency settings"""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        # Disable SQLAlchemy logging completely
        import logging
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        
        # Add better SQLite settings for concurrency
        connect_args = {}
        if "sqlite" in database_url:
            connect_args = {
                "timeout": 30,
                "check_same_thread": False,
                "isolation_level": None  # Autocommit mode for better concurrency
            }
        
        _engine = create_engine(
            database_url, 
            echo=False,
            connect_args=connect_args,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600     # Recycle connections every hour
        )
    return _engine

def create_tables():
    """Create all tables"""
    engine = create_database_engine()
    Base.metadata.create_all(bind=engine)

def get_session():
    """Get database session with better error handling"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = create_database_engine()
        _SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=engine,
            expire_on_commit=False  # Keep objects accessible after commit
        )
    return _SessionLocal() 