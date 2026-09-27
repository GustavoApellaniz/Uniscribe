"""Entry point for the Kivy client or the local Python backend."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="UniScribe")
    parser.add_argument(
        "--backend",
        action="store_true",
        help="start the dependency-free HTTP backend instead of the Kivy app",
    )
    args = parser.parse_args(argv)
    if args.backend:
        from uniscribe.backend import main as run_backend

        run_backend()
        return
    from uniscribe.app import UniScribeApp

    UniScribeApp().run()


if __name__ == "__main__":
    main()
