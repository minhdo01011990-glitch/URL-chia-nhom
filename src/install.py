"""CLI: url-labeler-install — tự động thêm url-labeler vào claude_desktop_config.json."""

from __future__ import annotations

import json
import pathlib
import platform
import shutil
import sys


def _config_path() -> pathlib.Path:
    system = platform.system()
    if system == "Darwin":
        return pathlib.Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        import os
        return pathlib.Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    # Linux (Claude Desktop chưa hỗ trợ chính thức, nhưng để sẵn)
    return pathlib.Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _server_command() -> str:
    # Ưu tiên full path nếu tìm thấy, tránh lỗi PATH khi Claude Desktop App khởi động
    cmd = shutil.which("url-labeler-server")
    if cmd:
        return cmd
    return "url-labeler-server"


def main() -> None:
    config_path = _config_path()
    server_cmd = _server_command()

    # Đọc config hiện tại (hoặc tạo mới nếu chưa có)
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"⚠  File cấu hình bị lỗi JSON: {config_path}")
            print("   Tạo backup rồi tạo mới...")
            backup = config_path.with_suffix(".json.bak")
            config_path.rename(backup)
            print(f"   Backup: {backup}")
            config = {}
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {}

    # Thêm / cập nhật server entry
    mcp_servers = config.setdefault("mcpServers", {})
    already_installed = "url-labeler" in mcp_servers

    mcp_servers["url-labeler"] = {"command": server_cmd}
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    # Output
    print()
    if already_installed:
        print("✓ url-labeler đã được cập nhật trong Claude Desktop App.")
    else:
        print("✓ url-labeler đã được thêm vào Claude Desktop App.")
    print()
    print(f"  Server  : {server_cmd}")
    print(f"  Config  : {config_path}")
    print()
    print("Bước tiếp theo:")
    print("  1. Tắt hoàn toàn Claude Desktop App (Cmd+Q trên Mac)")
    print("  2. Mở lại Claude Desktop App")
    print("  3. Biểu tượng 🔧 xuất hiện trong chat = cài đặt thành công")
    print()
    print("Bắt đầu sử dụng:")
    print('  Gõ: "Đánh nhãn file URL này cho tôi: /đường/dẫn/file.csv"')
    print()

    sys.exit(0)


if __name__ == "__main__":
    main()
