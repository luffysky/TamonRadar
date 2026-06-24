"""敏感設定(AI 金鑰、Discord/Telegram 憑證)的對稱加密。

存進資料庫前加密、讀出時解密。金鑰由環境變數 ENCRYPTION_KEY 衍生,
沒設則退回用 JWT_SECRET 衍生(至少有保護;正式建議獨立設 ENCRYPTION_KEY)。
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    secret = os.environ.get("ENCRYPTION_KEY") or os.environ.get("JWT_SECRET") or "dev-insecure-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(text: str) -> str:
    if not text:
        return ""
    return _PREFIX + _fernet().encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    if not text:
        return ""
    if not text.startswith(_PREFIX):
        return text  # 舊的明文資料,直接回傳(漸進遷移,下次儲存就會加密)
    try:
        return _fernet().decrypt(text[len(_PREFIX):].encode()).decode()
    except Exception:
        return ""
