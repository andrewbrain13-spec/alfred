#!/usr/bin/env python3
"""Alfred entrypoint.

Usage:
    python run.py --config config/rules.yaml           # run forever (the daemon)
    python run.py --config config/rules.yaml --once     # single pass, then exit
    python run.py --config config/rules.yaml --check    # validate config only
"""

from __future__ import annotations

import argparse
import logging
import sys

from alfred.config import Config, ConfigError
from alfred.engine import Engine


def _setup_logging(log_file: str) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Alfred email-triggered workflow engine")
    parser.add_argument("--config", "-c", default="config/rules.yaml", help="Path to the YAML config")
    parser.add_argument("--once", action="store_true", help="Run a single poll cycle and exit")
    parser.add_argument("--check", action="store_true", help="Validate config and exit")
    parser.add_argument("--baseline", action="store_true",
                        help="Mark current inbox as seen without running workflows (first-time setup)")
    args = parser.parse_args()

    try:
        config = Config.load(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    _setup_logging(config.log_file)

    if args.check:
        # Building the engine constructs every workflow, surfacing bad specs.
        Engine(config)
        print(f"Config OK: {len(config.rules)} rule(s), source '{config.source.get('type')}'.")
        return 0

    engine = Engine(config)
    if args.baseline:
        n = engine.baseline()
        print(f"Baselined {n} existing message(s) as already-seen. "
              f"Alfred will now only react to mail that arrives from here on.")
    elif args.once:
        engine.run_once()
    else:
        engine.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
