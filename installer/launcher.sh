#!/bin/sh
# Mở Hotel Price Tool: tự cập nhật bản mới (nếu có) rồi chạy app.
set -u
ROOT="$HOME/.hotel-price-tool"
PORT="${HOTEL_PRICE_PORT:-8765}"
REPO="$(cat "$ROOT/repo.txt")"
BRANCH="$(cat "$ROOT/branch.txt" 2>/dev/null || echo main)"
RAW_BASE="$(cat "$ROOT/raw_base.txt" 2>/dev/null || echo "https://raw.githubusercontent.com/$REPO/$BRANCH")"
ARCHIVE_URL="$(cat "$ROOT/archive_url.txt" 2>/dev/null || echo "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH")"
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$ROOT/venv"   # giữ thư viện ngoài thư mục code -> cập nhật nhanh

open_url() { (command -v open >/dev/null && open "$1") || (command -v xdg-open >/dev/null && xdg-open "$1") || true; }

# Tool đang mở rồi -> chỉ mở lại giao diện, không cập nhật (tránh ghi đè code đang chạy).
if [ "${1:-}" != "--update-only" ] && curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/"; then
  echo "Tool đang chạy, mở giao diện..."
  open_url "http://127.0.0.1:$PORT"
  exit 0
fi

update() {
  local_v="$(cat "$ROOT/app/VERSION" 2>/dev/null || echo none)"
  remote_v="$(curl -fsSL --max-time 8 "$RAW_BASE/VERSION" 2>/dev/null | tr -d '[:space:]' || true)"
  if [ -z "$remote_v" ]; then
    if [ -d "$ROOT/app" ]; then echo "Không kiểm tra được bản mới (mất mạng?) — dùng bản hiện có."; return 0; fi
    echo "Lỗi: không tải được tool. Kiểm tra kết nối mạng rồi thử lại."; exit 1
  fi
  [ "$remote_v" = "$local_v" ] && return 0
  echo "==> Cập nhật $local_v -> $remote_v ..."
  tmp="$(mktemp -d)"
  if ! curl -fsSL "$ARCHIVE_URL" -o "$tmp/app.tgz" || ! tar -xzf "$tmp/app.tgz" -C "$tmp"; then
    echo "Tải bản mới thất bại — dùng bản hiện có."; rm -rf "$tmp"; [ -d "$ROOT/app" ] && return 0; exit 1
  fi
  src="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  rm -rf "$ROOT/app.old"
  [ -d "$ROOT/app" ] && mv "$ROOT/app" "$ROOT/app.old"
  mv "$src" "$ROOT/app"
  rm -rf "$ROOT/app.old" "$tmp"
  # cập nhật chính launcher cho lần sau (mv thay file mới, không ảnh hưởng lần chạy này)
  if [ -f "$ROOT/app/installer/launcher.sh" ]; then
    cp "$ROOT/app/installer/launcher.sh" "$ROOT/launcher.sh.new" && chmod +x "$ROOT/launcher.sh.new" && mv "$ROOT/launcher.sh.new" "$ROOT/launcher.sh"
  fi
  (cd "$ROOT/app" && uv sync --frozen --no-dev --quiet) || { echo "Lỗi cài thư viện."; exit 1; }
  echo "==> Đã cập nhật lên $remote_v"
}

update
[ "${1:-}" = "--update-only" ] && exit 0

cd "$ROOT/app" && exec uv run --frozen --no-dev hotel-price --port "$PORT"
