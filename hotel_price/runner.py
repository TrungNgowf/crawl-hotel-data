"""Điều phối một lượt lấy giá.

Với mỗi ngày × khách sạn:
  1. Lấy trực tiếp từ từng OTA có link (Agoda, Booking.com, Trip.com).
  2. Nếu OTA nào bị chặn / lỗi / chỉ có giá chung (Trip.com) -> mở Google Hotels của khách sạn đó và
     lấy giá của chính OTA ấy mà Google hiển thị. Chưa có link Google thì tự tìm theo tên khách sạn
     (chỉ dùng khi tên Google tìm ra khớp, tránh lấy nhầm khách sạn).
Không vượt CAPTCHA / chống bot: OTA nào chặn thì bỏ qua lấy trực tiếp OTA đó trong lượt.
"""
import asyncio
import random
from datetime import date, timedelta

from playwright.async_api import async_playwright

from . import db
from .browser import launch
from .sites import SITES
from .sites.base import OTA_LABELS, Blocked, Query
from .sites.booking import booking_hint
from .sites.google import same_hotel, search_url

DIRECT = ("agoda", "booking", "trip")
WEAK = {"trip"}  # lấy trực tiếp chỉ có giá "From" chung, nên ưu tiên giá qua Google nếu có


def date_list(start: date, end: date, step: int = 1):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=max(1, step))


def prepare_hotels(hotels):
    """Bỏ khách sạn đang tắt; với OTA đang tắt thì coi như không có link (kể cả không lấy thay qua Google)."""
    out = []
    for h in hotels:
        if not h.get("enabled", 1):
            continue
        h = dict(h)
        off = db.otas_off(h)
        for k in off:
            h[f"{k}_url"] = ""
        h["google_off"] = "google" in off
        if any(h.get(f"{k}_url") for k in DIRECT) or (h.get("google_url") and not h["google_off"]):
            out.append(h)
    return out


def estimate_pages(hotels, n_dates: int, use_google=True) -> int:
    hotels = prepare_hotels(hotels)
    per_date = 0
    for h in hotels:
        per_date += sum(1 for k in DIRECT if h.get(f"{k}_url"))
        if use_google and not h["google_off"] and (h.get("google_url") or h.get("booking_url") or h.get("trip_url")):
            per_date += 1
    return per_date * n_dates


async def run_crawl(hotels, settings, log=print, progress=lambda done, total: None, stop=None):
    nights = int(settings["nights"])
    use_google = bool(settings.get("google_fallback", True))
    hotels = prepare_hotels(hotels)
    dates = list(date_list(settings["start"], settings["end"], int(settings.get("step", 1))))
    total = estimate_pages(hotels, len(dates), use_google)
    if not total:
        log("Chưa có khách sạn nào có link. Thêm đối thủ ở thanh bên trái trước.")
        return None

    run_id = db.start_run()
    blocked: set[str] = set()      # OTA đang chặn lấy trực tiếp trong lượt này
    google_miss: set[int] = set()  # khách sạn không tìm được trên Google
    done = saved = errors = 0
    delay = lambda: asyncio.sleep(random.uniform(float(settings["delay_min"]), float(settings["delay_max"])))  # noqa: E731

    def tick():
        nonlocal done, total
        done += 1
        total = max(total, done)
        progress(done, total)

    log(f"Bắt đầu: {len(hotels)} khách sạn × {len(dates)} ngày (khoảng {total} trang).")
    try:
        async with async_playwright() as p:
            ctx = await launch(p, settings, log)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            for d in dates:
                ci, co = d.isoformat(), (d + timedelta(days=nights)).isoformat()
                q = Query(ci, co, nights, int(settings["adults"]), int(settings.get("children", 0)),
                          int(settings["rooms"]), settings.get("currency", "VND"))
                for h in hotels:
                    if stop and stop.is_set():
                        break
                    need: set[str] = set()   # OTA cần lấy thay qua Google
                    for key in DIRECT:
                        url = h.get(f"{key}_url")
                        if not url:
                            continue
                        label = OTA_LABELS[key]
                        if key in blocked:
                            need.add(key)
                            db.save_fetch(run_id, h["id"], key, ci, "blocked", 0, "OTA chặn từ trước trong lượt")
                            if key == "booking" and use_google and not h.get("google_url") and not h.get("search_hint"):
                                try:  # chỉ đọc tên + thành phố để tìm trên Google
                                    h["search_hint"] = await booking_hint(page, url)
                                    tick()
                                    await delay()
                                except Exception:  # noqa: BLE001
                                    pass
                            continue
                        try:
                            res = await SITES[key][2](page, url, q)
                            db.save_rates(run_id, h["id"], res.rates)
                            h["search_hint"] = h.get("search_hint") or res.search_hint
                            if res.hotel_name and h.get("name_auto"):
                                db.set_real_name(h["id"], res.hotel_name)
                                h["name"], h["name_auto"] = res.hotel_name, 0
                            db.save_fetch(run_id, h["id"], key, ci, "ok" if res.rates else "soldout", len(res.rates))
                            saved += len(res.rates)
                            if key in WEAK:
                                need.add(key)
                            cheapest = min((r.price for r in res.rates if r.price), default=None)
                            log(f"{label} · {h['name']} · {ci}: "
                                + (f"{len(res.rates)} giá, thấp nhất {cheapest:,.0f}" if res.rates else "hết phòng / không có giá"))
                        except Blocked as e:
                            h["search_hint"] = h.get("search_hint") or e.search_hint
                            blocked.add(key)
                            need.add(key)
                            errors += 1
                            db.save_fetch(run_id, h["id"], key, ci, "blocked", 0, str(e))
                            log(f"{label} chặn lấy trực tiếp ({e})."
                                + (" Chuyển sang lấy qua Google Hotels." if use_google else ""))
                        except Exception as e:  # noqa: BLE001
                            need.add(key)
                            errors += 1
                            db.save_fetch(run_id, h["id"], key, ci, "error", 0, f"{type(e).__name__}: {e}")
                            log(f"{label} · {h['name']} · {ci}: lỗi — {type(e).__name__}: {str(e)[:120]}")
                        tick()
                        await delay()

                    # ---- Google Hotels: lấy thay cho OTA bị chặn/lỗi, hoặc khi người dùng có link Google
                    want_google = (use_google and not h["google_off"] and (need or h.get("google_url"))
                                   and "google" not in blocked)
                    if not want_google:
                        continue
                    if h["id"] in google_miss:
                        for key in need - WEAK:
                            db.save_fetch(run_id, h["id"], key, ci, "nogoogle", 0)
                        continue
                    gurl = h.get("google_url") or search_url(h.get("search_hint") or h["name"])
                    try:
                        res = await SITES["google"][2](page, gurl, q, "" if h.get("google_url") else h["name"])
                        if not h.get("google_url"):
                            if not res.rates or not same_hotel(h["name"], res.hotel_name):
                                google_miss.add(h["id"])
                                for key in need - WEAK:
                                    db.save_fetch(run_id, h["id"], key, ci, "nogoogle", 0, res.hotel_name)
                                log(f"Google Hotels · {h['name']}: không tìm thấy đúng khách sạn"
                                    + (f" (ra '{res.hotel_name}')" if res.hotel_name else "")
                                    + ". Hãy thêm link Google Hotels cho khách sạn này.")
                                tick()
                                await delay()
                                continue
                            if res.resolved_url:
                                db.set_google_url(h["id"], res.resolved_url)
                                h["google_url"] = res.resolved_url
                        db.save_rates(run_id, h["id"], res.rates)
                        saved += len(res.rates)
                        got = {r.ota for r in res.rates}
                        for key in sorted(need):
                            if key in got:
                                db.save_fetch(run_id, h["id"], key, ci, "google", 1)
                                if key in WEAK:  # có giá theo ngày qua Google -> bỏ giá "From" chung
                                    db.delete_rates(run_id, h["id"], key, ci)
                            elif key not in WEAK:
                                db.save_fetch(run_id, h["id"], key, ci, "missing", 0, "Google không có giá OTA này")
                        db.save_fetch(run_id, h["id"], "google", ci, "ok" if res.rates else "soldout", len(res.rates))
                        found = ", ".join(OTA_LABELS[k] for k in sorted(need & got)) or "không có OTA cần thay"
                        log(f"Google Hotels · {h['name']} · {ci}: {len(res.rates)} nhà cung cấp — lấy thay: {found}")
                    except Blocked as e:
                        blocked.add("google")
                        errors += 1
                        db.save_fetch(run_id, h["id"], "google", ci, "blocked", 0, str(e))
                        log(f"Google Hotels chặn ({e}). Bỏ qua Google trong lượt này.")
                    except Exception as e:  # noqa: BLE001
                        errors += 1
                        db.save_fetch(run_id, h["id"], "google", ci, "error", 0, f"{type(e).__name__}: {e}")
                        log(f"Google Hotels · {h['name']} · {ci}: lỗi — {type(e).__name__}: {str(e)[:120]}")
                    tick()
                    await delay()
                if stop and stop.is_set():
                    log("Đã dừng theo yêu cầu.")
                    break
            await ctx.close()
        status = "stopped" if stop and stop.is_set() else ("done" if not errors else "done_with_errors")
        db.finish_run(run_id, status, f"{saved} giá, {errors} lỗi")
        progress(total, total)
        log(f"Xong: {saved} giá" + (f", {errors} trang bị chặn/lỗi (đã lấy thay qua Google nếu có)." if errors else "."))
    except Exception as e:
        db.finish_run(run_id, "failed", str(e)[:300])
        log(f"Lỗi nghiêm trọng: {e}")
        raise
    return run_id
