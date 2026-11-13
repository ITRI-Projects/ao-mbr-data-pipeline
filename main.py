"""Entry point for make dev and the existing scripted flags."""

from src.cli.app import main, select_options

__all__ = ["main", "select_options"]


if __name__ == "__main__":
    raise SystemExit(main())
