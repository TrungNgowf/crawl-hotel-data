"""Booking.com: đọc bảng phòng `#hprt-table` trong HTML trang chi tiết khách sạn.

Booking thường bỏ ngày/số khách khỏi URL khi trình duyệt chạy tự động (không có giá). Khi đó tool
báo "đang chặn" và bỏ qua Booking trong lượt, không cố vượt qua.
"""
from .base import OTA_LABELS, CHILD_AGE, base_url, Blocked, FREE_CANCEL_RE, Query, Rate, Result, has_breakfast, parse_money, with_params

EXTRACT_JS = r"""
() => {
  const rows = [...document.querySelectorAll('#hprt-table tbody tr')];
  let room = '';
  const name = (document.querySelector('#hp_hotel_name h2, h2.pp-header__title, [data-testid="property-name"]') || {}).innerText || '';
  return {name, rows: rows.map(tr => {
    const nameEl = tr.querySelector('.hprt-roomtype-icon-link, .hprt-roomtype-link');
    if (nameEl) room = nameEl.innerText.trim();
    const priceEl = tr.querySelector('.bui-price-display__value, .prco-valign-middle-helper');
    const taxEl = tr.querySelector('.prd-taxes-and-fees-under-price');
    const cond = tr.querySelector('.hprt-table-cell-conditions');
    return {room, price: priceEl ? priceEl.innerText.trim() : '',
            tax: taxEl ? taxEl.innerText.replace(/\s+/g, ' ').trim() : '',
            conditions: cond ? cond.innerText.replace(/\s+/g, ' ').trim() : ''};
  }).filter(r => r.price)};
}
"""


async def crawl_booking(page, url, q: Query) -> Result:
    params = {"checkin": q.checkin, "checkout": q.checkout, "group_adults": q.adults, "no_rooms": q.rooms,
              "group_children": q.children, "selected_currency": q.currency, "lang": "en-us"}
    if q.children:
        params["age"] = CHILD_AGE
    resp = await page.goto(with_params(url, params), wait_until="domcontentloaded", timeout=60000)
    if resp and resp.status in (403, 429):
        raise Blocked(f"Booking trả mã {resp.status}")
    hint = (await page.title()).split(" (")[0].strip()  # "Tên, Thành phố"
    if "checkin=" not in page.url:
        raise Blocked("Booking không nhận ngày đặt phòng khi trình duyệt chạy tự động", hint)
    try:
        await page.wait_for_selector("#hprt-table", timeout=20000)
    except Exception:
        html = (await page.content()).lower()
        if "captcha" in html or "are you a robot" in html:
            raise Blocked("Booking hiện CAPTCHA")
        return Result(search_hint=hint)  # hết phòng cho ngày này

    data = await page.evaluate(EXTRACT_JS)
    out = []
    for r in data["rows"]:
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
        elif price and "includes taxes" in r["conditions"].lower():
            incl = price
        out.append(Rate(
            source="booking", ota="booking", ota_label=OTA_LABELS["booking"], checkin=q.checkin, checkout=q.checkout, adults=q.adults, room_name=r["room"],
            price=price, price_incl=incl, currency=q.currency, price_note=note,
            breakfast=has_breakfast(r["conditions"]), free_cancel=bool(FREE_CANCEL_RE.search(r["conditions"])),
            cancel_text=r["conditions"][:200],
        ))
    return Result(out, data["name"].strip(), search_hint=hint)


async def booking_hint(page, url) -> str:
    """Đọc 'Tên, Thành phố' từ tiêu đề trang Booking (không cần ngày) — để tìm khách sạn trên Google."""
    await page.goto(base_url(url), wait_until="domcontentloaded", timeout=60000)
    return (await page.title()).split(" (")[0].strip()
