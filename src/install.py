"""CLI: url-labeler-install — đăng ký MCP server vào Claude Desktop App và Claude Code."""

from __future__ import annotations

import json
import os
import pathlib
import platform
import shutil
import sys


# ── Config paths ────────────────────────────────────────────────────────────

def _desktop_config_path() -> pathlib.Path:
    system = platform.system()
    if system == "Darwin":
        return pathlib.Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        return pathlib.Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    return pathlib.Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _claude_code_settings_path() -> pathlib.Path:
    return pathlib.Path.home() / ".claude" / "settings.json"


def _server_command() -> str:
    cmd = shutil.which("url-labeler-server")
    return cmd if cmd else "url-labeler-server"


# ── JSON helpers ─────────────────────────────────────────────────────────────

def _read_json(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(".json.bak")
        path.rename(backup)
        print(f"   ⚠ File lỗi JSON — backup: {backup}")
        return {}


def _write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Step 1: Claude Desktop App ───────────────────────────────────────────────

def _install_desktop_app(server_cmd: str) -> tuple[bool, pathlib.Path]:
    path = _desktop_config_path()
    config = _read_json(path)
    mcp = config.setdefault("mcpServers", {})
    already = "url-labeler" in mcp
    mcp["url-labeler"] = {"command": server_cmd}
    _write_json(path, config)
    return already, path


# ── Step 2: Claude Code global MCP ──────────────────────────────────────────

def _install_claude_code_mcp(server_cmd: str) -> tuple[bool, pathlib.Path]:
    path = _claude_code_settings_path()
    config = _read_json(path)
    mcp = config.setdefault("mcpServers", {})
    already = "url-labeler" in mcp
    mcp["url-labeler"] = {"command": server_cmd}
    _write_json(path, config)
    return already, path


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    server_cmd = _server_command()

    print()
    print("Đang đăng ký MCP server url-labeler...")
    print()

    # 1. Claude Desktop App
    desktop_already, desktop_path = _install_desktop_app(server_cmd)
    verb = "cập nhật" if desktop_already else "thêm mới"
    print(f"✓ [1/2] Claude Desktop App: {verb}")
    print(f"        {desktop_path}")
    print()

    # 2. Claude Code global MCP
    cc_already, cc_path = _install_claude_code_mcp(server_cmd)
    verb = "cập nhật" if cc_already else "thêm mới"
    print(f"✓ [2/2] Claude Code — MCP server: {verb}")
    print(f"        {cc_path}")
    print()

    print("─" * 56)
    print()
    print("Bước tiếp theo:")
    print()
    print("  Claude Desktop App:")
    print("    • Tắt hoàn toàn (Cmd+Q trên Mac) rồi mở lại")
    print("    • Biểu tượng 🔧 trong chat = MCP đã hoạt động")
    print()
    print("  Claude Code:")
    print("    • MCP tools hoạt động ngay, không cần làm gì thêm")
    print()
    print("  Cài plugin (để dùng /url-labeler:URL):")
    print("    • Tải file: https://github.com/minhdo01011990-glitch/URL-chia-nhom/releases")
    print("    • Vào Claude → Settings → Plugins → Upload file")
    print()

    sys.exit(0)


if __name__ == "__main__":
    main()
