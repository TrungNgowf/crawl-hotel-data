# Phát hành tool cho bạn bè (dành cho bạn)

Tool được phân phối qua **GitHub (miễn phí)**: bạn bè chạy 1 lệnh cài, sau đó tool tự cập nhật mỗi khi bạn đẩy bản mới.

## Lần đầu (khoảng 10 phút)

### 1–3. Repo GitHub
Repo: **https://github.com/TrungNgowf/crawl-hotel-data** — cần để **Public** (Settings → General → Danger Zone → Change visibility) thì lệnh cài mới tải được code.

### 4. Tự cài thử trên máy bạn
Chạy lệnh cài trong `HUONG_DAN.md` mục 2. Thấy biểu tượng **Hotel Price Tool** trên Desktop và mở được là OK.

### 5. Gửi cho bạn bè
Gửi file `HUONG_DAN.md` (hoặc link `https://github.com/TrungNgowf/crawl-hotel-data/blob/main/HUONG_DAN.md`) kèm tin nhắn mẫu bên dưới.

## Mỗi lần có bản mới
1. Sửa code, chạy thử: `uv run hotel-price`.
2. Tăng số trong file `VERSION` (vd `0.2.0` → `0.2.1`) — **bắt buộc**, tool dựa vào số này để biết có bản mới.
3. Đẩy lên:
   ```bash
   git add . && git commit -m "Bản 0.2.1: ..." && git push
   ```
4. Lần sau bạn bè mở tool sẽ tự cập nhật (GitHub có thể trễ vài phút).

## Tin nhắn mẫu gửi bạn bè

> Mình gửi tool theo dõi giá phòng đối thủ (Agoda, Booking, Trip.com, Google Hotels), chạy trên máy bạn, miễn phí.
>
> **Cài 1 lần:**
> - Mac: mở Terminal, dán lệnh rồi Enter:
>   `curl -LsSf https://raw.githubusercontent.com/TrungNgowf/crawl-hotel-data/main/installer/install.sh | sh`
> - Windows: mở PowerShell, dán lệnh rồi Enter:
>   `powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/TrungNgowf/crawl-hotel-data/main/installer/install.ps1 | iex"`
>
> Xong thì bấm đúp **Hotel Price Tool** trên Desktop. Hướng dẫn chi tiết: https://github.com/TrungNgowf/crawl-hotel-data/blob/main/HUONG_DAN.md
>
> Máy cần có Chrome / Edge / Brave. Lúc dùng đừng tắt cửa sổ đen nhé.

## Lưu ý
- Bản Windows chưa được chạy thử thực tế — nên nhờ 1 người dùng Windows cài thử trước khi gửi rộng.
- Mỗi người tự lấy giá bằng mạng nhà mình, nên ít bị chặn hơn so với chạy tập trung.
- Booking.com, Trip.com cấm thu thập dữ liệu tự động trong điều khoản sử dụng; tool chạy chậm, không vượt chặn, chỉ nên dùng cá nhân để tham khảo.
