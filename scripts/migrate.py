"""Run Alembic migrations with the current environment configuration."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run database migrations.")
    parser.add_argument("revision", nargs="?", default="head", help="Target Alembic revision, default: head.")
    parser.add_argument("--sql", action="store_true", help="Render SQL instead of applying migrations.")
    args = parser.parse_args()

    command = [sys.executable, "-m", "alembic", "upgrade", args.revision]
    if args.sql:
        command.append("--sql")

    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
