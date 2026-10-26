#!/usr/bin/env python3
"""Host-only callback adapter; one opaque id, no caller-selected command or data.

The trusted host registry injects absolute NANOCLAW_CALLBACK_HOST_ROOT and
NANOCLAW_CALLBACK_NODE. Resolve the regular contained compiled host entrypoint,
run it once with that exact claim id, validate its bounded result and relay JSON.
No network or callback database operation belongs to this adapter.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def run(args: list[str]) -> dict:
    if len(args) != 1 or re.fullmatch(r"[A-Za-z0-9_-]{22}", args[0]) is None:
        raise ValueError("Restore the trusted host callback registration.")
    root = Path(os.environ.get("NANOCLAW_CALLBACK_HOST_ROOT", ""))
    node = Path(os.environ.get("NANOCLAW_CALLBACK_NODE", ""))
    if not root.is_absolute() or not node.is_absolute():
        raise ValueError("Restore host-selected absolute callback paths.")
    try:
        root = root.resolve(strict=True)
    except RuntimeError as error:
        raise ValueError("Restore an acyclic trusted host root.") from error
    target = root / "dist/conference-followup-callback-cli.js"
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root):
        raise ValueError("Install the regular conference callback consumer in the trusted host.")
    result = subprocess.run(
        [str(node), str(target), args[0]],
        cwd=root,
        # Reserve stdout for the result; host warnings/errors remain on stderr.
        env={**os.environ, "LOG_LEVEL": "warn"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    if result.returncode or len(result.stdout.encode("utf-8")) > 2048:
        raise ValueError("Inspect the private host hold before retrying.")
    value = json.loads(result.stdout)
    if (
        not isinstance(value, dict)
        or set(value) != {"status", "text"}
        or value["status"] not in ("applied", "rejected", "stale", "failed")
        or not isinstance(value["text"], str)
        or len(value["text"]) > 200
        or any(0xD800 <= ord(c) <= 0xDFFF for c in value["text"])
    ):
        raise ValueError("Restore the bounded conference callback result contract.")
    return value


def main() -> int:
    try:
        value = run(sys.argv[1:])
    except (ValueError, OSError, subprocess.SubprocessError):
        print(
            "Conference follow-up callback unavailable; "
            "inspect the private host hold before retrying.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
