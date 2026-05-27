#!/usr/bin/env bash
# install.sh — Cài đặt url-labeler MCP server
# Dùng: bash <(curl -sSL https://raw.githubusercontent.com/minhdo01011990-glitch/URL-chia-nhom/main/install.sh)
set -euo pipefail

BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; RESET="\033[0m"

# Tìm Python 3.9+ — thử theo thứ tự ưu tiên để tránh dùng system Python bị lỗi
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" &>/dev/null; then
        _major=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        _minor=$("$candidate" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
        if [[ "$_major" -eq 3 && "$_minor" -ge 9 ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo -e "${RED}❌ Không tìm thấy Python 3.9+. Cài đặt tại https://python.org/downloads/${RESET}"
    echo "   (python3 --version hiện tại: $(python3 --version 2>/dev/null || echo 'không tìm thấy'))"
    exit 1
fi
echo -e "${BOLD}Python:${RESET} $("$PYTHON" --version)"

echo -e "${BOLD}Cài đặt url-labeler từ PyPI...${RESET}"
"$PYTHON" -m pip install --quiet --upgrade url-labeler

echo -e "${BOLD}Đăng ký MCP server...${RESET}"
"$("$PYTHON" -c "import sysconfig; print(sysconfig.get_path('scripts'))")/url-labeler-install" 2>/dev/null \
    || "$("$PYTHON" -m site --user-base 2>/dev/null)/bin/url-labeler-install" 2>/dev/null \
    || url-labeler-install
