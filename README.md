# Spotify MP3 Sync

A full-stack application that syncs Spotify playlists, downloads MP3s from YouTube, and uploads them to S3 for offline listening.

## 🚀 Features

- **Spotify Integration**: OAuth authentication and playlist management
- **YouTube Download**: Automatic MP3 download from YouTube videos
- **S3 Storage**: Cloud storage for offline access
- **Advanced Caching**: LRU cache with smart eviction strategies
- **Mobile App**: React Native/Expo frontend
- **RESTful API**: FastAPI backend with comprehensive testing

## 📁 Project Structure

```
spotify-mp3-sync/
├── backend/                 # Python FastAPI backend
│   ├── main.py             # Main FastAPI application
│   ├── models.py           # SQLAlchemy database models
│   ├── user_service.py     # User and playlist management
│   ├── s3_client.py        # AWS S3 operations
│   ├── requirements.txt    # Python dependencies
│   ├── pytest.ini         # Test configuration
│   ├── scripts/            # Utility scripts
│   │   ├── start.sh        # Startup script with localtunnel
│   │   ├── start_backend.py # Python startup script
│   │   ├── auth_spotify.py # Spotify authentication helper
│   │   └── create_db.py    # Database creation script
│   ├── test/               # Test files
│   │   ├── test_integration.py
│   │   └── test_e2e.py
│   └── PROJECT_TASKS.md    # Project task tracking
├── frontend/               # React Native/Expo app
│   ├── app/                # App screens and navigation
│   ├── hooks/              # Custom React hooks
│   └── .gitignore          # Frontend-specific ignores
├── .gitignore              # Global gitignore
└── README.md               # This file
```

## 🛠️ Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- AWS CLI configured
- Spotify Developer Account
- LocalTunnel (for HTTPS tunneling)

### Backend Setup

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Create database**:
   ```bash
   python scripts/create_db.py
   ```

4. **Start the backend**:
   ```bash
   # Option 1: Use the startup script (recommended)
   ./scripts/start.sh
   
   # Option 2: Manual startup
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### Frontend Setup

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start the app**:
   ```bash
   npx expo start
   ```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Spotify API
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=https://spotisync.loca.lt/callback

# AWS S3
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET_NAME=your_s3_bucket_name

# JWT
JWT_SECRET_KEY=your_jwt_secret_key

# Testing
TEST_S3_BUCKET=your_test_bucket_name
```

### Spotify App Configuration

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add redirect URI: `https://spotisync.loca.lt/callback`
4. Copy Client ID and Client Secret to your `.env` file

## 🧪 Testing

### Run Tests

```bash
cd backend
pytest test/                    # All tests
pytest test/test_integration.py # Integration tests only
pytest test/test_e2e.py         # End-to-end tests only
```

### Test Coverage

- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint testing with mocked services
- **E2E Tests**: Full workflow testing with real Spotify/S3

## 🚀 Deployment

### Development

The startup script automatically:
- Starts LocalTunnel for HTTPS access
- Updates URLs dynamically
- Starts the FastAPI backend
- Provides consistent `https://spotisync.loca.lt` URL

### Production

For production deployment:
1. Use a proper domain instead of LocalTunnel
2. Set up SSL certificates
3. Configure environment variables
4. Use a production database (PostgreSQL/MySQL)

## 📊 Features

### Advanced Caching System

- **LRU Eviction**: Least Recently Used cache eviction
- **Smart Scoring**: Intelligent cache entry scoring
- **Proactive Eviction**: Preemptive cache cleanup
- **Statistics Tracking**: Cache hit/miss metrics

### API Endpoints

- `GET /` - Health check
- `GET /login` - Spotify OAuth initiation
- `GET /callback` - OAuth callback handler
- `GET /playlists` - User playlists
- `POST /download` - Download playlist to S3

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

1. **Database Schema Errors**: Run `python scripts/create_db.py`
2. **Spotify OAuth Issues**: Check redirect URI in Spotify Dashboard
3. **S3 Connection Errors**: Verify AWS credentials
4. **LocalTunnel Issues**: Try different subdomain or restart tunnel

### Getting Help

- Check the logs for detailed error messages
- Verify all environment variables are set
- Ensure Spotify app redirect URI matches exactly 