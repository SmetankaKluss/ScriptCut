"""Standalone entry point used by the packaged desktop backend."""

from __future__ import annotations

import argparse
import multiprocessing

import uvicorn


def main() -> None:
    from main import app

    parser = argparse.ArgumentParser(description="ScriptCut local backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8642)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
