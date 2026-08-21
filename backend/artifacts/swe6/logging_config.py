"""Console logging setup for standalone/dry runs (see runner.py's __main__ (removed - see tests/test_swe6_fixed_blocks.py)
block). Not used automatically when this package is imported: a host app
owns its own logging configuration, and every module here only ever calls
`logging.getLogger(__name__)` so it plugs into whatever the host has set up.
"""
from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("artifacts.swe6").setLevel(level)
