import boto3
import os
import uuid
import tempfile
from typing import BinaryIO
from urllib.parse import urlparse

AWS_REGION = os.getenv("AWS_REGION")
AWS_BUCKET = os.getenv("AWS_S3_BUCKET")

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

# --------------------------------------------------
# SAFE S3 KEY EXTRACTOR
# --------------------------------------------------
def extract_s3_key(s3_url: str) -> str:
    parsed = urlparse(s3_url)

    # Handles:
    # https://bucket.s3.region.amazonaws.com/voices/uuid.wav
    # https://bucket.s3.amazonaws.com/voices/uuid.wav
    if f"{AWS_BUCKET}.s3" in parsed.netloc:
        return parsed.path.lstrip("/")

    raise ValueError(f"Invalid S3 URL: {s3_url}")


# --------------------------------------------------
# DOWNLOAD FROM S3
# --------------------------------------------------
def download_voice_from_s3(s3_url: str) -> str:
    """
    Downloads S3 file to a temp location and returns local path
    """
    key = extract_s3_key(s3_url)

    print("🔴 S3 DOWNLOAD DEBUG")
    print("URL:", s3_url)
    print("BUCKET:", AWS_BUCKET)
    print("REGION:", AWS_REGION)
    print("KEY:", key)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    s3.download_fileobj(AWS_BUCKET, key, tmp)
    tmp.close()

    return tmp.name


# --------------------------------------------------
# UPLOAD TO S3
# --------------------------------------------------
def upload_voice_to_s3(file_obj: BinaryIO, filename: str, content_type: str) -> str:
    """
    Upload voice file to S3 and return public URL
    """
    ext = filename.split(".")[-1]
    key = f"voices/{uuid.uuid4()}.{ext}"

    s3.upload_fileobj(
        file_obj,
        AWS_BUCKET,
        key,
        ExtraArgs={
            "ContentType": content_type,
        },
    )

    return f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
