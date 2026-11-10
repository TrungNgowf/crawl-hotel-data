"""Giao diện Streamlit. Chạy bằng `uv run hotel-price` (không chạy trực tiếp file này)."""
import io
from datetime import date, time as dtime, timedelta

import pandas as pd
import streamlit as st

from hotel_price import __version__, db
from hotel_price.export import to_excel
from hotel_price.runner import date_list, estimate_pages
from hotel_price.sites.base import OTA_LABELS, detect_ota, guess_name
from hotel_price.state import STATE

st.set_page_config(page_title="Theo dõi giá đối thủ", page_icon="🏨", layout="wide")
db.init()
s = db.get_settings()
if not s.get("merged_v2"):  # bản trước lưu mỗi link 1 khách sạn -> gộp theo tên
    db.merge_single_link_hotels()
    db.save_settings({"merged_v2": True})

LINK_OTAS = {"agoda": "Agoda", "booking": "Booking.com", "trip": "Trip.com", "google": "Google Hotels"}
DIRECT_OTAS = ["agoda", "booking", "trip"]          # OTA lấy giá trực tiếp
OTA_COLOR = {"agoda": "#E5484D", "booking": "#2B7FE0", "trip": "#F08C00", "google": "#2FA36B"}  # màu nhận diện nguồn
MAIN_OTAS = ["agoda", "booking", "trip", "official"]
GOOGLE_COL = "Google (tham khảo)"                   # Google Hotels: nguồn tham khảo, luôn ở cột riêng
CURRENCIES = ["VND", "USD"]
DOW = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def money(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.0f}".replace(",", ".") if v >= 100 else f"{v:,.2f}"


def day_label(iso):
    d = date.fromisoformat(iso)
    return f"{DOW[d.weekday()]} {d:%d/%m}"


st.html("""<style>
  .hp-legend {font-size: .85rem; opacity: .75;}
  /* ---- thẻ khách sạn đối thủ ở thanh bên */
  [class*="st-key-hcard-"] {padding: .5rem .75rem .65rem; gap: .45rem;}
  [class*="st-key-hcard-off-"] {border-style: dashed; padding-bottom: .5rem;}
  [class*="st-key-hcard-off-"] [data-testid="stMarkdownContainer"] {opacity: .55;}
  [class*="st-key-hcard-"] [data-testid="stMarkdownContainer"] p {margin-bottom: 0; line-height: 1.3;}
  [class*="st-key-hcard-"] [data-testid="stHorizontalBlock"] {gap: .25rem; flex-wrap: nowrap;}
  [class*="st-key-hcard-"] [data-testid="stCaptionContainer"] {margin-top: -.2rem;}
  /* nút ⋯: gọn, không mũi tên */
  [class*="st-key-hcard-"] [data-testid="stPopoverButton"] {min-height: 1.75rem; padding: 0 .3rem; opacity: .6;}
  [class*="st-key-hcard-"] [data-testid="stPopoverButton"]:hover {opacity: 1;}
  [class*="st-key-hcard-"] [data-testid="stPopoverButton"] div[aria-hidden="true"] {display: none;}
  /* nút OTA: mỗi OTA một màu (đặt qua --ota ở từng nút), tắt thì mờ */
  [class*="st-key-otas"] button[data-variant="pills"] {padding: .1rem .6rem; min-height: 1.7rem; border-color: transparent;
    background: color-mix(in srgb, currentColor 7%, transparent); color: inherit;}
  [class*="st-key-otas"] button[data-variant="pills"] p {font-size: .82rem; opacity: .6;}
  [class*="st-key-otas"] button[data-variant="pills"] p::before {content: ""; display: inline-block; width: .5em;
    height: .5em; border-radius: 50%; margin-right: .4em; vertical-align: .08em; background: var(--ota); opacity: .55;}
  [class*="st-key-otas"] button[data-variant="pills"]:hover {border-color: var(--ota); color: inherit;}
  [class*="st-key-otas"] button[data-variant="pills"][data-selected="true"] {border-color: var(--ota); color: inherit;
    background: color-mix(in srgb, var(--ota) 16%, transparent);}
  [class*="st-key-otas"] button[data-variant="pills"][data-selected="true"] p {opacity: 1; font-weight: 600;}
  [class*="st-key-otas"] button[data-variant="pills"][data-selected="true"] p::before {opacity: 1;}
  /* Google (tham khảo): hàng riêng, ngăn bằng đường kẻ mảnh */
  [class*="st-key-gref"] {width: 100% !important; margin-top: .1rem; padding-top: .55rem;
    border-top: 1px solid color-mix(in srgb, currentColor 14%, transparent);}
  [class*="st-key-gref"] label p {font-size: .82rem;}
</style>""")


def ota_pill_css(hid, offered):
    """Gán màu riêng cho từng nút OTA của 1 khách sạn (theo thứ tự nút)."""
    return "".join(f'.st-key-otas{hid} button[data-variant="pills"]:nth-of-type({i}) {{--ota: {OTA_COLOR[k]};}}'
                   for i, k in enumerate(offered, 1))


# ================================================================== Dialog: khách sạn
DLG_KEYS = ["dlg_name"] + [f"dlg_{k}" for k in LINK_OTAS]


def prefill(h=None):
    st.session_state["dlg_id"] = h["id"] if h else None
    st.session_state["dlg_name"] = h["name"] if h else ""
    for k in LINK_OTAS:
        st.session_state[f"dlg_{k}"] = (h or {}).get(f"{k}_url") or ""
    st.session_state["dlg_paste"] = ""
    st.session_state.pop("dlg_msg", None)


def on_paste():
    url = st.session_state["dlg_paste"].strip()
    if not url:
        return
    ota = detect_ota(url)
    if not ota:
        st.session_state["dlg_msg"] = ("error", "Không nhận ra link. Hỗ trợ Agoda, Booking.com, Trip.com, Google Hotels.")
    else:
        st.session_state[f"dlg_{ota}"] = url
        if not st.session_state["dlg_name"]:
            st.session_state["dlg_name"] = guess_name(url)
        st.session_state["dlg_msg"] = ("success", f"Đã nhận link **{LINK_OTAS[ota]}**.")
    st.session_state["dlg_paste"] = ""


@st.dialog("Khách sạn đối thủ", width="large")
def hotel_dialog():
    st.text_input("Dán link bất kỳ — tool tự nhận OTA", key="dlg_paste", on_change=on_paste,
                  placeholder="Dán link Agoda, Booking.com, Trip.com hoặc Google Hotels rồi nhấn Enter")
    if msg := st.session_state.get("dlg_msg"):
        getattr(st, msg[0])(msg[1])
    st.text_input("Tên khách sạn", key="dlg_name")
    c1, c2 = st.columns(2)
    c1.text_input(":red-badge[Agoda]", key="dlg_agoda", placeholder="https://www.agoda.com/…/hotel/….html")
    c2.text_input(":blue-badge[Booking.com]", key="dlg_booking", placeholder="https://www.booking.com/hotel/vn/….html")
    c1.text_input(":orange-badge[Trip.com]", key="dlg_trip", placeholder="https://www.trip.com/hotels/detail/?hotelId=…")
    c2.text_input(":green-badge[Google Hotels] · tham khảo, không bắt buộc", key="dlg_google",
                  placeholder="Để trống: tool tự tìm theo tên khách sạn")
    st.caption("Chỉ cần ít nhất 1 link. Google Hotels là nguồn **tham khảo**: giá hiện ở cột riêng, "
               "không thay cho giá lấy trực tiếp từ OTA.")
    if st.button("Lưu", type="primary", icon=":material/save:"):
        name = st.session_state["dlg_name"].strip()
        urls = {k: st.session_state[f"dlg_{k}"].strip() for k in LINK_OTAS}
        wrong = [LINK_OTAS[k] for k, u in urls.items() if u and detect_ota(u) != k]
        if not any(urls.values()):
            st.error("Cần ít nhất 1 link.")
        elif wrong:
            st.error("Link không đúng ô: " + ", ".join(wrong))
        else:
            db.save_hotel(st.session_state["dlg_id"], name or guess_name(next(u for u in urls.values() if u)), urls,
                          name_auto=not name)
            st.rerun()


# ================================================================== Sidebar
hotels = db.list_hotels()
with st.sidebar:
    n_on = sum(1 for h in hotels if h.get("enabled", 1))
    c1, c2 = st.columns([3, 2], vertical_alignment="center")
    c1.header("Đối thủ")
    if c2.button("Thêm", icon=":material/add:", width="stretch", type="primary" if not hotels else "secondary",
                 help="Thêm khách sạn đối thủ"):
        prefill()
        hotel_dialog()
    st.caption(f"{n_on}/{len(hotels)} khách sạn đang bật" if hotels else "Chưa có khách sạn nào. Bấm **Thêm** để bắt đầu.")

    def on_hotel_toggle(hid):
        db.set_hotel_enabled(hid, st.session_state[f"on{hid}"])

    def sync_sources(hid, offered):
        """Lưu các nguồn đang tắt của 1 khách sạn: OTA (pills) + Google tham khảo (checkbox)."""
        off = set(offered) - set(st.session_state.get(f"otas{hid}") or [])
        if not st.session_state.get(f"gref{hid}", True):
            off.add("google")
        db.set_otas_off(hid, off)

    st.html("<style>" + "".join(ota_pill_css(h["id"], [k for k in DIRECT_OTAS if h.get(f"{k}_url")])
                                for h in hotels) + "</style>")
    for h in hotels:
        hid, enabled, off = h["id"], bool(h.get("enabled", 1)), db.otas_off(h)
        offered = [k for k in DIRECT_OTAS if h.get(f"{k}_url")]
        with st.container(border=True, key=f"hcard-{'on' if enabled else 'off'}-{hid}"):
            c1, c2, c3 = st.columns([6, 2, 2], vertical_alignment="center", gap="small")
            c1.markdown(f"**{h['name']}**")
            with c2.popover("", icon=":material/more_horiz:", type="tertiary", help="Sửa / xóa"):
                if st.button("Sửa tên và link", key=f"edit{hid}", icon=":material/edit:", width="stretch"):
                    prefill(h)
                    hotel_dialog()
                if st.button("Xóa khách sạn", key=f"del{hid}", icon=":material/delete:", width="stretch",
                             help="Xóa khách sạn này khỏi danh sách đối thủ. Giá đã lấy vẫn giữ trong các lượt cũ."):
                    db.delete_hotel(hid)
                    st.rerun()
            c3.toggle("Bật", value=enabled, key=f"on{hid}", on_change=on_hotel_toggle, args=(hid,),
                      label_visibility="collapsed", help="Bật/tắt lấy giá khách sạn này")
            if not enabled:
                st.caption("Đang tắt, không lấy giá")
                continue
            if offered:
                st.pills("OTA", offered, selection_mode="multi", key=f"otas{hid}",
                         default=[k for k in offered if k not in off], label_visibility="collapsed",
                         format_func=LINK_OTAS.get,
                         on_change=sync_sources, args=(hid, offered),
                         help="Bấm để bật/tắt lấy giá trực tiếp từng OTA.")
            missing = [LINK_OTAS[k] for k in DIRECT_OTAS if not h.get(f"{k}_url")]
            if missing:
                st.caption("Chưa có link " + ", ".join(missing))
            st.checkbox(GOOGLE_COL, value="google" not in off, key=f"gref{hid}", on_change=sync_sources,
                        args=(hid, offered),
                        help="Lấy thêm giá Google Hotels làm tham khảo: mỗi ngày mở thêm 1 trang, giá gồm thuế & phí, "
                             "mặc định 2 khách, hiện ở cột riêng và không thay giá OTA. "
                             + ("Đã có link Google Hotels." if h.get("google_url")
                                else "Chưa có link: tool tự tìm theo tên khách sạn."))

    st.header("Lấy giá")
    today = date.today()
    if "d_from" not in st.session_state:
        st.session_state["d_from"] = today + timedelta(days=1)
        st.session_state["d_to"] = today + timedelta(days=int(s.get("span_days", 7)))

    def on_quick():
        n = st.session_state.get("quick_span")
        if n:
            st.session_state["d_to"] = st.session_state["d_from"] + timedelta(days=n - 1)
        st.session_state["quick_span"] = None

    c1, c2 = st.columns(2)
    d_from = c1.date_input("Nhận phòng từ", key="d_from", min_value=today, format="DD/MM/YYYY")
    d_to = c2.date_input("đến", key="d_to", min_value=today, format="DD/MM/YYYY")
    st.pills("Chọn nhanh", [7, 14, 30, 60, 90], key="quick_span", on_change=on_quick,
             format_func=lambda n: f"{n} ngày", label_visibility="collapsed")
    if d_to < d_from:
        st.error("Ngày kết thúc phải sau ngày bắt đầu.")
    c1, c2 = st.columns(2)
    nights = c1.number_input("Số đêm", 1, 14, int(s["nights"]))
    step = c2.number_input("Cách nhau (ngày)", 1, 30, int(s.get("step", 1)),
                           help="1 = lấy mọi ngày; 7 = mỗi tuần 1 ngày (cùng thứ).")
    c1, c2, c3 = st.columns(3)
    adults = c1.number_input("Người lớn", 1, 10, int(s["adults"]))
    children = c2.number_input("Trẻ em", 0, 6, int(s.get("children", 0)), help="Tính là trẻ 8 tuổi.")
    rooms = c3.number_input("Phòng", 1, 5, int(s["rooms"]))
    with st.expander("Tùy chọn khác"):
        currency = st.selectbox("Tiền tệ", CURRENCIES, index=CURRENCIES.index(s.get("currency", "VND")),
                                help="Agoda luôn trả theo tiền tệ khu vực (VND khi ở Việt Nam).")
        delay = st.slider("Nghỉ giữa 2 trang (giây)", 1, 60, (int(s["delay_min"]), int(s["delay_max"])),
                          help="Nghỉ ngẫu nhiên trong khoảng này, giúp tránh bị chặn.")
        headless = st.checkbox("Chạy ẩn trình duyệt", value=bool(s["headless"]))
        auto = st.toggle("Tự lấy giá hằng ngày (khi tool đang mở)", value=bool(s["auto_run"]))
        h_, m_ = (int(x) for x in s["auto_run_time"].split(":"))
        at = st.time_input("Giờ chạy", value=dtime(h_, m_), step=timedelta(minutes=15))
        if auto != s["auto_run"] or at.strftime("%H:%M") != s["auto_run_time"]:
            db.save_settings({"auto_run": auto, "auto_run_time": at.strftime("%H:%M")})

    pages = 0
    if d_to >= d_from:
        n_dates = len(list(date_list(d_from, d_to, int(step))))
        pages = estimate_pages(hotels, n_dates)
        mins = max(1, round(pages * (sum(delay) / 2 + 8) / 60))
        st.caption(f"{n_dates} ngày · khoảng {pages} trang · ~{mins} phút" if pages else "Thêm khách sạn đối thủ trước.")
    c1, c2 = st.columns([3, 2])
    if c1.button("Lấy giá", type="primary", width="stretch", icon=":material/play_arrow:",
                 disabled=STATE.running or not pages):
        cfg = dict(start=d_from, end=d_to, step=int(step), nights=int(nights), adults=int(adults),
                   children=int(children), rooms=int(rooms), currency=currency, delay_min=delay[0],
                   delay_max=delay[1], headless=headless)
        db.save_settings({"span_days": (d_to - d_from).days + 1,
                          **{k: v for k, v in cfg.items() if k not in ("start", "end")}})
        STATE.start(cfg)
        st.session_state["watching"] = True
        st.rerun()
    if c2.button("Dừng", width="stretch", icon=":material/stop:", disabled=not STATE.running):
        STATE.stop.set()

    st.divider()
    st.caption(f"v{__version__}")


# ================================================================== Main
st.title("Theo dõi giá phòng đối thủ")


@st.fragment(run_every="1s")
def status_panel():
    if STATE.running:
        frac = STATE.done / STATE.total if STATE.total else 0
        st.progress(frac, text=f"Đang lấy giá… {STATE.done}/{STATE.total or '…'} trang")
        if STATE.lines:
            st.caption(STATE.lines[-1])
    elif st.session_state.get("watching"):
        st.session_state["watching"] = False
        st.rerun()
    elif STATE.lines:
        st.success(STATE.lines[-1].split("  ", 1)[-1], icon=":material/check_circle:")
    if STATE.lines:
        with st.expander("Nhật ký lấy giá"):
            st.code("\n".join(reversed(STATE.lines)), language=None, wrap_lines=True)


status_panel()

runs = [r for r in db.list_runs(100) if r["n"] or r["status"] != "running"]
if not hotels:
    st.info("**Bắt đầu:** bấm **Thêm** ở mục Đối thủ bên trái, dán link Agoda / Booking.com / Trip.com / "
            "Google Hotels của khách sạn đối thủ. Sau đó chọn ngày và bấm **Lấy giá**.", icon=":material/info:")
    st.stop()
if not runs:
    st.info("Chưa có dữ liệu giá. Chọn ngày ở thanh bên trái rồi bấm **Lấy giá**.", icon=":material/info:")
    st.stop()

# ---------- dữ liệu của lượt đã chọn
c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
run = c1.selectbox("Lượt lấy giá", runs, format_func=lambda r: (
    f"{r['started_at'][8:10]}/{r['started_at'][5:7]} {r['started_at'][11:16]} · {r['n']} giá"
    + (" · mới nhất" if r["id"] == runs[0]["id"] else "")))
df = pd.DataFrame(db.rates_for_run(run["id"]), columns=["hotel_id", "hotel", "source", "ota", "ota_label", "via",
                                                        "checkin", "checkout", "adults", "room_name", "offer_name",
                                                        "price", "price_incl", "currency", "price_note", "breakfast",
                                                        "free_cancel", "cancel_text"])
fetch = pd.DataFrame(db.fetches_for_run(run["id"]))
df["via"] = df["via"].fillna(df["source"].map(lambda x: "google" if x == "google" else "direct"))
df["ota"] = df["ota"].fillna(df["source"])
df["ota_label"] = df["ota_label"].fillna(df["ota"].map(OTA_LABELS)).fillna(df["ota"])
df["hotel"] = df["hotel"].fillna("(đã xóa)")
df.loc[df["via"] == "google", "price_incl"] = df["price_incl"].fillna(df["price"])  # Google luôn gồm thuế
df = df[df["price"].notna()]
df["price_excl"] = df["price"].where(df["via"] != "google")   # Google chỉ có giá đã gồm thuế
df["price"] = df["price_incl"].fillna(df["price"])               # giá chính = sau thuế (khách trả khi đặt)
direct, gdf = df[df["via"] != "google"], df[df["via"] == "google"]   # Google = tham khảo, không trộn vào giá OTA
if len(df):
    c2.caption(f"Nhận phòng {day_label(df['checkin'].min())} → {day_label(df['checkin'].max())} · "
               f"{int(df['adults'].max())} người lớn · {df['hotel'].nunique()} khách sạn")

# ---------- bộ lọc
ota_order = [k for k in MAIN_OTAS if k in set(direct["ota"])] + sorted(set(direct["ota"]) - set(MAIN_OTAS))
ota_name = dict(zip(direct["ota"], direct["ota_label"]))
c1, c2, c3 = st.columns([3, 5, 2], vertical_alignment="bottom")
all_hotels = sorted(set(df["hotel"]) | set(fetch["hotel"].dropna() if len(fetch) else []))
sel_hotels = c1.multiselect("Khách sạn", all_hotels, default=all_hotels)
sel_otas = c2.pills("OTA", ota_order, selection_mode="multi", format_func=lambda k: ota_name.get(k, k),
                    default=ota_order) if ota_order else []
only_fc = c3.toggle("Hủy miễn phí")
only_bf = c3.toggle("Có bữa sáng")
f = direct[direct["hotel"].isin(sel_hotels) & direct["ota"].isin(sel_otas or [])]
gf = gdf[gdf["hotel"].isin(sel_hotels)]
if only_fc:
    f, gf = f[f["free_cancel"] == 1], gf[gf["free_cancel"] == 1]
if only_bf:
    f, gf = f[f["breakfast"] == 1], gf[gf["breakfast"] == 1]

# ---------- nguồn dữ liệu: mỗi khách sạn × nguồn lấy được gì
BAD = {"soldout": "🈳 Hết phòng", "blocked": "⛔ Bị chặn", "error": "⚠️ Lỗi", "notfound": "🔍 Cần dán link"}


def src_status(g):
    """Tóm tắt các lần mở trang của 1 khách sạn × 1 nguồn trong lượt."""
    if g.empty:
        return "—"
    per_date = g.groupby("checkin")["status"].agg(set)
    n_ok, total = sum("ok" in x for x in per_date), len(per_date)
    if n_ok == total:
        return "✅ Có giá"
    bad = pd.Series([c for x in per_date if "ok" not in x for c in x if c in BAD]).mode()
    worst = BAD[bad.iat[0]] if len(bad) else "—"
    return f"✅ {n_ok}/{total} ngày · còn lại {worst}" if n_ok else worst


if len(fetch):
    rows = []
    for hid, g in fetch.groupby("hotel_id"):
        hname = g["hotel"].iat[0] or "(đã xóa)"
        if hname in sel_hotels:
            rows.append({"Khách sạn": hname,
                         **{LINK_OTAS[k]: src_status(g[g["source"] == k]) for k in DIRECT_OTAS},
                         GOOGLE_COL: src_status(g[g["source"] == "google"])})
    with st.expander("Nguồn dữ liệu của lượt này", expanded=not all(
            v in ("✅ Có giá", "—") for r in rows for k, v in r.items() if k != "Khách sạn"), icon=":material/hub:"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown('<div class="hp-legend">✅ lấy được giá · 🈳 hết phòng / không có giá · ⛔ trang chặn trình duyệt tự '
                    'động (tool không cố vượt qua) · 🔍 không tự tìm được đúng khách sạn trên Google: mở ⋯ ở thẻ khách '
                    'sạn → Sửa tên và link để dán link Google Hotels · — không có link hoặc đang tắt. <b>Google (tham khảo)</b> là nguồn '
                    'riêng, không thay cho OTA bị chặn.</div>', unsafe_allow_html=True)

if f.empty and gf.empty:
    st.info("Lượt này không có giá nào." if df.empty else "Không có giá nào khớp bộ lọc.", icon=":material/info:")
    st.stop()

# ---------- giá đại diện cho mỗi (ngày, KS, OTA) — chỉ từ giá lấy trực tiếp
INFO_COLS = ["price", "price_excl", "room_name", "offer_name", "breakfast", "free_cancel", "cancel_text", "price_note"]
pick = (f.loc[f.groupby(["checkin", "hotel", "ota"])["price"].idxmin()] if len(f) else f)[
    ["checkin", "hotel", "ota"] + INFO_COLS].reset_index(drop=True)
pick["OTA"] = pick["ota"].map(lambda k: ota_name.get(k, k))
# Google (tham khảo): giá thấp nhất Google hiển thị cho mỗi (ngày, KS) và nhà cung cấp bán giá đó
gbest = (gf.loc[gf.groupby(["checkin", "hotel"])["price"].idxmin()] if len(gf) else gf)[
    ["checkin", "hotel", "price", "ota_label"]].reset_index(drop=True)
has_google = len(gbest) > 0
cur = (f if len(f) else gf)["currency"].mode().iat[0]

# ---------- chỉ số
if pick.empty:
    st.info("Không có giá lấy trực tiếp từ OTA nào khớp bộ lọc — bên dưới chỉ có giá **tham khảo** từ Google Hotels.",
            icon=":material/info:")
else:
    best_row = pick.loc[pick["price"].idxmin()]
    cheapest_ota = pick.loc[pick.groupby(["checkin", "hotel"])["price"].idxmin(), "OTA"].value_counts()
    soldout = int(((fetch["status"] == "soldout") & (fetch["source"] != "google")).sum()) if len(fetch) else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Số ngày có giá", f["checkin"].nunique())
    m2.metric(f"Giá/đêm thấp nhất, sau thuế ({cur})", money(best_row["price"]),
              help=f"{best_row['hotel']} · {best_row['OTA']} · {day_label(best_row['checkin'])}")
    m3.metric("OTA thường rẻ nhất", cheapest_ota.index[0] if len(cheapest_ota) else "—",
              help="OTA có giá thấp nhất nhiều ngày nhất (tính theo từng khách sạn). Không tính Google (tham khảo).")
    m4.metric("Lần hết phòng / không có giá", soldout)


BEST_CSS = "background-color: rgba(34,197,94,.20); font-weight: 600"
REF_CSS = "background-color: rgba(66,133,244,.10); font-style: italic"   # cột Google (tham khảo)


def styled_min(values: pd.DataFrame, text: pd.DataFrame):
    """Hiển thị bảng chữ `text`; tô xanh ô có giá thấp nhất mỗi hàng theo `values` (cột thừa trong text để trống)."""
    css = pd.DataFrame("", index=text.index, columns=text.columns)
    for i, r in values.iterrows():
        if r.count() > 1:
            for c in r.index[r == r.min()]:
                css.at[i, c] = BEST_CSS
    if GOOGLE_COL in css.columns:
        css[GOOGLE_COL] = REF_CSS
    return text.style.apply(lambda _: css, axis=None)


def ota_table(hotel):
    """(giá sau thuế để tô màu, bảng chữ) — hàng: ngày; mỗi OTA 2 cột: sau thuế, trước thuế; cuối: Google tham khảo."""
    p, gb = pick[pick["hotel"] == hotel], gbest[gbest["hotel"] == hotel].set_index("checkin")
    days = sorted(set(p["checkin"]) | set(gb.index))
    after = p.pivot(index="checkin", columns="ota", values="price").reindex(days)
    before = p.pivot(index="checkin", columns="ota", values="price_excl").reindex(days)
    cols = [k for k in ota_order if k in after.columns]
    text, vals = pd.DataFrame(index=days), pd.DataFrame(index=days)
    for c in cols:
        name = ota_name.get(c, c)
        text[f"{name} · sau thuế"] = after[c].map(money)
        text[f"{name} · trước thuế"] = before[c].map(money)
        vals[f"{name} · sau thuế"] = after[c]
    low = after[cols].min(axis=1) if cols else pd.Series(float("nan"), index=days)
    if cols:
        text["Rẻ nhất"] = [ota_name.get(after.loc[i, cols].idxmin(), "—") if pd.notna(low[i]) else "—" for i in days]
    if has_google:
        text[GOOGLE_COL] = [
            f"{money(gb.at[i, 'price'])} · {gb.at[i, 'ota_label']}" + (" ▼" if gb.at[i, "price"] < low[i] else "")
            if i in gb.index else "—" for i in days]
    vals.index = text.index = [day_label(i) for i in days]
    text.index.name = "Nhận phòng"
    return vals, text


def pick_hotel(options, key):
    h = st.segmented_control("Khách sạn", options, default=options[0], key=key) if len(options) > 1 else None
    return h or options[0]


# ---------- tabs
tab_names = ["Giá theo OTA", "So sánh khách sạn", "Theo loại phòng"] + ([GOOGLE_COL] if has_google else []) + [
    "Biểu đồ", "Chi tiết"]
tabs = dict(zip(tab_names, st.tabs(tab_names)))
both_hotels = sorted(set(pick["hotel"]) | set(gbest["hotel"]))

with tabs["Giá theo OTA"]:
    vals, text = ota_table(pick_hotel(both_hotels, "ota_hotel"))
    st.dataframe(styled_min(vals, text), width="stretch")
    st.markdown(f'<div class="hp-legend">Giá/đêm thấp nhất ({cur}) lấy trực tiếp trên mỗi OTA. <b>Sau thuế</b> = giá '
                'khách trả khi đặt (gồm thuế &amp; phí) · <b>Trước thuế</b> = giá OTA hiển thị ở trang danh sách. Ô xanh '
                '= OTA rẻ nhất ngày đó (theo giá sau thuế).'
                + (f' Cột <b>{GOOGLE_COL}</b> = giá thấp nhất Google Hotels hiển thị và nhà cung cấp bán giá đó (gồm '
                   'thuế &amp; phí, mặc định 2 khách); chỉ để đối chiếu, không tính vào "Rẻ nhất". <b>▼</b> = Google '
                   'đang thấy giá thấp hơn mọi OTA lấy trực tiếp.' if has_google else '') + '</div>',
                unsafe_allow_html=True)

with tabs["So sánh khách sạn"]:
    if pick.empty:
        st.info("Chưa có giá lấy trực tiếp từ OTA để so sánh.")
    else:
        best = pick.loc[pick.groupby(["checkin", "hotel"])["price"].idxmin()]
        vals = best.pivot(index="checkin", columns="hotel", values="price")
        text = best.assign(t=best["price"].map(money) + " · " + best["OTA"]).pivot(
            index="checkin", columns="hotel", values="t")
        text = text.reindex_like(vals).fillna("—")
        vals.columns.name = text.columns.name = None
        vals.index = text.index = [day_label(i) for i in vals.index]
        text.index.name = "Nhận phòng"
        st.dataframe(styled_min(vals, text), width="stretch")
        st.markdown('<div class="hp-legend">Giá thấp nhất của mỗi khách sạn trong ngày (trên các OTA đang chọn, lấy trực '
                    'tiếp) và OTA bán giá đó. Ô xanh = khách sạn rẻ nhất ngày đó.'
                    + (f' Không tính giá Google — xem tab <b>{GOOGLE_COL}</b>.' if has_google else '') + '</div>',
                    unsafe_allow_html=True)

with tabs["Theo loại phòng"]:
    rooms_df = f[f["ota"].isin(["agoda", "booking"])]
    if rooms_df.empty:
        st.info("Chưa có giá theo loại phòng. Giá từng loại phòng chỉ có khi lấy trực tiếp từ Agoda (hoặc Booking.com "
                "khi không bị chặn).")
    else:
        c1, c2 = st.columns(2)
        rh = c1.selectbox("Khách sạn", sorted(rooms_df["hotel"].unique()), key="room_hotel")
        ro = c2.selectbox("OTA", sorted(rooms_df[rooms_df["hotel"] == rh]["ota"].unique()), format_func=OTA_LABELS.get)
        r = rooms_df[(rooms_df["hotel"] == rh) & (rooms_df["ota"] == ro)]
        vals = r.groupby(["checkin", "room_name"])["price"].min().unstack("room_name")
        vals.index = [day_label(i) for i in vals.index]
        vals.index.name = "Nhận phòng"
        st.dataframe(vals.style.format(money, na_rep="Hết phòng"), width="stretch")
        st.markdown(f'<div class="hp-legend">Giá/đêm thấp nhất ({cur}) của từng loại phòng trên {OTA_LABELS[ro]} '
                    '(lấy trực tiếp).</div>', unsafe_allow_html=True)

if has_google:
    with tabs[GOOGLE_COL]:
        gh = pick_hotel(sorted(gbest["hotel"].unique()), "google_hotel")
        g1 = gf[gf["hotel"] == gh]
        vals = g1.groupby(["checkin", "ota_label"])["price"].min().unstack("ota_label")
        main = [OTA_LABELS[k] for k in MAIN_OTAS if OTA_LABELS[k] in vals.columns]
        vals = vals[main + list(vals.drop(columns=main).count().sort_values(ascending=False).index)]
        vals.columns.name = None
        vals.index = [day_label(i) for i in vals.index]
        vals.index.name = "Nhận phòng"
        st.dataframe(styled_min(vals, vals.map(money)), width="stretch")
        st.markdown(f'<div class="hp-legend">Giá/đêm thấp nhất ({cur}) của từng nhà cung cấp theo Google Hotels: gồm thuế '
                    '&amp; phí, mặc định 2 khách, không có từng loại phòng. Ô xanh = nhà cung cấp rẻ nhất ngày đó. Đây là '
                    'giá Google hiển thị, có thể lệch so với giá trên chính trang OTA — chỉ dùng để tham khảo.</div>',
                    unsafe_allow_html=True)

with tabs["Biểu đồ"]:
    modes = ["Các khách sạn", "Các OTA của 1 khách sạn"]
    mode = st.segmented_control("Hiển thị", modes, default=modes[0] if len(pick) else modes[1], key="chart_mode")
    if mode == modes[1]:
        ch = st.selectbox("Khách sạn", both_hotels, key="chart_hotel")
        data = pick[pick["hotel"] == ch].pivot(index="checkin", columns="OTA", values="price")
        ref = gbest[gbest["hotel"] == ch].set_index("checkin")["price"].rename(GOOGLE_COL)
        if len(ref):
            data = data.join(ref, how="outer")
    else:
        data = pick.groupby(["checkin", "hotel"])["price"].min().unstack("hotel")
    data.index = [date.fromisoformat(i) for i in data.index]
    if data.empty:
        st.info("Chưa có giá lấy trực tiếp từ OTA để vẽ. Chọn “Các OTA của 1 khách sạn” để xem giá Google (tham khảo).")
    elif len(data) > 1:
        st.line_chart(data, height=380, y_label=f"Giá/đêm ({cur})", x_label="Nhận phòng")
    else:
        st.bar_chart(data.T, height=380, y_label=f"Giá/đêm ({cur})")

with tabs["Chi tiết"]:
    allf = pd.concat([f, gf])
    detail = allf.assign(
        Nguồn=allf["via"].map({"google": GOOGLE_COL, "direct": "Trực tiếp"}),
        breakfast=allf["breakfast"].fillna(0).astype(bool), free_cancel=allf["free_cancel"].fillna(0).astype(bool),
    )[["checkin", "hotel", "ota_label", "Nguồn", "room_name", "offer_name", "price_excl", "price_incl", "currency",
       "breakfast", "free_cancel", "price_note", "cancel_text"]].sort_values(["checkin", "hotel", "Nguồn", "price_incl"],
                                                                             ascending=[True, True, False, True])
    st.dataframe(detail, width="stretch", hide_index=True, height=460, column_config={
        "checkin": "Nhận phòng", "hotel": "Khách sạn", "ota_label": "OTA",
        "room_name": st.column_config.TextColumn("Loại phòng", width="medium"),
        "offer_name": "Gói",
        "price_excl": st.column_config.NumberColumn("Trước thuế", format="localized"),
        "price_incl": st.column_config.NumberColumn("Sau thuế (gồm thuế & phí)", format="localized"),
        "currency": "Tiền tệ", "breakfast": st.column_config.CheckboxColumn("Bữa sáng"),
        "free_cancel": st.column_config.CheckboxColumn("Hủy miễn phí"),
        "price_note": "Ghi chú", "cancel_text": "Chính sách hủy"})

# ---------- tải về
sheets = {"Giá theo OTA": pick[["checkin", "hotel", "OTA", "price", "price_excl"]].rename(columns={
    "checkin": "Nhận phòng", "hotel": "Khách sạn", "price": f"Giá/đêm sau thuế ({cur})",
    "price_excl": f"Giá/đêm trước thuế ({cur})"})}
if has_google:
    sheets[GOOGLE_COL] = gf.groupby(["checkin", "hotel", "ota_label"], as_index=False)["price"].min().rename(columns={
        "checkin": "Nhận phòng", "hotel": "Khách sạn", "ota_label": "Nhà cung cấp trên Google",
        "price": f"Giá/đêm sau thuế ({cur})"})
detail_x = detail.rename(columns={"checkin": "Nhận phòng", "hotel": "Khách sạn", "ota_label": "OTA",
                                  "room_name": "Loại phòng", "offer_name": "Gói", "price_excl": "Giá/đêm trước thuế",
                                  "price_incl": "Giá/đêm sau thuế",
                                  "currency": "Tiền tệ", "breakfast": "Bữa sáng", "free_cancel": "Hủy miễn phí",
                                  "price_note": "Ghi chú", "cancel_text": "Chính sách hủy"})
sheets["Chi tiết"] = detail_x
d1, d2 = st.columns(2)
d1.download_button("Tải Excel", to_excel(sheets), icon=":material/download:",
                   width="stretch", file_name=f"gia-doi-thu-{run['started_at'][:10]}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
csv = io.StringIO()
detail_x.to_csv(csv, index=False)
d2.download_button("Tải CSV", csv.getvalue().encode("utf-8-sig"), icon=":material/download:", width="stretch",
                   file_name=f"gia-doi-thu-{run['started_at'][:10]}.csv", mime="text/csv")
