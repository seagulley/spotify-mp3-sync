import os
import pytest
import sys
from unittest.mock import Mock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s3_client import S3Client


class TestS3Client:
    """Test S3Client methods"""
    
    @patch('s3_client.boto3.client')
    def test_upload_file_success(self, mock_boto3_client):
        """Test successful file upload to S3"""
        # Mock S3 client
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Set environment variable
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        
        # Create service and test
        client = S3Client()
        result = client.upload_file("/tmp/test.mp3", "user123/test.mp3")
        
        assert result == True
        mock_s3_client.upload_file.assert_called_once_with("/tmp/test.mp3", "test-bucket", "user123/test.mp3")
    
    @patch('s3_client.boto3.client')
    def test_upload_file_failure(self, mock_boto3_client):
        """Test failed file upload to S3"""
        # Mock S3 client to fail
        mock_s3_client = Mock()
        mock_s3_client.upload_file.side_effect = Exception("Upload failed")
        mock_boto3_client.return_value = mock_s3_client
        
        # Set environment variable
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        
        # Create service and test
        client = S3Client()
        result = client.upload_file("/tmp/test.mp3", "user123/test.mp3")
        
        assert result == False
    
    @patch('s3_client.boto3.client')
    def test_generate_presigned_url(self, mock_boto3_client):
        """Test generating presigned URL"""
        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://example.com/presigned-url"
        mock_boto3_client.return_value = mock_s3_client
        
        # Set environment variable
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        
        # Create service and test
        client = S3Client()
        result = client.generate_presigned_url("user123/test.mp3")
        
        assert result == "https://example.com/presigned-url"
        mock_s3_client.generate_presigned_url.assert_called_once()
    
    @patch('s3_client.boto3.client')
    def test_upload_file_no_bucket_configured(self, mock_boto3_client):
        """Test upload fails when no bucket is configured"""
        # Ensure S3_BUCKET_NAME environment variable is not set
        if 'S3_BUCKET_NAME' in os.environ:
            del os.environ['S3_BUCKET_NAME']
        
        # Create service and test
        client = S3Client()
        result = client.upload_file("/tmp/test.mp3", "user123/test.mp3")
        
        assert result == False
    
    def test_cleanup_environment_variables(self):
        """Clean up environment variables after tests"""
        # Remove S3_BUCKET_NAME if it was set
        if 'S3_BUCKET_NAME' in os.environ:
            del os.environ['S3_BUCKET_NAME']


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 