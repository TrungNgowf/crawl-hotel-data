"""Trạng thái crawl chạy nền (thread riêng) + lịch tự chạy hằng ngày."""
import asyncio
import threading
import time
from datetime import date, datetime, timedelta

from . import db
from .runner import run_crawl


class CrawlState:
    def __init__(self):
        self._lock = threading.Lock()
        self.running = False
        self.stop = threading.Event()
        self.lines: list[str] = []
        self.done = 0
        self.total = 0
        self.last_run_id = None
        self.started_at: datetime | None = None

    def log(self, msg):
        with self._lock:
            self.lines = (self.lines + [f"{datetime.now():%H:%M:%S}  {msg}"])[-500:]

    def progress(self, done, total):
        self.done, self.total = done, total

    def start(self, overrides: dict) -> bool:
        with self._lock:
            if self.running:
                return False
            self.running, self.done, self.total = True, 0, 0
            self.lines = []
            self.started_at = datetime.now()
            self.stop.clear()
        hotels = db.list_hotels()
        settings = {**db.get_settings(), **overrides}

        def target():
            try:
                self.last_run_id = asyncio.run(run_crawl(
                    hotels, settings, log=self.log, progress=self.progress, stop=self.stop))
            except Exception as e:  # noqa: BLE001
                self.log(f"Lỗi: {e}")
            finally:
                self.running = False

        threading.Thread(target=target, name="crawl", daemon=True).start()
        return True


STATE = CrawlState()


def _scheduler():
    """Tự chạy mỗi ngày (khi app đang mở), theo giờ đặt trong Cài đặt."""
    while True:
        time.sleep(30)
        try:
            s = db.get_settings()
            now = datetime.now()
            today = now.date().isoformat()
            if (s.get("auto_run") and not STATE.running and now.strftime("%H:%M") >= s.get("auto_run_time", "07:00")
                    and s.get("last_auto_run") != today):
                db.save_settings({"last_auto_run": today})
                span = int(s.get("span_days", 7))
                start = now.date() + timedelta(days=1)
                STATE.start({"start": start, "end": start + timedelta(days=span - 1)})
                STATE.log("Tự động chạy theo lịch hằng ngày.")
        except Exception:  # noqa: BLE001
            pass


threading.Thread(target=_scheduler, name="scheduler", daemon=True).start()
