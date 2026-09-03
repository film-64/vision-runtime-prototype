#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dynamic_pipeline.core.package_verify import verify_package
from dynamic_pipeline.core.protocol_bundle import verify_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a durable metadata package or bundle.")
    parser.add_argument("path")
    parser.add_argument("--bundle", action="store_true", help="Verify a bundle_manifest checksum bundle instead of a package root.")
    parser.add_argument("--source", default=None, help="Optional source file path used to recompute source_fingerprint sha256.")
    args = parser.parse_args()
    if args.bundle:
        ok, errors = verify_bundle(args.path)
        payload = {"ok": ok, "errors": errors}
    else:
        payload = verify_package(args.path, source_path=args.source).to_dict()
        ok = bool(payload["ok"])
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
