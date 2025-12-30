"""Contains `sharp gui` CLI implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from sharp.utils import logging as logging_utils


@click.command()
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="Host to bind the GUI server.",
)
@click.option(
    "--port",
    type=int,
    default=7860,
    show_default=True,
    help="Port to bind the GUI server.",
)
@click.option(
    "--output-path",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Path to store GUI outputs.",
)
@click.option("-v", "--verbose", is_flag=True, help="Activate debug logs.")
def gui_cli(host: str, port: int, output_path: Path | None, verbose: bool) -> None:
    """Launch the SHARP Studio GUI."""
    logging_utils.configure(logging.DEBUG if verbose else logging.INFO)

    from sharp.gui import run

    run(host=host, port=port, output_root=output_path)
