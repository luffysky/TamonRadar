"""寄信:Resend 為主,額度用完 / 失敗自動換 Gmail SMTP。

- Resend:免費 3000 封/月,設 RESEND_API_KEY(+ RESEND_FROM)。
- Gmail:設 GMAIL_USER + GMAIL_APP_PASSWORD(Google 兩步驟驗證的「應用程式密碼」)。
都用內建庫 / requests,不需額外套件。
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

import requests


def mail_available() -> bool:
    return bool(
        os.environ.get("RESEND_API_KEY")
        or (os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"))
    )


def _send_resend(to: str, subject: str, html: str) -> tuple[bool, str]:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return False, "未設定 RESEND_API_KEY"
    frm = os.environ.get("RESEND_FROM", "TamonRadar <onboarding@resend.dev>")
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}"},
            json={"from": frm, "to": [to], "subject": subject, "html": html},
            timeout=20,
        )
        if r.status_code >= 400:
            return False, f"resend {r.status_code}: {r.text[:160]}"
        return True, "resend"
    except Exception as e:
        return False, str(e)[:200]


def _send_gmail(to: str, subject: str, html: str) -> tuple[bool, str]:
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        return False, "未設定 GMAIL_USER / GMAIL_APP_PASSWORD"
    frm = os.environ.get("MAIL_FROM", user)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = to
    msg.set_content("請用支援 HTML 的郵件軟體檢視此信。")
    msg.add_alternative(html, subtype="html")
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(user, pw)
            s.send_message(msg)
        return True, "gmail"
    except Exception as e:
        return False, str(e)[:200]


def send_email(to: str, subject: str, html: str) -> tuple[bool, str]:
    """先試 Resend,失敗/額度用完換 Gmail。回傳 (成功, 用了哪個或錯誤)。"""
    ok, info = _send_resend(to, subject, html)
    if ok:
        return True, info
    ok2, info2 = _send_gmail(to, subject, html)
    if ok2:
        return True, info2
    return False, f"resend({info}) / gmail({info2})"
