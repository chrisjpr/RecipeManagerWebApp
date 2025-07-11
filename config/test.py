import boto3
import os
from botocore.exceptions import ClientError

# Load credentials from environment (your .env must be loaded)
session = boto3.Session(
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name='eu-central-1'
)

s3 = session.client('s3')
bucket = os.getenv("AWS_STORAGE_BUCKET_NAME")

try:
    # Try listing objects (should succeed if permissions are correct)
    response = s3.list_objects_v2(Bucket=bucket)
    print(f"✅ Connection successful. Found {response.get('KeyCount', 0)} object(s) in '{bucket}'.")

    # Optional: upload a test file
    s3.put_object(Bucket=bucket, Key='media/test-upload.txt', Body=b'Hello from Django!')
    print("✅ Test file uploaded: media/test-upload.txt")

except ClientError as e:
    print("❌ S3 ClientError:", e)