# SPDX-FileCopyrightText: 2026 Trackmind
# SPDX-License-Identifier: MIT
"""
Validates .claude-plugin/marketplace.json before it reaches users.

`claude plugin validate .` checks the manifest's shape. This script checks the
things that shape alone can't catch and that only bite after publishing:

  - the marketplace name is kebab-case and not one of Anthropic's reserved names
    (a reserved name stops loading for *every* user, not just new installs)
  - plugin names are kebab-case and unique
  - each source object carries the fields its own type requires
  - `renames` entries point at a plugin that actually exists, or null
  - the README table hasn't drifted from the manifest
  - with --check-sources: every git source is reachable and its ref resolves

Exit code is 0 when clean, 1 when any error is found. Warnings never fail.

Usage:
    python scripts/validate_marketplace.py
    python scripts/validate_marketplace.py --check-sources   # adds network checks
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / ".claude-plugin" / "marketplace.json"

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Reserved for official Anthropic use; a marketplace using one stops loading entirely.
# Source: https://code.claude.com/docs/en/plugin-marketplaces
RESERVED_NAMES = {
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace",
    "anthropic-plugins", "agent-skills", "anthropic-agent-skills",
    "knowledge-work-plugins", "life-sciences", "claude-for-legal",
    "claude-for-financial-services", "financial-services-plugins",
    "first-party-plugins", "healthcare",
}

# source type -> (required fields, optional fields)
SOURCE_TYPES = {
    "github": ({"repo"}, {"ref", "sha"}),
    "url": ({"url"}, {"ref", "sha"}),
    "git-subdir": ({"url", "path"}, {"ref", "sha"}),
    "npm": ({"package"}, {"version", "registry"}),
    "archive": ({"url"}, {"sha256"}),
}

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_source(plugin_name: str, source: object) -> dict | None:
    """Validate one plugin's source. Returns the source dict if it's a git type."""
    if isinstance(source, str):
        if not source.startswith("./"):
            err(f"{plugin_name}: string source {source!r} must start with './'")
        return None

    if not isinstance(source, dict):
        err(f"{plugin_name}: source must be a string or object, got {type(source).__name__}")
        return None

    stype = source.get("source")
    if stype not in SOURCE_TYPES:
        err(f"{plugin_name}: unknown source type {stype!r} "
            f"(expected one of {', '.join(sorted(SOURCE_TYPES))})")
        return None

    required, optional = SOURCE_TYPES[stype]
    present = set(source) - {"source"}
    for field in required - present:
        err(f"{plugin_name}: source type {stype!r} requires field {field!r}")
    for field in present - required - optional:
        warn(f"{plugin_name}: source type {stype!r} does not use field {field!r}")

    if stype in ("github", "url", "git-subdir"):
        if "ref" not in source and "sha" not in source:
            warn(f"{plugin_name}: no 'ref' or 'sha' pin — users will receive an update on "
                 f"every commit to the default branch. Pin to a release tag once one exists.")
        return source
    return None


def check_remote(plugin_name: str, source: dict) -> None:
    """Confirm the git source is reachable and its ref resolves. Requires network."""
    url = source.get("url") or f"https://github.com/{source.get('repo')}.git"
    ref = source.get("sha") or source.get("ref")
    cmd = ["git", "ls-remote", url] + ([ref] if ref and not source.get("sha") else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        err(f"{plugin_name}: could not reach {url} ({e.__class__.__name__})")
        return

    if r.returncode != 0:
        err(f"{plugin_name}: `git ls-remote {url}` failed — repo missing or private?\n"
            f"    {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
        return
    if ref and not source.get("sha") and not r.stdout.strip():
        err(f"{plugin_name}: ref {ref!r} does not exist in {url}")
        return
    print(f"  ok  {plugin_name}: {url}" + (f" @ {ref}" if ref else " (default branch)"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the Trackmind plugin marketplace manifest.")
    ap.add_argument("--check-sources", action="store_true",
                    help="also verify every git source is reachable and its ref resolves")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print(f"FATAL: {MANIFEST} not found", file=sys.stderr)
        return 1

    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FATAL: {MANIFEST.name} is not valid JSON: {e}", file=sys.stderr)
        return 1

    name = data.get("name")
    if not name:
        err("marketplace 'name' is missing")
    elif not KEBAB.match(name):
        err(f"marketplace name {name!r} must be kebab-case (lowercase, hyphen-separated) — "
            f"it is public-facing, e.g. `/plugin install my-plugin@{name}`")
    elif name in RESERVED_NAMES:
        err(f"marketplace name {name!r} is reserved for official Anthropic use and will "
            f"refuse to load for every user")

    owner = data.get("owner") or {}
    if not owner.get("name"):
        err("owner.name is missing")
    if not owner.get("email"):
        warn("owner.email is missing — users have no contact route for catalog problems")

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        err("'plugins' must be a non-empty array")
        plugins = []

    seen: set[str] = set()
    git_sources: list[tuple[str, dict]] = []
    for i, p in enumerate(plugins):
        pname = p.get("name") or f"<plugin #{i}>"
        if not p.get("name"):
            err(f"plugin #{i}: 'name' is required")
        elif not KEBAB.match(p["name"]):
            err(f"{pname}: plugin name must be kebab-case")
        if pname in seen:
            err(f"{pname}: duplicate plugin name")
        seen.add(pname)

        if "source" not in p:
            err(f"{pname}: 'source' is required")
        else:
            src = check_source(pname, p["source"])
            if src:
                git_sources.append((pname, src))

        if not p.get("description"):
            warn(f"{pname}: no description — it shows in `/plugin` listings")

    for old, new in (data.get("renames") or {}).items():
        if new is not None and new not in seen:
            err(f"renames: {old!r} -> {new!r}, but no plugin named {new!r} exists in this catalog")

    # The README table and the manifest are edited in different places and drift easily.
    readme = MANIFEST.parent.parent / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        for pname in seen:
            if pname not in text:
                err(f"{pname}: listed in the manifest but not mentioned in README.md")
    else:
        warn("README.md not found — skipping the manifest/README drift check")

    if args.check_sources and git_sources:
        print("Checking git sources are reachable…")
        for pname, src in git_sources:
            check_remote(pname, src)

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)

    plural = "" if len(plugins) == 1 else "s"
    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).", file=sys.stderr)
        return 1
    print(f"\nMarketplace {name!r} OK — {len(plugins)} plugin{plural}, "
          f"{len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
