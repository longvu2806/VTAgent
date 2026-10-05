"""Shared console, logging setup and per-stage timing."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console
from rich.logging import RichHandler

console = Console()
log = logging.getLogger("vtagent")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per Ollama request


@contextmanager
def timed(stage: str) -> Iterator[None]:
    """Log how long the enclosed block took."""
    start = time.perf_counter()
    try:
        yield
    finally:
        log.info("%s: %.2fs", stage, time.perf_counter() - start)
