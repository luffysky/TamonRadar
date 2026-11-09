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
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


PRESIGN_PUT_SECONDS = 900
EXPORT_LINK_SECONDS = 300


def presign_upload(filename: str, content_type: str, size: int) -> dict:
    """簽一個瀏覽器直傳 R2 的 PUT 網址(繞過 Function 的 4.5 MB 請求上限)。

    Content-Type 與 Content-Length 都納入簽章,實際上傳內容必須和宣告一致。
    """
    ext = os.path.splitext(filename or "")[1].lower()[:16]
    key = f"uploads/{uuid.uuid4().hex}{ext}"
    ctype = content_type or "application/octet-stream"
    url = _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": os.environ["R2_BUCKET_NAME"], "Key": key, "ContentType": ctype, "ContentLength": size},
        ExpiresIn=PRESIGN_PUT_SECONDS,
    )
    base = os.environ["R2_URL"].rstrip("/")
    return {"upload_url": url, "method": "PUT", "headers": {"Content-Type": ctype},
            "url": f"{base}/{key}", "key": key, "expires_in": PRESIGN_PUT_SECONDS}


def store_export(filename: str, data: bytes, content_type: str) -> str:
    """把超過回應上限的匯出檔放到 R2 私有路徑,回傳短效簽名下載網址。"""
    key = f"exports/{uuid.uuid4().hex}/{filename}"
    client = _client()
    bucket = os.environ["R2_BUCKET_NAME"]
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key, "ResponseContentDisposition": f'attachment; filename="{filename}"'},
        ExpiresIn=EXPORT_LINK_SECONDS,
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
