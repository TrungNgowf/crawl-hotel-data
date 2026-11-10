"""Lưu trữ SQLite: khách sạn đối thủ (mỗi KS có link nhiều OTA), kết quả giá, cài đặt."""
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import DB_PATH, DEFAULT_SETTINGS

URL_FIELDS = {"agoda": "agoda_url", "booking": "booking_url", "trip": "trip_url", "google": "google_url"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS hotels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    agoda_url TEXT DEFAULT '',
    booking_url TEXT DEFAULT '',
    trip_url TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    message TEXT
);
CREATE TABLE IF NOT EXISTS rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    hotel_id INTEGER,
    source TEXT,          -- trang tool mở: agoda | booking | trip | google
    checkin TEXT,
    checkout TEXT,
    adults INTEGER,
    room_name TEXT,
    offer_name TEXT,
    price REAL,
    currency TEXT,
    price_note TEXT,
    breakfast INTEGER,
    free_cancel INTEGER,
    cancel_text TEXT,
    crawled_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_rates_run ON rates(run_id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    hotel_id INTEGER,
    source TEXT,      -- OTA: agoda | booking | trip | google
    checkin TEXT,
    status TEXT,      -- ok | soldout | blocked | error | google (đã lấy thay qua Google) | missing
    n INTEGER,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetches_run ON fetches(run_id);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _add_column(c, table, col, ddl):
    if col not in {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError as e:  # 2 tab mở cùng lúc cùng thêm cột
            if "duplicate column" not in str(e):
                raise


def init():
    with connect() as c:
        c.executescript(SCHEMA)
        _add_column(c, "hotels", "name_auto", "INTEGER DEFAULT 0")  # tên đoán từ link, thay bằng tên thật sau
        _add_column(c, "hotels", "google_url", "TEXT DEFAULT ''")
        _add_column(c, "hotels", "enabled", "INTEGER DEFAULT 1")    # 0 = tạm tắt, không lấy giá
        _add_column(c, "hotels", "otas_off", "TEXT DEFAULT ''")    # OTA tạm tắt, vd "booking,trip"
        _add_column(c, "rates", "ota", "TEXT")   # OTA bán giá này: agoda | booking | trip | expedia | official ...
        _add_column(c, "rates", "ota_label", "TEXT")
        _add_column(c, "rates", "via", "TEXT")   # direct | google
        _add_column(c, "rates", "price_incl", "REAL")  # giá/đêm gồm thuế & phí (nếu biết)


def now():
    return datetime.now().isoformat(timespec="seconds")


# ---- hotels ----
def list_hotels():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM hotels ORDER BY id")]


def get_hotel(hotel_id):
    with connect() as c:
        r = c.execute("SELECT * FROM hotels WHERE id=?", (hotel_id,)).fetchone()
        return dict(r) if r else None


def save_hotel(hotel_id, name, urls: dict, name_auto=False):
    """Thêm (hotel_id=None) hoặc sửa khách sạn. urls: {agoda, booking, trip, google}."""
    vals = [urls.get(k, "").strip() for k in URL_FIELDS]
    with connect() as c:
        if hotel_id:
            c.execute("UPDATE hotels SET name=?, agoda_url=?, booking_url=?, trip_url=?, google_url=?, name_auto=? "
                      "WHERE id=?", (name.strip(), *vals, int(name_auto), hotel_id))
        else:
            c.execute("INSERT INTO hotels(name, agoda_url, booking_url, trip_url, google_url, name_auto, created_at) "
                      "VALUES (?,?,?,?,?,?,?)", (name.strip(), *vals, int(name_auto), now()))


def set_hotel_enabled(hotel_id, enabled: bool):
    with connect() as c:
        c.execute("UPDATE hotels SET enabled=? WHERE id=?", (int(enabled), hotel_id))


def set_otas_off(hotel_id, otas_off):
    with connect() as c:
        c.execute("UPDATE hotels SET otas_off=? WHERE id=?", (",".join(sorted(otas_off)), hotel_id))


def otas_off(h) -> set[str]:
    return set(filter(None, (h.get("otas_off") or "").split(",")))


def delete_hotel(hotel_id):
    with connect() as c:
        c.execute("DELETE FROM hotels WHERE id=?", (hotel_id,))


def set_real_name(hotel_id, name):
    if name:
        with connect() as c:
            c.execute("UPDATE hotels SET name=?, name_auto=0 WHERE id=? AND name_auto=1", (name.strip()[:200], hotel_id))


def set_google_url(hotel_id, url):
    with connect() as c:
        c.execute("UPDATE hotels SET google_url=? WHERE id=? AND COALESCE(google_url,'')=''", (url, hotel_id))


def merge_single_link_hotels():
    """Bản trước lưu mỗi link thành 1 khách sạn. Gộp các dòng có cùng tên thành 1 khách sạn."""
    hotels = list_hotels()
    groups = {}
    for h in hotels:
        key = re.sub(r"[^a-z0-9]", "", h["name"].lower())
        groups.setdefault(key, []).append(h)
    with connect() as c:
        for hs in groups.values():
            if len(hs) < 2:
                continue
            keep, rest = hs[0], hs[1:]
            for h in rest:
                for f in URL_FIELDS.values():
                    if h[f] and not keep[f]:
                        keep[f] = h[f]
                c.execute("UPDATE rates SET hotel_id=? WHERE hotel_id=?", (keep["id"], h["id"]))
                c.execute("UPDATE fetches SET hotel_id=? WHERE hotel_id=?", (keep["id"], h["id"]))
                c.execute("DELETE FROM hotels WHERE id=?", (h["id"],))
            c.execute("UPDATE hotels SET agoda_url=?, booking_url=?, trip_url=?, google_url=? WHERE id=?",
                      (*[keep[f] for f in URL_FIELDS.values()], keep["id"]))


# ---- runs & rates ----
def start_run():
    with connect() as c:
        return c.execute("INSERT INTO runs(started_at, status) VALUES (?, 'running')", (now(),)).lastrowid


def finish_run(run_id, status, message=""):
    with connect() as c:
        c.execute("UPDATE runs SET finished_at=?, status=?, message=? WHERE id=?", (now(), status, message, run_id))


def list_runs(limit=30):
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT r.*, (SELECT COUNT(*) FROM rates WHERE run_id=r.id) AS n FROM runs r ORDER BY id DESC LIMIT ?",
            (limit,))]


def get_run(run_id):
    with connect() as c:
        r = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(r) if r else None


def _b(v):
    return None if v is None else int(bool(v))


def save_rates(run_id, hotel_id, rates):
    with connect() as c:
        c.executemany(
            """INSERT INTO rates(run_id, hotel_id, source, ota, ota_label, via, checkin, checkout, adults, room_name,
               offer_name, price, price_incl, currency, price_note, breakfast, free_cancel, cancel_text, crawled_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(run_id, hotel_id, r.source, r.ota or r.source, r.ota_label, r.via, r.checkin, r.checkout, r.adults,
              r.room_name, r.offer_name, r.price, r.price_incl, r.currency, r.price_note, _b(r.breakfast), _b(r.free_cancel),
              r.cancel_text, now()) for r in rates],
        )


def delete_rates(run_id, hotel_id, source, checkin):
    with connect() as c:
        c.execute("DELETE FROM rates WHERE run_id=? AND hotel_id=? AND source=? AND checkin=?",
                  (run_id, hotel_id, source, checkin))


def rates_for_run(run_id):
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT rates.*, hotels.name AS hotel FROM rates LEFT JOIN hotels ON hotels.id = rates.hotel_id
               WHERE run_id=? ORDER BY checkin, hotel, price""", (run_id,))]


def save_fetch(run_id, hotel_id, source, checkin, status, n=0, message=""):
    with connect() as c:
        c.execute("INSERT INTO fetches(run_id, hotel_id, source, checkin, status, n, message) VALUES (?,?,?,?,?,?,?)",
                  (run_id, hotel_id, source, checkin, status, n, message[:300]))


def fetches_for_run(run_id):
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT fetches.*, hotels.name AS hotel FROM fetches LEFT JOIN hotels ON hotels.id = fetches.hotel_id
               WHERE run_id=?""", (run_id,))]


# ---- settings ----
def get_settings():
    s = dict(DEFAULT_SETTINGS)
    with connect() as c:
        for row in c.execute("SELECT key, value FROM settings"):
            s[row["key"]] = json.loads(row["value"])
    return s


def save_settings(values: dict):
    with connect() as c:
        c.executemany("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                      [(k, json.dumps(v, default=str)) for k, v in values.items()])
