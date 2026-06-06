"""CLI entry point - re-exports from sharp package for backward compatibility."""

from sharp.cli import app

__all__ = ["app"]

if __name__ == "__main__":
    app()
