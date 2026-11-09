"""執行環境判定與「正式環境必備設定」檢查(fail-closed)。

正式環境的判定(只有一個入口:is_production):
- 優先看 APP_ENV(或 ENV):production / prod 視為正式,其他值視為非正式。
- 兩者都沒設時,DATABASE_URL 指向 Postgres 就視為正式環境(寧可多擋,也不要帶著預設密鑰上線)。
"""
import os

# 程式內的開發用預設值;正式環境絕不允許使用
DEV_JWT_SECRET = "dev-insecure-secret-change-me"
DEV_ENCRYPTION_KEY = "dev-insecure-key"


def is_production() -> bool:
    env = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "").strip().lower()
    if env:
        return env in ("production", "prod")
    return os.environ.get("DATABASE_URL", "").strip().startswith(("postgres://", "postgresql://", "postgresql+"))


def production_config_errors() -> list[str]:
    """回傳正式環境設定的問題清單(只含變數名稱,不含任何值)。非正式環境回空清單。"""
    if not is_production():
        return []
    errors: list[str] = []
    jwt_secret = os.environ.get("JWT_SECRET", "").strip()
    enc_key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not jwt_secret or jwt_secret == DEV_JWT_SECRET:
        errors.append("JWT_SECRET 未設定或仍是開發預設值")
    if not enc_key or enc_key == DEV_ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY 未設定或仍是開發預設值")
    if jwt_secret and jwt_secret == enc_key:
        errors.append("JWT_SECRET 與 ENCRYPTION_KEY 不可相同")
    return errors


def assert_production_config() -> None:
    """設定有問題就直接拒絕啟動;必須在匯入 auth / db 之前呼叫。"""
    errors = production_config_errors()
    if errors:
        raise RuntimeError("正式環境設定不完整,拒絕啟動:" + ";".join(errors))
