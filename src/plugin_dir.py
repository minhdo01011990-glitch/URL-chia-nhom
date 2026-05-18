"""CLI helper: in ra đường dẫn thư mục plugin để dùng với claude --plugin-dir."""

from __future__ import annotations

import pathlib


def get_plugin_dir() -> pathlib.Path:
    # Khi cài từ pip: src/url_labeler_plugin/ chứa skills/, agents/, .claude-plugin/
    pip_bundle = pathlib.Path(__file__).parent / "url_labeler_plugin"
    if pip_bundle.exists():
        return pip_bundle
    # Khi chạy từ source (git clone): thư mục gốc của project
    return pathlib.Path(__file__).parent.parent


def main() -> None:
    print(get_plugin_dir())


if __name__ == "__main__":
    main()
