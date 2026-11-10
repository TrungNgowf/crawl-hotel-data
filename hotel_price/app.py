"""Giao diện Streamlit. Chạy bằng `uv run hotel-price` (không chạy trực tiếp file này)."""
import io
from datetime import date, time as dtime, timedelta

import pandas as pd
import streamlit as st

from hotel_price import __version__, db
from hotel_price.config import DATA_DIR
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
BADGE = {"agoda": "red", "booking": "blue", "trip": "orange", "google": "green"}
MAIN_OTAS = ["agoda", "booking", "trip", "official"]
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
  [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {padding: 2px 0;}
  .hp-legend {font-size: .85rem; opacity: .75;}
</style>""")


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
    c2.text_input(":green-badge[Google Hotels] (không bắt buộc)", key="dlg_google",
                  placeholder="Để trống: tool tự tìm trên Google khi cần")
    st.caption("Chỉ cần ít nhất 1 link. OTA nào bị chặn hoặc lỗi, tool tự lấy giá OTA đó qua Google Hotels.")
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
    st.header("Đối thủ" + (f" ({n_on}/{len(hotels)} đang bật)" if hotels else ""))
    if not hotels:
        st.caption("Chưa có khách sạn nào.")

    def on_hotel_toggle(hid):
        db.set_hotel_enabled(hid, st.session_state[f"on{hid}"])

    def on_otas_change(hid, offered):
        chosen = set(st.session_state[f"otas{hid}"] or [])
        db.set_otas_off(hid, set(offered) - chosen)

    for h in hotels:
        enabled = bool(h.get("enabled", 1))
        with st.container(border=True):
            c1, c2, c3 = st.columns([6, 1, 1], vertical_alignment="center", gap="small")
            c1.toggle(f"**{h['name']}**" if enabled else f"~~{h['name']}~~", value=enabled, key=f"on{h['id']}",
                      on_change=on_hotel_toggle, args=(h["id"],), help="Bật/tắt lấy giá khách sạn này")
            if c2.button("", key=f"edit{h['id']}", icon=":material/edit:", type="tertiary", help="Sửa link"):
                prefill(h)
                hotel_dialog()
            with c3.popover("", icon=":material/delete:", type="tertiary", help="Xóa"):
                st.write(f"Xóa **{h['name']}**?")
                if st.button("Xóa", key=f"del{h['id']}", type="primary"):
                    db.delete_hotel(h["id"])
                    st.rerun()
            if not enabled:
                st.caption("Đang tắt — không lấy giá khách sạn này.")
                continue
            # OTA có link (Google luôn có thể dùng: tự tìm nếu chưa có link)
            offered = [k for k in LINK_OTAS if h.get(f"{k}_url") or k == "google"]
            off = db.otas_off(h)
            st.pills("OTA", offered, selection_mode="multi", key=f"otas{h['id']}",
                     default=[k for k in offered if k not in off], label_visibility="collapsed",
                     format_func=lambda k, h=h: "Google (tự tìm)" if k == "google" and not h.get("google_url")
                     else LINK_OTAS[k],
                     on_change=on_otas_change, args=(h["id"], offered),
                     help="Bấm để bật/tắt từng OTA. OTA tắt sẽ không được lấy giá (kể cả qua Google).")
            missing = [LINK_OTAS[k] for k in ("agoda", "booking", "trip") if not h.get(f"{k}_url")]
            if missing:
                st.caption("Chưa có link: " + ", ".join(missing))
    if st.button("Thêm khách sạn", icon=":material/add:", width="stretch"):
        prefill()
        hotel_dialog()

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
    google_fb = st.toggle("Tự lấy qua Google Hotels khi OTA bị chặn", value=bool(s.get("google_fallback", True)),
                          help="Booking.com thường chặn trình duyệt tự động; Trip.com chỉ có giá chung. Khi đó tool lấy "
                               "giá của chính OTA đó mà Google Hotels hiển thị (gồm thuế & phí, mặc định 2 khách).")
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
        pages = estimate_pages(hotels, n_dates, google_fb)
        mins = max(1, round(pages * (sum(delay) / 2 + 8) / 60))
        st.caption(f"{n_dates} ngày · khoảng {pages} trang · ~{mins} phút" if pages else "Thêm khách sạn đối thủ trước.")
    c1, c2 = st.columns([3, 2])
    if c1.button("Lấy giá", type="primary", width="stretch", icon=":material/play_arrow:",
                 disabled=STATE.running or not pages):
        cfg = dict(start=d_from, end=d_to, step=int(step), nights=int(nights), adults=int(adults),
                   children=int(children), rooms=int(rooms), currency=currency, delay_min=delay[0],
                   delay_max=delay[1], headless=headless, google_fallback=google_fb)
        db.save_settings({"span_days": (d_to - d_from).days + 1,
                          **{k: v for k, v in cfg.items() if k not in ("start", "end")}})
        STATE.start(cfg)
        st.session_state["watching"] = True
        st.rerun()
    if c2.button("Dừng", width="stretch", icon=":material/stop:", disabled=not STATE.running):
        STATE.stop.set()

    st.divider()
    st.caption(f"v{__version__} · Sáng/tối: menu ⋮ góc trên phải · Dữ liệu: `{DATA_DIR}`")


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
    st.info("**Bắt đầu:** bấm **Thêm khách sạn** ở thanh bên trái, dán link Agoda / Booking.com / Trip.com / "
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
if len(df):
    c2.caption(f"Nhận phòng {day_label(df['checkin'].min())} → {day_label(df['checkin'].max())} · "
               f"{int(df['adults'].max())} người lớn · {df['hotel'].nunique()} khách sạn")

# ---------- bộ lọc
ota_order = [k for k in MAIN_OTAS if k in set(df["ota"])] + sorted(set(df["ota"]) - set(MAIN_OTAS))
ota_name = dict(zip(df["ota"], df["ota_label"]))
c1, c2, c3 = st.columns([3, 5, 2], vertical_alignment="bottom")
all_hotels = sorted(set(df["hotel"]) | set(fetch["hotel"].dropna() if len(fetch) else []))
sel_hotels = c1.multiselect("Khách sạn", all_hotels, default=all_hotels)
sel_otas = c2.pills("OTA", ota_order, selection_mode="multi", format_func=lambda k: ota_name.get(k, k),
                    default=[k for k in ota_order if k in MAIN_OTAS] or ota_order)
only_fc = c3.toggle("Hủy miễn phí")
only_bf = c3.toggle("Có bữa sáng")
f = df[df["hotel"].isin(sel_hotels) & df["ota"].isin(sel_otas or [])]
if only_fc:
    f = f[f["free_cancel"] == 1]
if only_bf:
    f = f[f["breakfast"] == 1]

# ---------- nguồn dữ liệu (OTA nào lấy trực tiếp, OTA nào qua Google)
STATUS = [("google", "🔁 Qua Google"), ("ok", "✅ Trực tiếp"), ("soldout", "🈳 Hết phòng"),
          ("missing", "❔ Google không có"), ("nogoogle", "🔍 Cần link Google"), ("blocked", "⛔ Bị chặn"),
          ("error", "⚠️ Lỗi")]
if len(fetch):
    rows = []
    for hid, g in fetch.groupby("hotel_id"):
        hname = g["hotel"].iat[0] or "(đã xóa)"
        if hname not in sel_hotels:
            continue
        row = {"Khách sạn": hname}
        for k, label in LINK_OTAS.items():
            st_set = set(g[g["source"] == k]["status"])
            if k == "google":
                row[label] = "✅ Đã dùng" if "ok" in st_set else ("⛔ Bị chặn" if "blocked" in st_set else
                             ("🈳 Không có giá" if "soldout" in st_set else "—"))
            else:
                row[label] = next((txt for code, txt in STATUS if code in st_set), "—")
        rows.append(row)
    with st.expander("Nguồn dữ liệu của lượt này", expanded=True, icon=":material/hub:"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown('<div class="hp-legend">✅ lấy trực tiếp từ OTA · 🔁 OTA chặn/không có giá theo ngày nên lấy qua '
                    'Google Hotels · 🔍 tool không tự tìm được khách sạn trên Google: bấm ✏️ cạnh tên khách sạn để dán link Google Hotels · ⛔ bị chặn và không lấy thay được · — không có link</div>', unsafe_allow_html=True)

if f.empty:
    st.info("Lượt này không có giá nào." if df.empty else "Không có giá nào khớp bộ lọc.", icon=":material/info:")
    st.stop()

# ---------- giá đại diện cho mỗi (ngày, KS, OTA)
INFO_COLS = ["price", "price_excl", "room_name", "offer_name", "breakfast", "free_cancel", "cancel_text", "price_note"]


def _cheapest(rows):
    """Mỗi (ngày, KS, OTA): gói có giá sau thuế thấp nhất, kèm thông tin gói và số gói."""
    if rows.empty:
        return pd.DataFrame(columns=INFO_COLS + ["n_offers"])
    grp = rows.groupby(["checkin", "hotel", "ota"])
    out = rows.loc[grp["price"].idxmin()].set_index(["checkin", "hotel", "ota"])[INFO_COLS]
    out["n_offers"] = grp.size()
    return out


g, d = _cheapest(f[f["via"] == "google"]), _cheapest(f[f["via"] == "direct"])
pick = d.combine_first(g)   # ưu tiên giá lấy trực tiếp từ OTA, thiếu mới dùng Google
pick["via"] = ["direct" if k in d.index else "google" for k in pick.index]
pick = pick.reset_index()
pick["OTA"] = pick["ota"].map(lambda k: ota_name.get(k, k))
cur = f["currency"].mode().iat[0]

# ---------- chỉ số
best_row = pick.loc[pick["price"].idxmin()]
cheapest_ota = pick.loc[pick.groupby(["checkin", "hotel"])["price"].idxmin(), "OTA"].value_counts()
soldout = int((fetch["status"] == "soldout").sum()) if len(fetch) else 0
m1, m2, m3, m4 = st.columns(4)
m1.metric("Số ngày có giá", f["checkin"].nunique())
m2.metric(f"Giá/đêm thấp nhất, sau thuế ({cur})", money(best_row["price"]),
          help=f"{best_row['hotel']} · {best_row['OTA']} · {day_label(best_row['checkin'])}")
m3.metric("OTA thường rẻ nhất", cheapest_ota.index[0] if len(cheapest_ota) else "—",
          help="OTA có giá thấp nhất nhiều ngày nhất (tính theo từng khách sạn).")
m4.metric("Lần hết phòng / không có giá", soldout)


BEST_CSS = "background-color: rgba(34,197,94,.20); font-weight: 600"


def styled_min(values: pd.DataFrame, text: pd.DataFrame):
    """Hiển thị bảng chữ `text`; tô xanh ô có giá thấp nhất mỗi hàng theo `values` (cột thừa trong text để trống)."""
    css = pd.DataFrame("", index=text.index, columns=text.columns)
    for i, r in values.iterrows():
        if r.count() > 1:
            for c in r.index[r == r.min()]:
                css.at[i, c] = BEST_CSS
    return text.style.apply(lambda _: css, axis=None)


def ota_table(hotel):
    """(giá sau thuế để tô màu, bảng chữ) — hàng: ngày; mỗi OTA 2 cột: sau thuế, trước thuế."""
    p = pick[pick["hotel"] == hotel]
    after = p.pivot(index="checkin", columns="ota", values="price")
    before = p.pivot(index="checkin", columns="ota", values="price_excl")
    via = p.pivot(index="checkin", columns="ota", values="via")
    cols = [k for k in ota_order if k in after.columns]
    text, vals = pd.DataFrame(index=after.index), pd.DataFrame(index=after.index)
    for c in cols:
        name = ota_name.get(c, c)
        mark = lambda i: " ᴳ" if via.at[i, c] == "google" else ""  # noqa: E731
        text[f"{name} · sau thuế"] = [money(v) + mark(i) if pd.notna(v) else "—" for i, v in after[c].items()]
        text[f"{name} · trước thuế"] = [money(v) if pd.notna(v) else "—" for v in before[c]]
        vals[f"{name} · sau thuế"] = after[c]
    cheapest = after[cols].idxmin(axis=1)
    text["Rẻ nhất"] = [ota_name.get(k, k) if isinstance(k, str) else "—" for k in cheapest]
    vals.index = text.index = [day_label(i) for i in after.index]
    text.index.name = "Nhận phòng"
    return vals, text


# ---------- tabs
t1, t2, t3, t4, t5 = st.tabs(["Giá theo OTA", "So sánh khách sạn", "Theo loại phòng", "Biểu đồ", "Chi tiết"])

with t1:
    hs = [h for h in sorted(pick["hotel"].unique())]
    hotel = st.segmented_control("Khách sạn", hs, default=hs[0], key="ota_hotel") if len(hs) > 1 else hs[0]
    hotel = hotel or hs[0]
    vals, text = ota_table(hotel)
    st.dataframe(styled_min(vals, text), width="stretch")
    st.markdown(f'<div class="hp-legend">Giá/đêm thấp nhất ({cur}) trên mỗi OTA. <b>Sau thuế</b> = giá khách trả khi '
                'đặt (gồm thuế &amp; phí) · <b>Trước thuế</b> = giá OTA hiển thị ở trang danh sách. Ô xanh = OTA rẻ nhất '
                'ngày đó (theo giá sau thuế). <b>ᴳ</b> = lấy qua Google Hotels (Google chỉ có giá sau thuế, nên cột '
                'trước thuế để trống).</div>', unsafe_allow_html=True)

with t2:
    best = pick.loc[pick.groupby(["checkin", "hotel"])["price"].idxmin()]
    vals = best.pivot(index="checkin", columns="hotel", values="price")
    text = best.assign(t=best["price"].map(money) + " · " + best["OTA"]).pivot(index="checkin", columns="hotel", values="t")
    text = text.reindex_like(vals).fillna("—")
    vals.columns.name = text.columns.name = None
    vals.index = text.index = [day_label(i) for i in vals.index]
    text.index.name = "Nhận phòng"
    st.dataframe(styled_min(vals, text), width="stretch")
    st.markdown('<div class="hp-legend">Giá thấp nhất của mỗi khách sạn trong ngày (trên các OTA đang chọn) và OTA bán '
                'giá đó. Ô xanh = khách sạn rẻ nhất ngày đó.</div>', unsafe_allow_html=True)

with t3:
    rooms_df = f[(f["via"] == "direct") & (f["ota"].isin(["agoda", "booking"]))]
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

with t4:
    mode = st.segmented_control("Hiển thị", ["Các OTA của 1 khách sạn", "Các khách sạn"], default="Các khách sạn",
                                key="chart_mode")
    if mode == "Các OTA của 1 khách sạn":
        ch = st.selectbox("Khách sạn", sorted(pick["hotel"].unique()), key="chart_hotel")
        data = pick[pick["hotel"] == ch].pivot(index="checkin", columns="OTA", values="price")
    else:
        data = pick.groupby(["checkin", "hotel"])["price"].min().unstack("hotel")
    data.index = [date.fromisoformat(i) for i in data.index]
    if len(data) > 1:
        st.line_chart(data, height=380, y_label=f"Giá/đêm ({cur})", x_label="Nhận phòng")
    else:
        st.bar_chart(data.T, height=380, y_label=f"Giá/đêm ({cur})")

with t5:
    detail = f.assign(
        Nguồn=f["via"].map({"google": "Qua Google", "direct": "Trực tiếp"}),
        breakfast=f["breakfast"].fillna(0).astype(bool), free_cancel=f["free_cancel"].fillna(0).astype(bool),
    )[["checkin", "hotel", "ota_label", "Nguồn", "room_name", "offer_name", "price_excl", "price_incl", "currency",
       "breakfast", "free_cancel", "price_note", "cancel_text"]].sort_values(["checkin", "hotel", "price_excl"])
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
by_ota = pick.assign(Nguồn=pick["via"].map({"google": "Qua Google", "direct": "Trực tiếp"}))[
    ["checkin", "hotel", "OTA", "price", "price_excl", "Nguồn"]].rename(columns={
        "checkin": "Nhận phòng", "hotel": "Khách sạn", "price": f"Giá/đêm sau thuế ({cur})",
        "price_excl": f"Giá/đêm trước thuế ({cur})"})
detail_x = detail.rename(columns={"checkin": "Nhận phòng", "hotel": "Khách sạn", "ota_label": "OTA",
                                  "room_name": "Loại phòng", "offer_name": "Gói", "price_excl": "Giá/đêm trước thuế",
                                  "price_incl": "Giá/đêm sau thuế",
                                  "currency": "Tiền tệ", "breakfast": "Bữa sáng", "free_cancel": "Hủy miễn phí",
                                  "price_note": "Ghi chú", "cancel_text": "Chính sách hủy"})
d1, d2 = st.columns(2)
d1.download_button("Tải Excel", to_excel({"Giá theo OTA": by_ota, "Chi tiết": detail_x}), icon=":material/download:",
                   width="stretch", file_name=f"gia-doi-thu-{run['started_at'][:10]}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
csv = io.StringIO()
detail_x.to_csv(csv, index=False)
d2.download_button("Tải CSV", csv.getvalue().encode("utf-8-sig"), icon=":material/download:", width="stretch",
                   file_name=f"gia-doi-thu-{run['started_at'][:10]}.csv", mime="text/csv")
