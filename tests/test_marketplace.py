# SPDX-FileCopyrightText: 2026 Trackmind
# SPDX-License-Identifier: MIT
"""
Tests for the catalog additions in this change: the "automaqa" plugin entry
in .claude-plugin/marketplace.json and its corresponding row in README.md.

Uses only the standard library (unittest) so it runs without any extra
dependencies, matching the rest of this repo's tooling
(scripts/validate_marketplace.py is itself stdlib-only).

Run with:
    python3 -m unittest tests/test_marketplace.py -v
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README_PATH = REPO_ROOT / "README.md"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_marketplace.py"

KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_readme() -> str:
    return README_PATH.read_text(encoding="utf-8")


def find_plugin(manifest: dict, name: str) -> dict:
    for plugin in manifest["plugins"]:
        if plugin.get("name") == name:
            return plugin
    raise AssertionError(f"plugin {name!r} not found in manifest")


class TestManifestIsWellFormed(unittest.TestCase):
    """Basic sanity checks on the manifest as a whole after this change."""

    def test_manifest_parses_as_json(self):
        data = load_manifest()
        self.assertIsInstance(data, dict)

    def test_plugins_is_a_nonempty_list(self):
        data = load_manifest()
        self.assertIsInstance(data.get("plugins"), list)
        self.assertGreaterEqual(len(data["plugins"]), 2)

    def test_no_duplicate_plugin_names(self):
        data = load_manifest()
        names = [p["name"] for p in data["plugins"]]
        self.assertEqual(len(names), len(set(names)), f"duplicate plugin names found: {names}")

    def test_mcp_rubriq_entry_is_unaffected_by_this_change(self):
        # Regression guard: adding automaqa should not have disturbed the
        # pre-existing mcp-rubriq entry.
        data = load_manifest()
        plugin = find_plugin(data, "mcp-rubriq")
        self.assertEqual(plugin["source"]["url"], "https://github.com/trackmind-ai/mcp-rubriq.git")

    def test_renames_still_reference_existing_or_null_plugin(self):
        data = load_manifest()
        names = {p["name"] for p in data["plugins"]}
        for old, new in data.get("renames", {}).items():
            if new is not None:
                self.assertIn(new, names, f"renames maps {old!r} to nonexistent plugin {new!r}")


class TestAutomaqaPluginEntry(unittest.TestCase):
    """Validates every field of the newly added 'automaqa' plugin entry."""

    def setUp(self):
        self.manifest = load_manifest()
        self.plugin = find_plugin(self.manifest, "automaqa")

    def test_plugin_name_is_kebab_case(self):
        self.assertRegex(self.plugin["name"], KEBAB_CASE)

    def test_source_type_is_git_subdir(self):
        self.assertEqual(self.plugin["source"]["source"], "git-subdir")

    def test_source_has_required_git_subdir_fields(self):
        source = self.plugin["source"]
        for field in ("url", "path"):
            self.assertIn(field, source)
            self.assertTrue(source[field], f"{field!r} must be a non-empty value")

    def test_source_url_points_to_automaqa_repo(self):
        self.assertEqual(
            self.plugin["source"]["url"], "https://github.com/trackmind-ai/AutomaQA.git"
        )

    def test_source_url_ends_with_dot_git(self):
        # git-subdir sources are cloned directly, so the URL must be a valid
        # clone target, not a browser URL.
        self.assertTrue(self.plugin["source"]["url"].endswith(".git"))

    def test_source_path_is_the_plugin_subdirectory(self):
        self.assertEqual(self.plugin["source"]["path"], "plugins/automaqa")

    def test_source_ref_is_pinned_to_a_branch(self):
        self.assertEqual(self.plugin["source"].get("ref"), "main")

    def test_description_is_present_and_matches_pr(self):
        self.assertEqual(
            self.plugin["description"],
            "Installs and verifies a complete E2E toolchain (Playwright for web, "
            "Maestro for mobile), then drives spec-driven test authoring, live "
            "verification, and versioned HTML reporting.",
        )

    def test_author_matches_marketplace_owner(self):
        self.assertEqual(
            self.plugin["author"], {"name": "Trackmind", "email": "oss@trackmind.com"}
        )

    def test_homepage_and_repository_point_to_automaqa(self):
        self.assertEqual(self.plugin["homepage"], "https://github.com/trackmind-ai/AutomaQA")
        self.assertEqual(self.plugin["repository"], "https://github.com/trackmind-ai/AutomaQA")

    def test_license_is_mit(self):
        self.assertEqual(self.plugin["license"], "MIT")

    def test_category_is_testing(self):
        self.assertEqual(self.plugin["category"], "testing")

    def test_keywords_are_a_nonempty_list_of_nonempty_strings(self):
        keywords = self.plugin["keywords"]
        self.assertIsInstance(keywords, list)
        self.assertTrue(keywords)
        for kw in keywords:
            self.assertIsInstance(kw, str)
            self.assertTrue(kw)

    def test_keywords_match_expected_set(self):
        expected = {
            "playwright", "maestro", "e2e", "testing", "automation", "mobile", "web", "qa",
        }
        self.assertEqual(set(self.plugin["keywords"]), expected)

    def test_keywords_have_no_duplicates(self):
        keywords = self.plugin["keywords"]
        self.assertEqual(len(keywords), len(set(keywords)))


class TestReadmeAutomaqaRow(unittest.TestCase):
    """Validates the README table row added for 'automaqa'."""

    def setUp(self):
        self.readme = load_readme()
        self.manifest = load_manifest()
        self.plugin = find_plugin(self.manifest, "automaqa")

    def test_readme_mentions_automaqa(self):
        self.assertIn("automaqa", self.readme)

    def test_readme_row_links_to_automaqa_repo(self):
        self.assertIn("[automaqa](https://github.com/trackmind-ai/AutomaQA)", self.readme)

    def test_readme_row_includes_backticked_repo_shorthand(self):
        self.assertIn("`trackmind-ai/AutomaQA`", self.readme)

    def test_readme_row_description_matches_manifest_description(self):
        # Guards against README/manifest drift, same intent as the drift
        # check in scripts/validate_marketplace.py.
        self.assertIn(self.plugin["description"], self.readme)

    def test_readme_row_is_well_formed_table_row(self):
        pattern = re.compile(
            r"\|\s*\*\*\[automaqa\]\(https://github\.com/trackmind-ai/AutomaQA\)\*\*\s*\|"
            r"[^|]+\|\s*`trackmind-ai/AutomaQA`\s*\|"
        )
        self.assertRegex(self.readme, pattern)

    def test_readme_row_appears_after_mcp_rubriq_row(self):
        # The PR appends the new row after the existing mcp-rubriq row rather
        # than replacing or reordering it.
        rubriq_index = self.readme.index("mcp-rubriq](https://github.com/trackmind-ai/mcp-rubriq)")
        automaqa_index = self.readme.index("automaqa](https://github.com/trackmind-ai/AutomaQA)")
        self.assertLess(rubriq_index, automaqa_index)

    def test_every_manifest_plugin_name_appears_in_readme(self):
        for plugin in self.manifest["plugins"]:
            self.assertIn(
                plugin["name"], self.readme,
                f"plugin {plugin['name']!r} missing from README.md (manifest/README drift)",
            )


class TestValidateMarketplaceScript(unittest.TestCase):
    """
    Exercises the project's own validator against the actual, current
    manifest and README — the same local (non-network) command contributors
    are told to run in README.md ("Adding a plugin to the catalog") and that
    CI runs on every push.
    """

    def test_validator_accepts_the_current_manifest_and_readme(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"validator failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("2 plugin", result.stdout)
        self.assertEqual(result.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()