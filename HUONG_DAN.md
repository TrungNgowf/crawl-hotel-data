# Hướng dẫn dùng Hotel Price Tool

Tool giúp theo dõi giá phòng của các khách sạn đối thủ trên **Agoda, Booking.com, Trip.com** (và qua **Google Hotels**), chạy ngay trên máy của bạn. Dữ liệu chỉ lưu trên máy bạn.

---

## 1. Chuẩn bị

- Máy **macOS** hoặc **Windows 10/11**, có Internet.
- Có sẵn trình duyệt **Google Chrome**, **Microsoft Edge** hoặc **Brave** (Windows luôn có Edge). Nếu không có, tool tự tải một trình duyệt riêng (~150MB) ở lần chạy đầu.

## 2. Cài đặt (chỉ làm 1 lần)

### macOS
1. Mở ứng dụng **Terminal** (bấm `⌘ + Space`, gõ `Terminal`, Enter).
2. Copy toàn bộ dòng dưới, dán vào Terminal, nhấn **Enter**:
   ```bash
   curl -LsSf https://raw.githubusercontent.com/TrungNgowf/crawl-hotel-data/main/installer/install.sh | sh
   ```
3. Đợi 1–3 phút đến khi thấy dòng **"Xong!"**. Có thể đóng Terminal.

### Windows
1. Bấm nút **Start**, gõ `PowerShell`, mở **Windows PowerShell** (không cần quyền Administrator).
2. Copy toàn bộ dòng dưới, dán vào (chuột phải để dán), nhấn **Enter**:
   ```powershell
   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/TrungNgowf/crawl-hotel-data/main/installer/install.ps1 | iex"
   ```
3. Đợi 1–3 phút đến khi thấy dòng **"Xong!"**.

Cài xong, trên **Desktop** có biểu tượng **Hotel Price Tool**.

## 3. Mở tool

- Bấm đúp **Hotel Price Tool** trên Desktop.
- Một cửa sổ đen (Terminal / PowerShell) hiện ra, vài giây sau trình duyệt tự mở trang tool (`http://127.0.0.1:8765`).
- **Đừng đóng cửa sổ đen** khi đang dùng — đóng nó là tắt tool.
- Mỗi lần mở, tool **tự cập nhật** bản mới nhất (nếu có).

## 4. Cách dùng

### Bước 1 — Thêm khách sạn đối thủ
1. Ở thanh bên trái, mục **Đối thủ**, bấm **Thêm khách sạn**.
2. Mở trang khách sạn đối thủ trên Agoda / Booking.com / Trip.com / Google Hotels, **copy link** trên thanh địa chỉ, dán vào ô *"Dán link bất kỳ"* rồi nhấn **Enter**. Tool tự nhận OTA và điền đúng ô. Dán lần lượt các link của **cùng một khách sạn**.
3. Bấm **Lưu**.

> Mẹo: Booking.com thường chặn công cụ tự động. Tool sẽ tự lấy giá Booking qua Google Hotels. Nếu bảng **Nguồn dữ liệu** báo **🔍 Cần link Google**, hãy mở khách sạn trên [google.com/travel/hotels](https://www.google.com/travel/hotels), copy link và dán thêm vào ô *Google Hotels* (bấm ✏️ cạnh tên khách sạn).

### Bước 2 — Bật/tắt
- **Công tắc** cạnh tên khách sạn: bật/tắt lấy giá khách sạn đó.
- **Các nút OTA** dưới tên (Agoda, Booking.com, …): bấm để bật/tắt từng OTA. Nút sáng = đang lấy, nút mờ = bỏ qua.

### Bước 3 — Lấy giá
1. Ở mục **Lấy giá**: chọn ngày nhận phòng (*từ … đến …*) hoặc bấm nhanh **7 / 14 / 30 ngày**.
2. Chọn số đêm, người lớn, trẻ em, số phòng.
3. Bấm **Lấy giá**. Thanh tiến độ hiện ở giữa màn hình; bấm **Dừng** nếu muốn ngừng.
   Mỗi trang mất khoảng 10–15 giây (tool cố ý chạy chậm để không bị chặn), ví dụ 3 khách sạn × 7 ngày ≈ 5–10 phút.

### Bước 4 — Xem kết quả
- **Nguồn dữ liệu**: mỗi khách sạn × OTA lấy được trực tiếp (✅), qua Google (🔁), cần link Google (🔍) hay bị chặn (⛔).
- **Giá theo OTA**: chọn khách sạn → bảng theo ngày, mỗi OTA có cột **sau thuế** (giá khách trả khi đặt) và **trước thuế** (giá OTA hiện ở trang danh sách). Ô **xanh** = OTA rẻ nhất ngày đó. Dấu **ᴳ** = giá lấy qua Google Hotels.
- **So sánh khách sạn**: giá rẻ nhất của từng khách sạn mỗi ngày, kèm OTA bán giá đó.
- **Theo loại phòng**: giá từng loại phòng (khi lấy trực tiếp từ Agoda).
- **Biểu đồ**, **Chi tiết** (mọi gói phòng); nút **Tải Excel / Tải CSV** ở cuối trang.
- Đổi giao diện **sáng / tối**: menu **⋮** góc trên bên phải.

### Tự lấy giá hằng ngày
Mở **Tùy chọn khác** ở thanh bên trái → bật **Tự lấy giá hằng ngày** và chọn giờ. Chỉ chạy khi tool đang mở.

## 5. Lưu ý về giá

- Giá là **giá công khai** (không đăng nhập), có thể khác giá bạn thấy khi đăng nhập tài khoản thành viên, dùng mã giảm giá hoặc xem trên app.
- Giá qua **Google Hotels** là giá thấp nhất mỗi OTA, đã gồm thuế & phí, mặc định 2 khách.
- Giá OTA thay đổi liên tục — nên so sánh các lần lấy cùng thời điểm.

## 6. Gặp lỗi?

| Hiện tượng | Cách xử lý |
|---|---|
| Bấm đúp shortcut không thấy gì (macOS) | Chuột phải biểu tượng → **Open** → **Open**. Hoặc mở Terminal, chạy `~/.hotel-price-tool/launcher.sh` |
| Trình duyệt không tự mở | Tự mở trình duyệt, vào địa chỉ `http://127.0.0.1:8765` |
| Trang báo không kết nối được | Cửa sổ đen đã bị đóng → bấm đúp shortcut lại |
| Một OTA báo ⛔ bị chặn | Bình thường với Booking.com; tool lấy qua Google. Có thể thử lại sau vài giờ, hoặc tăng **Nghỉ giữa 2 trang** trong *Tùy chọn khác* |
| Muốn cài lại từ đầu | Chạy lại lệnh cài ở mục 2 (dữ liệu cũ vẫn giữ) |

**Gỡ cài đặt:** xóa thư mục `.hotel-price-tool` trong thư mục người dùng (macOS: `~/.hotel-price-tool`, Windows: `C:\Users\<tên>\.hotel-price-tool`) và biểu tượng trên Desktop.
