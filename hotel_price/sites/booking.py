"""Booking.com: đọc bảng phòng trong HTML bằng Scrapling.

Trang được mở bằng StealthySession riêng (trình duyệt thật, tiếng Việt, giờ Việt Nam),
cùng kiểu phiên với bản không bị Booking bỏ ngày. Link giữ tham số sẵn có, rồi gắn
ngày và số khách. Giá vẫn chỉ lấy từ bảng phòng, không đọc số tiền trôi trên trang.
Selector bám class hiện tại của `#hprt-table`. Bảng và ô giá được lưu lại; nếu Booking
đổi id/class của hai chỗ đó, adaptive tìm phần tử giống nhất. Tên phòng, thuế và
điều kiện chỉ đọc đúng selector, vì những ô này có thể không có trên một số dòng.
Nếu sau khi trang ổn định mà URL không còn ngày nhận phòng, tool báo "đang chặn"
và bỏ qua, không lấy giá của ngày khác.
"""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from scrapling.parser import Selector

from .. import db
from ..browser import find_browser
from ..config import DATA_DIR
from .base import OTA_LABELS, CHILD_AGE, base_url, Blocked, FREE_CANCEL_RE, Query, Rate, Result, has_breakfast, parse_money

_STORAGE = {
    "storage_file": str(DATA_DIR / "booking-elements.db"),
    "url": "https://www.booking.com",
}
# Chỉ gọi adaptive khi trang vẫn có giá. Trang hết phòng không có số tiền thì khỏi tìm lại.
_MONEY = re.compile(r"(?:₫|VND|US\$|\$)\s*\d|\d{1,3}(?:[.,]\d{3})+")

_TABLE = "#hprt-table"
_ROWS = "tbody tr"
_NAME = ("#hp_hotel_name h2", "h2.pp-header__title", '[data-testid="property-name"]')
_ROOM = (".hprt-roomtype-icon-link", ".hprt-roomtype-link")
_PRICE = (".bui-price-display__value", ".prco-valign-middle-helper")
_TAX = (".prd-taxes-and-fees-under-price",)
_COND = (".hprt-table-cell-conditions",)


def _text(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", str(el.get_all_text(separator=" ", strip=True))).strip()


def _page(html: str) -> Selector:
    return Selector(html, url=_STORAGE["url"], adaptive=True, storage_args=_STORAGE)


def _css(root, selectors: tuple[str, ...], identifier: str) -> str:
    """Đọc đúng selector và lưu phần tử. Không đoán khi selector không khớp —
    ô thuế/điều kiện/tên phòng có thể vắng trên một số dòng."""
    for sel in selectors:
        found = root.css(sel, identifier=identifier, auto_save=True)
        if found:
            return _text(found[0])
    return ""


def _price_text(row) -> str:
    for sel in _PRICE:
        found = row.css(sel, identifier="booking-price", auto_save=True)
        if found:
            return _text(found[0])
    if not _MONEY.search(_text(row)):
        return ""
    found = row.css(_PRICE[0], identifier="booking-price", adaptive=True, percentage=55)
    for el in found:
        text = _text(el)
        if parse_money(text) is not None:
            return text
    return ""


def parse_booking_html(html: str) -> dict | None:
    """Trả về {name, rows} hoặc None khi không còn bảng phòng."""
    page = _page(html)
    found = page.css(_TABLE, identifier="booking-room-table", auto_save=True)
    if found:
        table = found[0]
    elif _MONEY.search(_text(page)):
        found = page.css(_TABLE, identifier="booking-room-table", adaptive=True, percentage=55)
        if not found or not _MONEY.search(_text(found[0])):
            return None
        table = found[0]
    else:
        return None

    name = _css(page, _NAME, "booking-hotel-name")
    rows = []
    room = ""
    for tr in table.css(_ROWS):
        room_name = _css(tr, _ROOM, "booking-room-name")
        if room_name:
            room = room_name
        price = _price_text(tr)
        if not price:
            continue
        rows.append({
            "room": room,
            "price": price,
            "tax": _css(tr, _TAX, "booking-tax"),
            "conditions": _css(tr, _COND, "booking-conditions"),
        })
    return {"name": name, "rows": rows}


def _rates(rows: list[dict], q: Query) -> list[Rate]:
    out = []
    for r in rows:
        price = parse_money(r["price"])
        note = "1 đêm"
        if q.nights > 1 and price:  # Booking hiện tổng tiền cả kỳ ở -> quy về giá mỗi đêm
            price = round(price / q.nights)
            note = f"Trung bình/đêm (tổng {q.nights} đêm)"
        incl = None
        if r["tax"]:
            note += f"; {r['tax']}"
            tax = parse_money(r["tax"])  # "+VND 123,456 taxes and fees"
            if price and tax:
                incl = round(price + tax / max(1, q.nights))
        elif price and any(s in r["conditions"].lower() for s in ("includes taxes", "gồm thuế", "bao gồm thuế")):
            incl = price
        out.append(Rate(
            source="booking", ota="booking", ota_label=OTA_LABELS["booking"], checkin=q.checkin, checkout=q.checkout, adults=q.adults, room_name=r["room"],
            price=price, price_incl=incl, currency=q.currency, price_note=note,
            breakfast=has_breakfast(r["conditions"]), free_cancel=bool(FREE_CANCEL_RE.search(r["conditions"])),
            cancel_text=r["conditions"][:200],
        ))
    return out


def build_booking_url(url: str, q: Query) -> str:
    """Gắn ngày lên link khách sạn, giữ query cũ. Tuổi trẻ em lặp lại thành age=8&age=8."""
    parts = urlsplit(url.strip())
    updates = {
        "checkin": q.checkin,
        "checkout": q.checkout,
        "group_adults": str(q.adults),
        "group_children": str(q.children),
        "no_rooms": str(q.rooms),
        "selected_currency": q.currency,
        "lang": "vi",
    }
    drop = {key.lower() for key in updates} | {"age"}
    kept = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in drop]
    items = kept + list(updates.items())
    items.extend(("age", str(CHILD_AGE)) for _ in range(q.children))
    return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, urlencode(items), parts.fragment))


async def _settle(page):
    """Đóng banner cookie và cuộn xuống, để bảng phòng kịp render trước khi đọc."""
    for label in ("Accept all", "Accept", "Đồng ý", "Chấp nhận", "I agree", "Got it", "OK"):
        try:
            button = page.get_by_role("button", name=label, exact=True)
            if await button.count() > 0:
                await button.first.click(timeout=700)
                break
        except Exception:
            continue
    try:
        await page.mouse.wheel(0, 2000)
        await page.wait_for_timeout(600)
        await page.mouse.wheel(0, 2200)
        await page.wait_for_timeout(500)
    except Exception:
        return


_cfg = {"headless": True, "browser_path": ""}
_session = None


def configure_booking(settings: dict):
    """Gọi một lần đầu lượt crawl. Booking dùng phiên riêng, không dùng trình duyệt chung."""
    _cfg["headless"] = bool(settings.get("headless", True))
    _cfg["browser_path"] = settings.get("browser_path", "")


async def close_booking():
    global _session
    session, _session = _session, None
    if session is None:
        return
    try:
        await session.__aexit__(None, None, None)
    except Exception:
        return


async def _booking_session():
    """Cùng kiểu phiên với bản không bị Booking cắt ngày: Chrome/Brave thật, vi-VN, giờ VN."""
    global _session
    if _session is not None:
        return _session
    from scrapling.fetchers import AsyncStealthySession

    exe = find_browser(_cfg["browser_path"])
    profile = DATA_DIR / "booking-profile"
    profile.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "headless": _cfg["headless"],
        "real_chrome": exe is not None,
        "locale": "vi-VN",
        "timezone_id": "Asia/Ho_Chi_Minh",
        "solve_cloudflare": True,
        "block_ads": True,
        "google_search": False,
        "network_idle": False,
        "timeout": 60000,
        "user_data_dir": str(profile),
    }
    if exe:
        kwargs["executable_path"] = exe
    while True:
        try:
            session = AsyncStealthySession(**kwargs)
            break
        except TypeError as exc:
            match = re.search(r"unexpected keyword argument '(\w+)'", str(exc))
            if not match or match.group(1) not in kwargs:
                raise
            kwargs.pop(match.group(1))
    await session.__aenter__()
    _session = session
    return session


async def _load(url: str) -> tuple[str, str, int | None]:
    seen: dict[str, str] = {}

    async def action(page):
        seen["url"] = page.url
        await _settle(page)
        seen["url"] = page.url

    session = await _booking_session()
    response = await session.fetch(
        url,
        page_action=action,
        timeout=60000,
        wait=1200,
        wait_selector="#hprt-table",
        wait_selector_state="attached",
        google_search=False,
        network_idle=False,
        load_dom=True,
        solve_cloudflare=True,
    )
    html = str(getattr(response, "html_content", "") or "")
    status = getattr(response, "status", None)
    return seen.get("url", ""), html, status if isinstance(status, int) else None


def _hint_from(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    title = re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
    return title.split(" (")[0].strip()


async def crawl_booking(page, url, q: Query) -> Result:
    del page  # Booking không đi qua trình duyệt chung của Agoda/Google
    final_url, html, status = await _load(build_booking_url(url, q))
    if status in (403, 429):
        raise Blocked(f"Booking trả mã {status}")
    hint = _hint_from(html)  # "Tên, Thành phố"
    low = html.lower()
    if "captcha" in low or "are you a robot" in low:
        raise Blocked("Booking hiện CAPTCHA", hint)
    if "checkin=" not in final_url.lower():
        raise Blocked("Booking không nhận ngày đặt phòng khi trình duyệt chạy tự động", hint)
    parsed = parse_booking_html(html)
    if not parsed:
        return Result(search_hint=hint)  # hết phòng cho ngày này
    return Result(_rates(parsed["rows"], q), parsed["name"].strip(), search_hint=hint)


async def booking_hint(page, url) -> str:
    """Đọc 'Tên, Thành phố' từ tiêu đề trang Booking (không cần ngày) — để tìm khách sạn trên Google."""
    try:
        _final, html, _status = await _load(base_url(url))
        hint = _hint_from(html)
        if hint:
            return hint
    except Exception:
        pass
    await page.goto(base_url(url), wait_until="domcontentloaded", timeout=60000)
    return (await page.title()).split(" (")[0].strip()
