"""Module entrypoint for `python -m sharp`."""

from __future__ import annotations

from sharp.cli import main_cli


def main() -> None:
    """Run the SHARP CLI."""
    main_cli()


if __name__ == "__main__":
    main()
