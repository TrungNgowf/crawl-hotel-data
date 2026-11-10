"""Agoda: bắt JSON `api/v1/property/room-grid` mà trang chi tiết khách sạn tự gọi khi tải."""
import re

from .base import OTA_LABELS, CHILD_AGE, Blocked, FREE_CANCEL_RE, Query, Rate, Result, has_breakfast, with_params


async def crawl_agoda(page, url, q: Query) -> Result:
    params = {"checkIn": q.checkin, "los": q.nights, "rooms": q.rooms, "adults": q.adults,
              "children": q.children, "currencyCode": q.currency}
    if q.children:
        params["childages"] = ",".join([str(CHILD_AGE)] * q.children)
    async with page.expect_response(lambda r: "/api/v1/property/room-grid" in r.url, timeout=45000) as info:
        await page.goto(with_params(url, params), wait_until="domcontentloaded", timeout=60000)
    resp = await info.value
    if resp.status in (403, 429):
        raise Blocked(f"Agoda trả mã {resp.status}")
    data = await resp.json()

    currency = (data.get("analyticsContext", {}).get("charge_currency") or q.currency).upper()
    out = []
    for room in data.get("rooms") or []:
        if room.get("isSoldOut"):
            continue
        for offer in room.get("offers") or []:
            price = ((offer.get("price") or {}).get("final") or {}).get("amountNumber")
            if price is None:
                continue
            benefits = " | ".join(b.get("text", "") for b in offer.get("benefits") or [])
            cancel = ""
            for pol in offer.get("policies") or []:
                if "cancel" in (pol.get("name") or "").lower():
                    cancel = (pol.get("descriptions") or [""])[0]
            info_text = ", ".join((offer.get("price") or {}).get("priceInfo") or [])
            # tổng tiền khách trả khi đặt gói này (gồm thuế & phí), chia cho số đêm × số phòng
            per_book = (offer.get("analyticsContext") or {}).get("hotel_price_per_book")
            incl = round(float(per_book) / (q.nights * q.rooms)) if per_book else None
            out.append(Rate(
                source="agoda", ota="agoda", ota_label=OTA_LABELS["agoda"], checkin=q.checkin, checkout=q.checkout, adults=q.adults,
                room_name=room.get("name", ""), offer_name=offer.get("name") or "",
                price=price, price_incl=incl, currency=currency,  # Agoda: giá mỗi đêm
                price_note="Agoda: giá hiển thị chưa gồm thuế & phí; giá gồm thuế = tổng tiền khi đặt",
                breakfast=has_breakfast(benefits),
                free_cancel=bool(FREE_CANCEL_RE.search(cancel or benefits)),
                cancel_text=cancel,
            ))
    name = data.get("propertyName") or ""
    m = re.search(r"/hotel/([a-z-]+?)(?:-[a-z]{2})?\.html", url)
    city = m.group(1).replace("-", " ").replace(" island", "") if m else ""
    hint = name if city.replace(" ", "") in name.lower().replace(" ", "") else f"{name} {city}"
    return Result(out, name, search_hint=hint.strip())
