"""Standalone entry point used by the packaged desktop backend."""

from __future__ import annotations

import argparse
import multiprocessing
import os

import uvicorn


def configure_certificate_bundle() -> None:
    """Give frozen HTTP clients an explicit, bundled CA path."""
    try:
        import certifi

        certificate_bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", certificate_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certificate_bundle)
    except (ImportError, OSError):
        pass


def main() -> None:
    configure_certificate_bundle()
    from main import app

    parser = argparse.ArgumentParser(description="ScriptCut local backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8642)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
