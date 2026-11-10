"""Tìm trình duyệt có sẵn trên máy (Chrome / Edge / Brave) và mở bằng Playwright."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import PROFILE_DIR


def _candidates():
    if sys.platform == "darwin":
        names = ["Google Chrome.app/Contents/MacOS/Google Chrome",
                 "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 "Brave Browser.app/Contents/MacOS/Brave Browser",
                 "Chromium.app/Contents/MacOS/Chromium"]
        for base in (Path("/Applications"), Path.home() / "Applications"):
            for n in names:
                yield base / n
    elif sys.platform.startswith("win"):
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        rels = [r"Google\Chrome\Application\chrome.exe",
                r"Microsoft\Edge\Application\msedge.exe",
                r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        for rel in rels:
            for root in roots:
                if root:
                    yield Path(root) / rel
    else:
        for n in ("google-chrome", "google-chrome-stable", "microsoft-edge", "brave-browser", "chromium", "chromium-browser"):
            p = shutil.which(n)
            if p:
                yield Path(p)


def find_browser(custom_path: str = "") -> str | None:
    """Trả về đường dẫn trình duyệt, hoặc None nếu không có (sẽ dùng Chromium của Playwright)."""
    if custom_path and Path(custom_path).exists():
        return custom_path
    for p in _candidates():
        if p.exists():
            return str(p)
    return None


def ensure_playwright_chromium(log=print):
    """Tải Chromium của Playwright (chỉ khi máy không có Chrome/Edge/Brave)."""
    log("Không tìm thấy Chrome/Edge/Brave — đang tải Chromium (chỉ lần đầu, khoảng 150MB)...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


async def launch(playwright, settings, log=print):
    exe = find_browser(settings.get("browser_path", ""))
    kwargs = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=bool(settings.get("headless", True)),
        locale="en-US",
        viewport={"width": 1366, "height": 900},
    )
    if exe:
        log(f"Dùng trình duyệt: {exe}")
        return await playwright.chromium.launch_persistent_context(executable_path=exe, **kwargs)
    try:
        return await playwright.chromium.launch_persistent_context(**kwargs)
    except Exception:
        ensure_playwright_chromium(log)
        return await playwright.chromium.launch_persistent_context(**kwargs)
