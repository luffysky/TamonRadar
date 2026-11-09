"""敏感設定(AI 金鑰、Discord/Telegram 憑證)的對稱加密。

存進資料庫前加密、讀出時解密。金鑰由環境變數 ENCRYPTION_KEY 衍生;
開發環境沒設時退回用 JWT_SECRET 衍生,正式環境則必須設定(見 appconfig)。

換金鑰:把舊值放進 ENCRYPTION_KEY_PREVIOUS(逗號分隔),舊密文仍可解密,下次儲存時改用新金鑰。
解不開時會丟 DecryptionError,不再靜默回空字串,避免金鑰設錯時把使用者的資料洗掉。
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from appconfig import DEV_ENCRYPTION_KEY

_PREFIX = "enc:v1:"


class DecryptionError(Exception):
    """密文存在但目前的金鑰解不開(多半是 ENCRYPTION_KEY 換錯)。"""


def _fernet_for(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _fernet() -> Fernet:
    return _fernet_for(os.environ.get("ENCRYPTION_KEY") or os.environ.get("JWT_SECRET") or DEV_ENCRYPTION_KEY)


def _previous_fernets() -> list[Fernet]:
    raw = os.environ.get("ENCRYPTION_KEY_PREVIOUS", "")
    return [_fernet_for(s.strip()) for s in raw.split(",") if s.strip()]


def encrypt(text: str) -> str:
    if not text:
        return ""
    return _PREFIX + _fernet().encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    """解密;舊的明文資料原樣回傳。密文解不開時丟 DecryptionError。"""
    if not text:
        return ""
    if not text.startswith(_PREFIX):
        return text  # 舊的明文資料,直接回傳(漸進遷移,下次儲存就會加密)
    token = text[len(_PREFIX):].encode()
    for f in [_fernet(), *_previous_fernets()]:
        try:
            return f.decrypt(token).decode()
        except InvalidToken:
            continue
    raise DecryptionError("無法解密:ENCRYPTION_KEY 可能已更換,請確認 ENCRYPTION_KEY / ENCRYPTION_KEY_PREVIOUS")
