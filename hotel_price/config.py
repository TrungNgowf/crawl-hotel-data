"""Đường dẫn dữ liệu và cài đặt mặc định."""
import os
from pathlib import Path

HOME = Path(os.environ.get("HOTEL_PRICE_HOME", Path.home() / ".hotel-price-tool"))
DATA_DIR = HOME / "data"
DB_PATH = DATA_DIR / "hotel_price.db"
PROFILE_DIR = DATA_DIR / "browser-profile"
EXPORT_DIR = DATA_DIR / "exports"

DEFAULT_SETTINGS = {
    "headless": True,          # chạy trình duyệt ngầm (không hiện cửa sổ)
    "delay_min": 4,            # giây nghỉ tối thiểu giữa 2 lần mở trang
    "delay_max": 10,           # giây nghỉ tối đa
    "browser_path": "",        # để trống = tự dò Chrome / Edge / Brave
    "span_days": 7,            # khoảng ngày nhận phòng (dùng cho lượt tự động)
    "step": 1,                 # cách nhau bao nhiêu ngày
    "nights": 1,
    "adults": 2,
    "children": 0,
    "rooms": 1,
    "currency": "VND",
    "auto_run": False,         # tự chạy mỗi ngày khi app đang mở
    "auto_run_time": "07:00",
}

for d in (DATA_DIR, PROFILE_DIR, EXPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)
