#!/bin/sh
# Cài Hotel Price Tool trên macOS / Linux.
#   curl -LsSf https://raw.githubusercontent.com/<user>/<repo>/main/installer/install.sh | sh
set -eu

# >>> Sửa dòng này thành <tên-github>/<tên-repo> của bạn trước khi đẩy lên GitHub <<<
REPO="${HOTEL_PRICE_REPO:-TrungNgowf/crawl-hotel-data}"
BRANCH="${HOTEL_PRICE_BRANCH:-main}"
RAW_BASE="${HOTEL_PRICE_RAW_BASE:-https://raw.githubusercontent.com/$REPO/$BRANCH}"

ROOT="$HOME/.hotel-price-tool"
echo "==> Cài Hotel Price Tool vào $ROOT"
mkdir -p "$ROOT"
echo "$REPO" > "$ROOT/repo.txt"
echo "$BRANCH" > "$ROOT/branch.txt"
[ -n "${HOTEL_PRICE_RAW_BASE:-}" ] && echo "$HOTEL_PRICE_RAW_BASE" > "$ROOT/raw_base.txt"
[ -n "${HOTEL_PRICE_ARCHIVE_URL:-}" ] && echo "$HOTEL_PRICE_ARCHIVE_URL" > "$ROOT/archive_url.txt"

# 1. uv (quản lý Python + thư viện, tự tải Python nếu máy chưa có)
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "==> Cài uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# 2. Launcher + tải code lần đầu + cài thư viện
curl -fsSL "$RAW_BASE/installer/launcher.sh" -o "$ROOT/launcher.sh"
chmod +x "$ROOT/launcher.sh"
"$ROOT/launcher.sh" --update-only

# 3. Shortcut trên Desktop
SHORTCUT="$HOME/Desktop/Hotel Price Tool.command"
if [ -d "$HOME/Desktop" ]; then
  printf '#!/bin/sh\nexec "%s"\n' "$ROOT/launcher.sh" > "$SHORTCUT"
  chmod +x "$SHORTCUT"
  echo "==> Đã tạo shortcut: $SHORTCUT"
fi

echo ""
echo "Xong! Bấm đúp 'Hotel Price Tool' trên Desktop để mở tool."
echo "(Hoặc chạy lệnh: $ROOT/launcher.sh)"
