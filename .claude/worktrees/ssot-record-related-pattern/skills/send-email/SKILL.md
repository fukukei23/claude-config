---
name: send-email
description: >
  Gmail経由でメールを送信するスキル。
  ユーザーが「メールで送って」「email送信」「メール送信」または /send-email を呼び出した時にトリガーする。
  ~/.secrets.env の GMAIL_SMTP_USER / GMAIL_SMTP_PASSWORD を使用。
user-invocable: true
---

# send-email スキル

## 概要

Gmail SMTP経由でメールを送信する。添付ファイルにも対応。

---

## フェーズ1: 送信内容の特定

会話の文脈から以下を自動収集。不足分だけ聞く:

- **宛先** — 指定がなければ前回使用した宛先（デフォルト: `y.n.4416524@gmail.com`）
- **件名** — 文脈から推測。指定があればそれに従う
- **本文** — 指定がなければ「ファイルを送ります」程度の短い本文
- **添付ファイル** — 指定されたファイルパス、または直前に作成・編集したファイル

---

## フェーズ2: メール送信

以下のPythonスクリプトを実行する。**変数の値はフェーズ1で決定したものに置き換えること。**

```python
python3 << 'PYEOF'
import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# 認証情報（~/.secrets.env から環境変数経由で取得）
SMTP_USER = os.environ.get("GMAIL_SMTP_USER", "")
SMTP_PASS = os.environ.get("GMAIL_SMTP_PASSWORD", "")

if not SMTP_USER or not SMTP_PASS:
    print("❌ GMAIL_SMTP_USER / GMAIL_SMTP_PASSWORD が未設定")
    exit(1)

# 送信内容（フェーズ1で決定）
TO = "宛先をここに"
SUBJECT = "件名をここに"
BODY = "本文をここに"
ATTACHMENT = "/tmp/添付ファイルパス.md"  # None なら添付なし

msg = MIMEMultipart()
msg["From"] = SMTP_USER
msg["To"] = TO
msg["Subject"] = SUBJECT
msg.attach(MIMEText(BODY, "plain", "utf-8"))

if ATTACHMENT and os.path.exists(ATTACHMENT):
    with open(ATTACHMENT, "rb") as f:
        att = MIMEBase("text", "plain")
        att.set_payload(f.read())
        encoders.encode_base64(att)
        filename = os.path.basename(ATTACHMENT)
        att.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(att)

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    server.sendmail(SMTP_USER, TO, msg.as_string())
    server.quit()
    print(f"✅ メール送信完了 → {TO}")
except Exception as e:
    print(f"❌ エラー: {e}")
PYEOF
```

---

## フェーズ3: 完了報告

```
✅ メール送信完了

📧 送信元: fukukei4416@gmail.com
📬 宛先: y.n.4416524@gmail.com
📎 添付: ファイル名（または「なし」）
📝 件名: ...
```

---

## 制約

- APIキー値を会話・ログに出力しない
- 添付ファイルは25MB以下（Gmail制限）
- 宛先が未指定の場合はユーザーに確認すること
- BCC等の追加機能が必要なら都度対応
