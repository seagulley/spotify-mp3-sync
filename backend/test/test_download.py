import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

class TestBatchDownload:
    @patch("main.user_service")
    @patch("main.s3_client")
    @patch("main.yt_dlp.YoutubeDL")
    def test_batch_download_success(self, mock_yt_dlp, mock_s3_client, mock_user_service):
        # Mock yt-dlp to succeed
        mock_yt_dlp.return_value.__enter__.return_value = mock_yt_dlp.return_value
        mock_yt_dlp.return_value.download.return_value = 0
        # Mock user_service methods
        mock_user_service.add_song_file.return_value = True
        mock_user_service.update_last_listened.return_value = None
        # Mock S3 presigned URL
        mock_s3_client.generate_presigned_url.return_value = "https://s3/test.mp3"
        tracks = [
            {"name": "Song1", "artist": "Artist1"},
            {"name": "Song2", "artist": "Artist2"},
            {"name": "Song1", "artist": "Artist1"}  # duplicate
        ]
        response = client.post("/download", json={"tracks": tracks})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        # Deduplication: only 2 unique results
        assert len(data["results"]) == 2
        names = {r["name"] for r in data["results"]}
        assert names == {"Song1", "Song2"}

    @patch("main.user_service")
    @patch("main.s3_client")
    @patch("main.yt_dlp.YoutubeDL")
    def test_batch_download_partial_failure(self, mock_yt_dlp, mock_s3_client, mock_user_service):
        # Mock yt-dlp to fail for one track
        def download_side_effect(args):
            if "Song2" in args[0]:
                raise Exception("yt-dlp error")
            return 0
        mock_yt_dlp.return_value.__enter__.return_value = mock_yt_dlp.return_value
        mock_yt_dlp.return_value.download.side_effect = download_side_effect
        # Mock user_service methods
        mock_user_service.add_song_file.return_value = True
        mock_user_service.update_last_listened.return_value = None
        # Mock S3 presigned URL
        mock_s3_client.generate_presigned_url.return_value = "https://s3/test.mp3"
        tracks = [
            {"name": "Song1", "artist": "Artist1"},
            {"name": "Song2", "artist": "Artist2"}
        ]
        response = client.post("/download", json={"tracks": tracks})
        assert response.status_code == 207
        data = response.json()
        assert "results" in data
        assert "errors" in data
        # One success, one error
        assert len(data["results"]) == 1
        assert len(data["errors"]) == 1
        assert "Song2" in data["errors"][0]

    @patch("main.user_service")
    @patch("main.s3_client")
    @patch("main.yt_dlp.YoutubeDL")
    def test_batch_download_all_fail(self, mock_yt_dlp, mock_s3_client, mock_user_service):
        # Mock yt-dlp to fail for all tracks
        mock_yt_dlp.return_value.__enter__.return_value = mock_yt_dlp.return_value
        mock_yt_dlp.return_value.download.side_effect = Exception("yt-dlp error")
        # Mock user_service methods
        mock_user_service.add_song_file.return_value = True
        mock_user_service.update_last_listened.return_value = None
        # Mock S3 presigned URL
        mock_s3_client.generate_presigned_url.return_value = "https://s3/test.mp3"
        tracks = [
            {"name": "Song1", "artist": "Artist1"},
            {"name": "Song2", "artist": "Artist2"}
        ]
        response = client.post("/download", json={"tracks": tracks})
        assert response.status_code == 207
        data = response.json()
        assert "results" in data
        assert "errors" in data
        assert len(data["results"]) == 0
        assert len(data["errors"]) == 2 