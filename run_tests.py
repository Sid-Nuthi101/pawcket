#!/usr/bin/env python3
"""Run Pawcket integration tests with pytest (uses tests/conftest.py for PYTHONPATH)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    try:
        import pytest
    except ImportError as e:
        print(
            "pytest is required. Install dev dependencies, e.g.\n"
            "  pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from e

    # Ensure repo root is cwd so imports and paths match local development.
    import os

    os.chdir(ROOT)
    args = [str(ROOT / "tests"), *sys.argv[1:]]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
