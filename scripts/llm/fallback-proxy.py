#!/usr/bin/env python3
"""
fallback-proxy.py
Anthropic API互換フォールバックプロキシ

Claude Code → localhost:8976 → GLM API
                                ↘ (失敗時) → MiniMax API

起動: python3 fallback-proxy.py
環境変数: ~/.secrets.env から GLM_API_KEY, MINIMAX_API_KEY を読み込む
PID管理: /tmp/fallback-proxy.pid
ログ: /tmp/fallback-proxy.log
"""

import json
import os
import signal
import sys
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = 8976
TIMEOUT = 300  # 秒
PID_FILE = "/tmp/fallback-proxy.pid"
LOG_FILE = "/tmp/fallback-proxy.log"

# API エンドポイント
GLM_URL = "https://api.z.ai/api/anthropic/v1/messages"
MINIMAX_URL = "https://api.minimax.io/anthropic/v1/messages"


def load_secrets():
    secrets = Path.home() / ".secrets.env"
    keys = {}
    if secrets.exists():
        with open(secrets) as f:
            for line in f:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys


def forward_request(body: bytes, url: str, api_key: str) -> tuple:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


class ProxyHandler(BaseHTTPRequestHandler):
    keys = {}

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 1次: GLM API
        glm_key = self.keys.get("GLM_API_KEY", "")
        if glm_key:
            status, response = forward_request(body, GLM_URL, glm_key)
            if 200 <= status < 300:
                self._write_status("GLM-5.1")
                self._respond(status, response)
                self._log("GLM", status)
                return
            else:
                self._log("GLM", status, fallback=True)

        # 2次: MiniMax API
        minimax_key = self.keys.get("MINIMAX_API_KEY", "")
        if minimax_key:
            status, response = forward_request(body, MINIMAX_URL, minimax_key)
            if 200 <= status < 300:
                self._write_status("MiniMax-M3")
                self._respond(status, response)
                self._log("MiniMax", status, fallback=True)
                return
            else:
                self._log("MiniMax", status, failed=True)

        self._respond(502, json.dumps({"error": "both providers failed"}).encode())
        self._log("BOTH FAILED", 502, failed=True)

    def _respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _write_status(self, model_name):
        try:
            with open("/tmp/llm-last-used.txt", "w") as f:
                f.write(model_name)
        except Exception:
            pass

    def _log(self, provider, status, fallback=False, failed=False):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = "FALLBACK" if fallback else ("FAILED" if failed else "OK")
        msg = f"[{ts}] [{prefix}] {provider} → {status}"
        print(msg, file=sys.stderr)
        try:
            with open(LOG_FILE, "a") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def log_message(self, format, *args):
        pass


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def cleanup(signum=None, frame=None):
    try:
        os.unlink(PID_FILE)
    except Exception:
        pass
    sys.exit(0)


def main():
    # 既存プロセス確認
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # プロセス生存確認
            print(f"既に起動中: PID {old_pid}", file=sys.stderr)
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            os.unlink(PID_FILE)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    keys = load_secrets()
    ProxyHandler.keys = keys

    if not keys.get("GLM_API_KEY"):
        print("警告: GLM_API_KEY が未設定", file=sys.stderr)
    if not keys.get("MINIMAX_API_KEY"):
        print("警告: MINIMAX_API_KEY が未設定", file=sys.stderr)

    server = HTTPServer(("127.0.0.1", PORT), ProxyHandler)
    write_pid()
    print(f"フォールバックプロキシ起動: http://127.0.0.1:{PORT} PID={os.getpid()}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
