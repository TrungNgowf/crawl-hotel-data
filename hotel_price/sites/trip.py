"""Trip.com: chỉ lấy giá thấp nhất ("From ...") mà trang chi tiết trả về sẵn trong HTML.

Trip.com chặn API danh sách phòng với trình duyệt tự động; tool không cố vượt qua, nên chỉ có
giá thấp nhất, không có từng loại phòng. Giá này có thể không thay đổi theo ngày.
"""
import re

from .base import OTA_LABELS, CHILD_AGE, Blocked, Query, Rate, Result, parse_money, query_of

PRICE_RE = re.compile(r'"priceRange"\s*:\s*"From\s+([A-Z]{3}|US\$|\$)\s*([\d.,]+)"')


async def crawl_trip(page, url, q: Query) -> Result:
    qs = query_of(url)
    hotel_id = qs.get("hotelId") or qs.get("hotelid")
    if not hotel_id:
        m = re.search(r"detail-(\d+)", url)
        hotel_id = m.group(1) if m else None
    if not hotel_id:
        raise ValueError("Link Trip.com cần có hotelId (mở trang khách sạn rồi copy link).")
    params = f"hotelId={hotel_id}&checkIn={q.checkin}&checkOut={q.checkout}&adult={q.adults}&crn={q.rooms}&curr={q.currency}"
    if q.children:
        params += f"&children={q.children}&ages={','.join([str(CHILD_AGE)] * q.children)}"
    if qs.get("cityId"):
        params = f"cityId={qs['cityId']}&" + params
    resp = await page.goto(f"https://www.trip.com/hotels/detail/?{params}", wait_until="domcontentloaded", timeout=60000)
    if resp and resp.status in (403, 429, 430):
        raise Blocked(f"Trip.com trả mã {resp.status}")
    html = await page.content()
    title = await page.title()
    name = title.split(" (")[0].split(" - ")[0].strip()
    hint = title.split(" - ")[0].replace("(", "").replace(")", "").strip()
    m = PRICE_RE.search(html)
    if not m:
        return Result([], name, search_hint=hint)
    cur = "USD" if "$" in m.group(1) else m.group(1)
    return Result([Rate(
        source="trip", ota="trip", ota_label=OTA_LABELS["trip"], checkin=q.checkin, checkout=q.checkout, adults=q.adults,
        room_name="(Giá thấp nhất)", price=parse_money(m.group(2)), currency=cur,
        price_note="Giá 'From' chung của Trip.com — có thể không đổi theo ngày",
    )], name, search_hint=hint)
