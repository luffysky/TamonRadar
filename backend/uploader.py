"""檔案上傳到 Cloudflare R2(S3 相容)。支援任意格式。

環境變數(與 ai_island / insight-engine 同慣例):
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_URL
"""
import os
import uuid


_REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_URL")


def r2_available() -> bool:
    return all(os.environ.get(k) for k in _REQUIRED)


def _client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def upload(filename: str, data: bytes, content_type: str) -> str:
    """上傳並回傳公開網址。"""
    ext = os.path.splitext(filename or "")[1].lower()
    key = f"uploads/{uuid.uuid4().hex}{ext}"
    client = _client()
    client.put_object(
        Bucket=os.environ["R2_BUCKET_NAME"],
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )
    base = os.environ["R2_URL"].rstrip("/")
    return f"{base}/{key}"
