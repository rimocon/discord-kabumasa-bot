#!/usr/bin/env python3
"""
render_start.py - Render用起動スクリプト
Renderの無料プランではWebサービスとして動かすため、
簡易HTTPサーバーと並行してBotを起動する
"""
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import sys


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Discord Trade Bot is running!")

    def log_message(self, format, *args):
        pass  # ログ抑制


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[Health] ヘルスチェックサーバー起動 (port={port})")
    server.serve_forever()


if __name__ == "__main__":
    # ヘルスチェック用HTTPサーバーをバックグラウンドで起動
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()

    # Discord Botを起動
    print("[Start] Discord Bot を起動します...")
    subprocess.run([sys.executable, "bot.py"], check=True)
