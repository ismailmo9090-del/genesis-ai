"""Entry point for Genesis AI web application."""

import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

BANNER = r"""
  ____           _       _    _____
 / ___|___ _ __ (_)_ __ (_)  / ____|___  _ __ ___  ___
| |   / _ \ '_ \| | '_ \| | | |   / _ \| '__/ _ \/ __|
| |__|  __/ | | | | | | | | | |__| (_) | | |  __/ (__
 \____\___|_| |_|_|_| |_|_|  \____\___/|_|  \___|\___|

  Learn by Experience, Not by Retraining.
  Version: 0.1.0-alpha
"""

def main():
    parser = argparse.ArgumentParser(description="Genesis AI Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(BANNER)
    print(f"  Initializing Genesis AI...")

    from genesis_ai.main import GenesisAI
    genesis = GenesisAI()

    print(f"  Initializing database...")
    genesis.db.init_db()

    from genesis_ai.ui.app import create_app
    app = create_app(genesis)

    print(f"  Starting web server on http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop.\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
