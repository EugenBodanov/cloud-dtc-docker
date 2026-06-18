from __future__ import annotations

from .cli import parse_args
from .pipeline import run_pipeline


def main() -> None:
    run_pipeline(parse_args())
