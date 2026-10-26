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
import selectors
import subprocess
import sys
import time
from pathlib import Path

# Limit both streams while reading, not after a potentially unbounded capture.
MAX_STDOUT_BYTES = 2048
MAX_STDERR_BYTES = 8192
HOST_TIMEOUT_SECONDS = 240


def run_bounded(args: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    """Run one host callback with bounded byte streams and a single deadline."""
    with subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            with selectors.DefaultSelector() as streams:
                assert child.stdout is not None and child.stderr is not None
                streams.register(child.stdout, selectors.EVENT_READ, MAX_STDOUT_BYTES)
                streams.register(child.stderr, selectors.EVENT_READ, MAX_STDERR_BYTES)
                buffers = {child.stdout.fileno(): bytearray(), child.stderr.fileno(): bytearray()}
                deadline = time.monotonic() + HOST_TIMEOUT_SECONDS
                while streams.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(args, HOST_TIMEOUT_SECONDS)
                    for key, _ in streams.select(remaining):
                        buffer = buffers[key.fd]
                        chunk = os.read(key.fd, min(4096, key.data - len(buffer) + 1))
                        if not chunk:
                            streams.unregister(key.fileobj)
                            continue
                        buffer.extend(chunk)
                        if len(buffer) > key.data:
                            raise ValueError("Restore the bounded host callback output contract.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(args, HOST_TIMEOUT_SECONDS)
                if child.wait(timeout=remaining):
                    raise ValueError("Inspect the private host hold before retrying.")
                return buffers[child.stdout.fileno()].decode("utf-8")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()


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
    output = run_bounded(
        [str(node), str(target), args[0]],
        cwd=root,
        # Reserve stdout for the result; host warnings/errors remain on stderr.
        env={**os.environ, "LOG_LEVEL": "warn"},
    )
    value = json.loads(output)
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
    except (ValueError, RecursionError, OSError, subprocess.SubprocessError):
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
