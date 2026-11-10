import re
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlsplit, parse_qs

CHILD_AGE = 8  # tuổi mặc định của trẻ em khi tìm phòng


@dataclass
class Query:
    checkin: str
    checkout: str
    nights: int = 1
    adults: int = 2
    children: int = 0
    rooms: int = 1
    currency: str = "VND"


@dataclass
class Rate:
    source: str
    checkin: str
    checkout: str
    adults: int
    room_name: str
    offer_name: str = ""
    price: float | None = None
    currency: str = "VND"
    price_note: str = ""
    breakfast: bool | None = None
    free_cancel: bool | None = None
    cancel_text: str = ""
    ota: str = ""          # OTA bán giá này (agoda | booking | trip | expedia | official...); trống = source
    ota_label: str = ""    # tên hiển thị của OTA
    via: str = "direct"    # direct = lấy thẳng từ OTA; google = đọc từ Google Hotels
    price_incl: float | None = None  # giá/đêm đã gồm thuế & phí (giá khách trả khi đặt), nếu biết


OTA_LABELS = {"agoda": "Agoda", "booking": "Booking.com", "trip": "Trip.com", "official": "Website khách sạn"}


@dataclass
class Result:
    rates: list[Rate] = field(default_factory=list)
    hotel_name: str = ""   # tên thật đọc từ trang (để thay tên đoán từ link)
    resolved_url: str = "" # Google: link trang khách sạn tìm được (lưu lại cho lần sau)
    search_hint: str = ""  # "tên, thành phố" để tìm khách sạn trên Google khi cần


class Blocked(Exception):
    """Trang hiện CAPTCHA / chặn truy cập. Không cố vượt qua — dừng OTA đó trong lượt."""

    def __init__(self, msg, search_hint=""):
        super().__init__(msg)
        self.search_hint = search_hint


def base_url(url: str) -> str:
    return url.strip().split("?")[0].split("#")[0]


def query_of(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def with_params(url: str, params: dict) -> str:
    return base_url(url) + "?" + urlencode(params)


def parse_money(text: str) -> float | None:
    if not text:
        return None
    digits = re.sub(r"[^\d.,]", "", text)
    if not digits:
        return None
    # "1,192,918" / "1.192.918" -> 1192918 ; "54.95" -> 54.95
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", digits):
        return float(re.sub(r"[.,]", "", digits))
    return float(digits.replace(",", ""))


FREE_CANCEL_RE = re.compile(r"free cancel|cancel for free|hủy miễn phí", re.I)
BREAKFAST_RE = re.compile(r"breakfast|bữa sáng", re.I)
NO_BREAKFAST_RE = re.compile(r"no breakfast|breakfast not included|without breakfast|room only", re.I)


def has_breakfast(text: str) -> bool:
    return bool(BREAKFAST_RE.search(text)) and not NO_BREAKFAST_RE.search(text)


DOMAINS = {"agoda": "agoda.com", "booking": "booking.com", "trip": "trip.com"}


def detect_ota(url: str) -> str | None:
    parts = urlsplit(url.strip())
    host = parts.hostname or ""
    if re.fullmatch(r"(www\.)?google\.[a-z.]+", host) and parts.path.startswith("/travel"):
        return "google"
    for key, dom in DOMAINS.items():
        if host == dom or host.endswith("." + dom):
            return key
    return None


def guess_name(url: str) -> str:
    """Đoán tên khách sạn từ link (sẽ được thay bằng tên thật sau lần lấy giá đầu)."""
    ota, path = detect_ota(url), urlsplit(url).path
    slug = ""
    if ota == "agoda":
        parts = [p for p in path.split("/") if p and not re.fullmatch(r"[a-z]{2}-[a-z]{2}", p)]
        slug = parts[0] if parts else ""
    elif ota == "booking":
        slug = path.rstrip("/").split("/")[-1].split(".")[0]
    elif ota == "google":
        return (query_of(url).get("q") or "Khách sạn trên Google").strip()
    elif ota == "trip":
        m = re.search(r"hotels/([a-z0-9-]+?)-hotel-detail-(\d+)", path)
        slug = m.group(1) if m else ("Trip " + (query_of(url).get("hotelId") or ""))
    if not slug or slug == "hotels":
        return url[:60]
    return " ".join(w.capitalize() for w in slug.split("-") if w)
