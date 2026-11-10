"""Google Hotels: đọc danh sách giá các OTA (Booking.com, Agoda, Trip.com, trang chính thức...) mà Google hiển thị.

Link: mở khách sạn trên https://www.google.com/travel/hotels rồi copy link. Ngày nhận/trả phòng được
mã hóa trong tham số `ts` của URL (protobuf base64) — tool tự tạo cho từng ngày.
Giới hạn: Google mặc định 2 khách; chỉ có giá thấp nhất mỗi nhà cung cấp, không có từng loại phòng.
"""
import base64
import re
from urllib.parse import quote, urlsplit

from .base import OTA_LABELS, Blocked, Query, Rate, Result, has_breakfast, parse_money, query_of

GENERIC = {"hotel", "hotels", "the", "and", "by", "resort", "spa", "da", "nang", "danang", "boutique", "&", "-"}


def ota_of(provider: str, official: bool) -> tuple[str, str]:
    """Tên nhà cung cấp trên Google -> (mã OTA, tên hiển thị)."""
    if official:
        return "official", OTA_LABELS["official"]
    p = provider.lower()
    for key, dom in (("booking", "booking.com"), ("agoda", "agoda"), ("trip", "trip.com")):
        if p.startswith(dom):
            return key, OTA_LABELS[key]
    return re.sub(r"[^a-z0-9]+", "-", p).strip("-"), provider


def _tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", name.lower()) if t not in GENERIC}


def same_hotel(wanted: str, found: str) -> bool:
    """Tên khách sạn Google tìm ra có khớp tên mình tìm không (tránh lấy nhầm khách sạn khác)."""
    a, b = _tokens(wanted), _tokens(found)
    return bool(a) and len(a & b) / len(a) >= 0.6

PRICE_LINE = re.compile(r"^(₫|US\$|\$|VND)\s?[\d.,]+$|^[\d.,]+\s?(₫|VND)$")


def _date(iso: str) -> bytes:
    y, m, d = (int(x) for x in iso.split("-"))
    return bytes([0x08, (y & 0x7F) | 0x80, y >> 7, 0x10, m, 0x18, d])


def make_ts(checkin: str, checkout: str, currency: str = "VND") -> str:
    """Tạo tham số `ts` của Google Travel cho ngày nhận/trả phòng và tiền tệ."""
    a = bytes([0x0A, 7]) + _date(checkin)
    c = bytes([0x12, 7]) + _date(checkout)
    inner = bytes([0x12, len(a + c)]) + a + c + bytes([0x32, 2, 8, 0])
    l3 = bytes([0x12, len(inner)]) + inner
    cur = bytes([0x3A, len(currency)]) + currency.encode()
    cur = bytes([0x0A, len(cur)]) + cur
    raw = bytes([8, 0, 0x1A, len(l3)]) + l3 + bytes([0x2A, len(cur)]) + cur
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def search_url(name: str) -> str:
    return f"https://www.google.com/travel/search?q={quote(name)}"


def build_url(url: str, q: Query) -> str:
    path = urlsplit(url).path
    m = re.search(r"/travel/hotels/entity/([^/?#]+)", path)
    common = f"hl=en&gl=vn&curr={q.currency}&ts={make_ts(q.checkin, q.checkout, q.currency)}"
    if m:
        return f"https://www.google.com/travel/hotels/entity/{m.group(1)}/prices?{common}"
    name = query_of(url).get("q")
    if not name:
        raise ValueError("Link Google Hotels cần là trang khách sạn (…/travel/hotels/entity/…) hoặc có ?q=tên khách sạn.")
    return f"https://www.google.com/travel/search?q={quote(name)}&{common}"


KNOWN = {"booking.com", "agoda", "trip.com", "expedia", "expedia.com.vn", "hotels.com", "traveloka.com", "klook",
         "priceline", "vio.com", "tripadvisor.com.vn", "kayak", "vn.kayak.com", "trivago", "skyscanner"}


def _blocks(segment: str):
    """Tách đoạn văn bản thành các khối, mỗi khối kết thúc bằng 'Visit site'."""
    lines = [ln.strip() for ln in segment.splitlines() if ln.strip() and ln.strip() != ","]
    block = []
    for ln in lines:
        if ln == "Visit site":
            yield block
            block = []
        else:
            block.append(ln)


def parse_featured(text: str, known: set[str]):
    """Mục 'Featured options' (quảng cáo) — nơi Google hay đặt Booking.com. Chỉ lấy dòng của nhà cung cấp,
    bỏ các dòng loại phòng con."""
    start, end = text.find("Featured options"), text.find("All options")
    if start < 0 or end < start:
        return []
    out = []
    for block in _blocks(text[start + len("Featured options"):end]):
        prices = [b for b in block if PRICE_LINE.match(b)]
        if block and prices and block[0].lower() in known:
            joined = " · ".join(block)
            out.append((block[0], parse_money(prices[-1]), "Free cancellation" in joined, False, has_breakfast(joined)))
    return out


def parse_options(text: str):
    """Tách mục 'All options' thành [(nhà cung cấp, giá, hủy miễn phí, là trang chính thức)]."""
    start = text.find("All options")
    if start < 0:
        return []
    end = min([i for i in (text.find("View more options", start), text.find("Sponsored", start)) if i > 0] or [len(text)])
    out = []
    for block in _blocks(text[start + len("All options"):end]):
        prices = [b for b in block if PRICE_LINE.match(b)]
        names = [b for b in block if not PRICE_LINE.match(b) and not b.startswith("Free cancellation")
                 and b != "Official Site"]
        if prices and names:
            out.append((names[0], parse_money(prices[-1]), any(b.startswith("Free cancellation") for b in block),
                        "Official Site" in block, None))
    return out


async def _wait_options(page, timeout=20000) -> bool:
    try:
        await page.wait_for_function("document.body && document.body.innerText.includes('All options')", timeout=timeout)
        return True
    except Exception:
        return False


async def crawl_google(page, url, q: Query, want: str = "") -> Result:
    """want: tên khách sạn cần tìm (khi chưa có link Google) — nếu Google trả về danh sách, mở đúng khách sạn đó."""
    resp = await page.goto(build_url(url, q), wait_until="domcontentloaded", timeout=60000)
    if "/sorry/" in page.url or (resp and resp.status == 429):
        raise Blocked("Google yêu cầu xác minh (unusual traffic)")
    if not await _wait_options(page, 12000 if want else 20000):
        body = await page.inner_text("body")
        if "unusual traffic" in body.lower() or "captcha" in body.lower():
            raise Blocked("Google yêu cầu xác minh (unusual traffic)")
        if want:  # trang danh sách kết quả -> bấm vào khách sạn có tên khớp
            names = [ln.strip() for ln in body.splitlines() if 3 < len(ln.strip()) < 90 and same_hotel(want, ln.strip())]
            if names:
                await page.get_by_text(names[0], exact=True).first.click()
                await _wait_options(page)
    text = await page.inner_text("body")
    name = (await page.title()).split(" - Google")[0].strip()
    options = parse_options(text)
    known = KNOWN | {o[0].lower() for o in options}
    best: dict[str, Rate] = {}
    for provider, price, free_cancel, official, breakfast in options + parse_featured(text, known):
        if price is None:
            continue
        key, label = ota_of(provider, official or same_hotel(name, provider))
        if key in best and best[key].price <= price:
            continue
        best[key] = Rate(
            source="google", checkin=q.checkin, checkout=q.checkout, adults=2,
            room_name=f"Giá thấp nhất trên {label}", price=price, price_incl=price, currency=q.currency,
            price_note="Qua Google Hotels: gồm thuế & phí, mặc định 2 khách",
            breakfast=breakfast, free_cancel=free_cancel, cancel_text="Free cancellation" if free_cancel else "",
            ota=key, ota_label=label, via="google",
        )
    m = re.search(r'/travel/hotels/entity/([A-Za-z0-9_-]+)', page.url) or \
        re.search(r'href="(?:https://www\.google\.com)?/travel/hotels/entity/([A-Za-z0-9_-]+)', await page.content())
    resolved = f"https://www.google.com/travel/hotels/entity/{m.group(1)}" if m else ""
    return Result(sorted(best.values(), key=lambda r: r.price), name, resolved)
