# Hotel Price Tool

Tool chạy trên máy cá nhân để theo dõi giá phòng của khách sạn đối thủ trên Agoda, Booking.com và Trip.com.
Mỗi người tự cài và tự chạy trên máy mình. Dữ liệu lưu trên máy người dùng, không gửi đi đâu.

## Khả năng lấy giá của từng OTA (đã kiểm tra 11/2026)

| OTA | Lấy được gì | Ghi chú |
|---|---|---|
| **Agoda** | Giá **từng loại phòng, từng gói**: bữa sáng, hủy miễn phí, chính sách hủy | Giá VND mỗi đêm, **chưa gồm thuế và phí** |
| **Booking.com** | Từng loại phòng, nếu Booking cho xem | Booking hiện **bỏ ngày đặt phòng khỏi URL khi trình duyệt chạy tự động**, nên thường không có giá. Tool báo "đang chặn" và bỏ qua, không cố vượt qua |
| **Google Hotels** | Giá thấp nhất của **từng nhà cung cấp** Google hiển thị: Booking.com, Agoda, Trip.com, Expedia, trang chính thức... | **Cách có giá Booking.com.** Giá gồm thuế & phí, mặc định 2 khách. Nên dùng link trang khách sạn (`google.com/travel/hotels/entity/...`); link tìm theo tên có thể ra nhầm khách sạn |
| **Trip.com** | Chỉ giá "From" thấp nhất | Trip.com chặn API danh sách phòng với trình duyệt tự động. Giá "From" có thể **không đổi theo ngày** |

Tool không vượt CAPTCHA hay cơ chế chống bot. Gặp trang chặn thì tool dừng OTA đó trong lượt chạy và ghi lại trong log.

---

## Dành cho người dùng

Xem **[HUONG_DAN.md](HUONG_DAN.md)**: cài đặt (macOS / Windows), cách dùng, xử lý lỗi.

---

## Dành cho người phát hành (bạn)

Xem **[PHAT_HANH.md](PHAT_HANH.md)**: tạo repo GitHub, đẩy code, phát hành bản mới, tin nhắn mẫu gửi bạn bè.

### Chạy khi phát triển
```bash
uv run hotel-price            # mở giao diện tại http://127.0.0.1:8765
```
Đặt biến `HOTEL_PRICE_HOME=/thư/mục/khác` để dùng dữ liệu thử, tách khỏi dữ liệu thật.

### Cấu trúc
```
hotel_price/
  sites/agoda.py     # bắt JSON api/v1/property/room-grid
  sites/booking.py   # đọc bảng #hprt-table (nếu Booking hiện giá)
  sites/trip.py      # giá "From" trong HTML
  sites/google.py    # Google Hotels: giá từng nhà cung cấp (tự tạo tham số ngày `ts`)
  runner.py          # duyệt ngày × khách sạn × OTA, nghỉ ngẫu nhiên giữa các lần
  app.py             # giao diện Streamlit
  state.py           # trạng thái crawl chạy nền + lịch tự chạy hằng ngày
  db.py, export.py   # SQLite, xuất Excel
installer/           # install.sh / install.ps1 / launcher.sh / launcher.ps1
.streamlit/config.toml  # màu sắc chế độ sáng / tối
VERSION              # số phiên bản, dùng cho tự cập nhật
```
