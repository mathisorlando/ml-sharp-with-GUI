"""Launcher for the SHARP Studio GUI."""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

from sharp.gui import run


def _env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the SHARP Studio GUI.")
    output_env = os.environ.get("SHARP_GUI_OUTPUT_ROOT")
    output_default = Path(output_env) if output_env else None
    parser.add_argument(
        "--host",
        default=_env_or_default("SHARP_GUI_HOST", "127.0.0.1"),
        help="Host to bind the GUI server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_env_int("SHARP_GUI_PORT", 7860),
        help="Port to bind the GUI server.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=output_default,
        help="Path to store GUI outputs.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open the browser.",
    )
    args = parser.parse_args()

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}"
        timer = threading.Timer(1.0, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    run(host=args.host, port=args.port, output_root=args.output_path)


if __name__ == "__main__":
    main()
