"""Every script command path in this plugin's skills resolves to a co-shipped
script (`rules/nanoclaw-skill-root.md`).

NanoClaw mounts each skill at `/home/node/.claude/skills/tessl__<skill>/`;
a command block naming `.../tessl__<skill>/scripts/<file>` must point at
`skills/<skill>/scripts/<file>` here, for a skill this plugin ships.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MOUNT = re.compile(r"/home/node/\.claude/skills/([^\s`'\")/]+)(/[^\s`'\")]*)?")
COMMAND = re.compile(r"^tessl__(?P<skill>[a-z0-9-]+)/scripts/(?P<file>[A-Za-z0-9._-]+)$")


def _authored_scope() -> list[Path]:
    files: list[Path] = []
    for skill in ("check-cfps", "nightly-cfp-sync"):
        files.append(REPO_ROOT / "skills" / skill / "SKILL.md")
        files.extend(sorted((REPO_ROOT / "skills" / skill / "references").glob("*.md")))
    return [f for f in files if f.exists()]


def _mount_paths() -> list[tuple[Path, str]]:
    found = []
    for path in _authored_scope():
        for match in MOUNT.finditer(path.read_text(encoding="utf-8")):
            found.append((path, match.group(1) + (match.group(2) or "")))
    return found


def test_the_scan_finds_the_command_paths():
    # Positive control: the scan is not vacuous.
    assert len(_mount_paths()) >= 10


def test_every_mount_path_names_a_shipped_skill_script():
    manifest = json.loads((REPO_ROOT / ".tessl-plugin" / "plugin.json").read_text(encoding="utf-8"))
    shipped = {Path(s).name for s in manifest["skills"]}
    for source, tail in _mount_paths():
        command = COMMAND.match(tail)
        assert command, (
            f"{source.relative_to(REPO_ROOT)}: {tail} is not tessl__<skill>/scripts/<file>"
        )
        assert command["skill"] in shipped, (
            f"{source.relative_to(REPO_ROOT)}: {command['skill']} is not shipped"
        )
        target = REPO_ROOT / "skills" / command["skill"] / "scripts" / command["file"]
        assert target.is_file(), f"{source.relative_to(REPO_ROOT)}: {tail} has no co-shipped script"


def test_the_rule_lists_every_shipped_skill():
    manifest = json.loads((REPO_ROOT / ".tessl-plugin" / "plugin.json").read_text(encoding="utf-8"))
    rule = (REPO_ROOT / "rules" / "nanoclaw-skill-root.md").read_text(encoding="utf-8")
    for skill in manifest["skills"]:
        assert f"`{Path(skill).name}`" in rule
