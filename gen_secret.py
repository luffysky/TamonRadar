"""產生一組安全的隨機密鑰,給 JWT_SECRET 用。
用法:python gen_secret.py
把印出來的整串貼到 Zeabur 後端的環境變數 JWT_SECRET。
"""
import secrets

if __name__ == "__main__":
    print(secrets.token_urlsafe(48))
