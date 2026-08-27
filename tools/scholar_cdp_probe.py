#!/usr/bin/env python3
"""One-page diagnostic wrapper for ARIS's bounded visible-browser Scholar adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arisctl.browser_scholar import BrowserScholarError, search_google_scholar  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Read one visible Google Scholar result page")
    parser.add_argument("query")
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args()
    try:
        rows = search_google_scholar(args.query, page=args.page)
    except BrowserScholarError as exc:
        print(json.dumps({"query": args.query, "error": str(exc), "blocked": exc.blocked}, ensure_ascii=False))
        return 2
    print(json.dumps({"query": args.query, "page": args.page, "results": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
