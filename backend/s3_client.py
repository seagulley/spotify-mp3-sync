import boto3
import os
from botocore.exceptions import ClientError
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta

class S3Client:
    """Client for handling S3 operations"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
        if not self.bucket_name:
            logging.warning("S3_BUCKET_NAME not set - S3 operations will fail")
    
    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """Upload a file to S3"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return False
                
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            logging.info(f"Successfully uploaded {file_path} to s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logging.error(f"Error uploading file to S3: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error uploading file: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download a file from S3"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return False
                
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logging.info(f"Successfully downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except ClientError as e:
            logging.error(f"Error downloading file from S3: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error downloading file: {e}")
            return False
    
    def delete_file(self, s3_key: str) -> bool:
        """Delete a file from S3"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return False
                
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logging.info(f"Successfully deleted s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logging.error(f"Error deleting file from S3: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error deleting file: {e}")
            return False
    
    def get_file_size(self, s3_key: str) -> Optional[int]:
        """Get file size in bytes"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return None
                
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return response['ContentLength']
        except ClientError as e:
            logging.error(f"Error getting file size from S3: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error getting file size: {e}")
            return None
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for file access"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return None
                
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            logging.info(f"Generated presigned URL for s3://{self.bucket_name}/{s3_key}")
            return url
        except ClientError as e:
            logging.error(f"Error generating presigned URL: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error generating presigned URL: {e}")
            return None
    
    def file_exists(self, s3_key: str) -> bool:
        """Check if a file exists in S3"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return False
                
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False
        except Exception as e:
            logging.error(f"Unexpected error checking file existence: {e}")
            return False
    
    def list_user_files(self, user_id: str) -> List[Dict]:
        """List all files for a specific user"""
        try:
            if not self.bucket_name:
                logging.error("S3 bucket name not configured")
                return []
                
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{user_id}/"
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })
            
            return files
        except ClientError as e:
            logging.error(f"Error listing user files: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error listing user files: {e}")
            return []

# Global S3 client instance
s3_client = S3Client() 