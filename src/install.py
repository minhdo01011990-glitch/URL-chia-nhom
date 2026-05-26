"""CLI: url-labeler-install — cài đặt url-labeler vào Claude Desktop App và Claude Code."""

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


def _plugin_install_dir() -> pathlib.Path:
    return pathlib.Path.home() / ".local" / "share" / "url-labeler" / "plugin"


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


# ── Step 3: Plugin files (skills/agents) ────────────────────────────────────

def _get_plugin_source() -> pathlib.Path | None:
    """Trả về thư mục chứa skills/, agents/, .claude-plugin/ của plugin."""
    try:
        from src.plugin_dir import get_plugin_dir
        return get_plugin_dir()
    except Exception:
        return None


def _install_plugin_files() -> pathlib.Path | None:
    src_dir = _get_plugin_source()
    if src_dir is None:
        return None

    dst = _plugin_install_dir()
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)

    # Copy chỉ các thư mục/file liên quan đến plugin (không copy toàn bộ project root)
    copied = False
    for name in ("skills", "agents", ".claude-plugin"):
        src_sub = src_dir / name
        if src_sub.exists():
            shutil.copytree(src_sub, dst / name)
            copied = True
    for name in (".mcp.json",):
        src_file = src_dir / name
        if src_file.exists():
            shutil.copy2(src_file, dst / name)

    return dst if copied else None


# ── Step 4: Shell alias for slash commands ───────────────────────────────────

def _add_shell_alias(plugin_dir: pathlib.Path) -> tuple[str, pathlib.Path | None]:
    """Thêm shell function để claude tự load --plugin-dir. Trả về (line, rc_file|None)."""
    shell = pathlib.Path(os.environ.get("SHELL", "")).name
    if shell == "zsh":
        rc_file = pathlib.Path.home() / ".zshrc"
    elif shell == "bash":
        rc_file = pathlib.Path.home() / ".bashrc"
    else:
        return "", None

    # Dùng shell function thay alias để tránh infinite recursion
    func_line = (
        f'function claude() {{ command claude --plugin-dir "{plugin_dir}" "$@"; }}'
    )
    marker = "# url-labeler: slash commands"

    text = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
    if "url-labeler" in text and "--plugin-dir" in text:
        return func_line, None  # already configured

    with open(rc_file, "a", encoding="utf-8") as f:
        f.write(f"\n{marker}\n{func_line}\n")
    return func_line, rc_file


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    server_cmd = _server_command()

    print()
    print("Đang cài đặt url-labeler...")
    print()

    # 1. Claude Desktop App
    desktop_already, desktop_path = _install_desktop_app(server_cmd)
    verb = "cập nhật" if desktop_already else "thêm mới"
    print(f"✓ [1/4] Claude Desktop App: {verb}")
    print(f"        {desktop_path}")
    print()

    # 2. Claude Code global MCP
    cc_already, cc_path = _install_claude_code_mcp(server_cmd)
    verb = "cập nhật" if cc_already else "thêm mới"
    print(f"✓ [2/4] Claude Code / Cowork — MCP server: {verb}")
    print(f"        {cc_path}")
    print()

    # 3. Plugin files
    plugin_dir = _install_plugin_files()
    if plugin_dir:
        print(f"✓ [3/4] Plugin files (skills/agents):")
        print(f"        {plugin_dir}")
    else:
        print("  [3/4] Plugin files: bỏ qua (không tìm thấy nguồn)")
    print()

    # 4. Shell alias
    if plugin_dir:
        func_line, rc_file = _add_shell_alias(plugin_dir)
        if rc_file:
            print(f"✓ [4/4] Shell function đã thêm vào {rc_file}")
            print(f"        (cho phép dùng /url-labeler:start trong terminal mới)")
        elif func_line:
            print("✓ [4/4] Shell function: đã có sẵn")
        else:
            print(f"  [4/4] Shell function: thêm thủ công vào ~/.zshrc hoặc ~/.bashrc:")
            print(f'        function claude() {{ command claude --plugin-dir "{plugin_dir}" "$@"; }}')
    print()

    print("─" * 56)
    print()
    print("Bước tiếp theo:")
    print()
    print("  Claude Desktop App:")
    print("    • Tắt hoàn toàn (Cmd+Q trên Mac) rồi mở lại")
    print("    • Biểu tượng 🔧 trong chat = cài đặt thành công")
    print()
    print("  Claude Code / Terminal:")
    print("    • MCP tools: hoạt động ngay, không cần làm gì thêm")
    print("    • Slash commands (/url-labeler:start): mở terminal mới")
    print("      hoặc chạy:  source ~/.zshrc")
    print()
    print('  Bắt đầu: "Đánh nhãn file URL này cho tôi: /đường/dẫn/file.csv"')
    print()

    sys.exit(0)


if __name__ == "__main__":
    main()
