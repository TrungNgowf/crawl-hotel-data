"""Điểm khởi động: `uv run hotel-price` — mở giao diện tại http://127.0.0.1:8765."""
import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

PORT = 8765
ROOT = Path(__file__).resolve().parent.parent


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    parser = argparse.ArgumentParser(description="Hotel Price Tool")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true", help="không tự mở trình duyệt")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    if _port_in_use(args.port):
        # App đã chạy (vd. bấm shortcut 2 lần) -> chỉ mở lại giao diện.
        print(f"Tool đang chạy rồi, mở {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return

    print(f"Hotel Price Tool đang chạy tại {url}\nĐóng cửa sổ này (hoặc Ctrl+C) để tắt tool.")
    os.chdir(ROOT)  # để Streamlit đọc .streamlit/config.toml (màu sắc, chế độ sáng/tối)
    if not args.no_browser:
        threading.Timer(2.5, lambda: webbrowser.open(url)).start()

    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", str(Path(__file__).parent / "app.py"),
                "--server.port", str(args.port), "--server.address", "127.0.0.1",
                "--server.headless", "true", "--global.developmentMode", "false"]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
