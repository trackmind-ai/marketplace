# SPDX-FileCopyrightText: 2026 Trackmind
# SPDX-License-Identifier: MIT
"""
Tests for the `automaqa` catalog entry added to `.claude-plugin/marketplace.json`
and its corresponding row in `README.md`.

These tests exercise the same rules `scripts/validate_marketplace.py` enforces in
CI, plus a few checks specific to what this change touched: the new plugin's
shape, its `git-subdir` source, and that the manifest and README table agree.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README_PATH = REPO_ROOT / "README.md"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_marketplace.py"

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _load_validator():
    """Import scripts/validate_marketplace.py as a module without running main()."""
    spec = importlib.util.spec_from_file_location("validate_marketplace", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


validate_marketplace = _load_validator()


@pytest.fixture(autouse=True)
def _reset_validator_state():
    """`validate_marketplace` accumulates into module-level lists; keep tests isolated."""
    validate_marketplace.errors.clear()
    validate_marketplace.warnings.clear()
    yield
    validate_marketplace.errors.clear()
    validate_marketplace.warnings.clear()


@pytest.fixture(scope="module")
def manifest_text() -> str:
    return MANIFEST_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest_data(manifest_text: str) -> dict:
    return json.loads(manifest_text)


@pytest.fixture(scope="module")
def readme_text() -> str:
    return README_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def automaqa_entry(manifest_data: dict) -> dict:
    matches = [p for p in manifest_data["plugins"] if p.get("name") == "automaqa"]
    assert len(matches) == 1, "expected exactly one 'automaqa' entry in marketplace.json"
    return matches[0]


# ---------------------------------------------------------------------------
# marketplace.json shape
# ---------------------------------------------------------------------------


class TestManifestIsWellFormed:
    def test_manifest_is_valid_json(self, manifest_text: str) -> None:
        json.loads(manifest_text)  # raises if malformed

    def test_plugins_is_a_non_empty_list(self, manifest_data: dict) -> None:
        assert isinstance(manifest_data["plugins"], list)
        assert manifest_data["plugins"]

    def test_no_duplicate_plugin_names(self, manifest_data: dict) -> None:
        names = [p["name"] for p in manifest_data["plugins"]]
        assert len(names) == len(set(names)), f"duplicate plugin names in {names!r}"


class TestAutomaqaEntry:
    def test_required_top_level_fields_present(self, automaqa_entry: dict) -> None:
        for field in (
            "name",
            "source",
            "description",
            "author",
            "homepage",
            "repository",
            "license",
            "category",
            "keywords",
        ):
            assert field in automaqa_entry, f"missing {field!r}"

    def test_name_is_kebab_case(self, automaqa_entry: dict) -> None:
        # The upstream repo is "AutomaQA" (mixed case); the catalog entry must
        # still be lowercase kebab-case regardless of the repo's own casing.
        assert KEBAB.match(automaqa_entry["name"])

    def test_name_matches_kebab_regex_from_validator(self, automaqa_entry: dict) -> None:
        assert validate_marketplace.KEBAB.match(automaqa_entry["name"])

    def test_name_is_not_a_reserved_marketplace_name(self, automaqa_entry: dict) -> None:
        # RESERVED_NAMES applies to the marketplace name, not plugin names, but
        # a plugin colliding with a reserved marketplace name is still worth
        # flagging early.
        assert automaqa_entry["name"] not in validate_marketplace.RESERVED_NAMES

    def test_description_is_non_empty_string(self, automaqa_entry: dict) -> None:
        assert isinstance(automaqa_entry["description"], str)
        assert automaqa_entry["description"].strip() == automaqa_entry["description"]
        assert automaqa_entry["description"]

    def test_author_matches_trackmind_convention(self, automaqa_entry: dict) -> None:
        assert automaqa_entry["author"] == {"name": "Trackmind", "email": "oss@trackmind.com"}

    def test_homepage_and_repository_point_at_automaqa_repo(self, automaqa_entry: dict) -> None:
        expected = "https://github.com/trackmind-ai/AutomaQA"
        assert automaqa_entry["homepage"] == expected
        assert automaqa_entry["repository"] == expected

    def test_license_is_mit(self, automaqa_entry: dict) -> None:
        assert automaqa_entry["license"] == "MIT"

    def test_category_is_testing(self, automaqa_entry: dict) -> None:
        assert automaqa_entry["category"] == "testing"

    def test_keywords_are_a_non_empty_list_of_unique_lowercase_strings(
        self, automaqa_entry: dict
    ) -> None:
        keywords = automaqa_entry["keywords"]
        assert isinstance(keywords, list)
        assert keywords
        assert all(isinstance(k, str) and k for k in keywords)
        assert all(k == k.lower() for k in keywords)
        assert len(keywords) == len(set(keywords))

    def test_keywords_cover_expected_terms(self, automaqa_entry: dict) -> None:
        expected = {"playwright", "maestro", "e2e", "testing", "automation", "mobile", "web", "qa"}
        assert expected.issubset(set(automaqa_entry["keywords"]))


class TestAutomaqaSource:
    def test_source_type_is_git_subdir(self, automaqa_entry: dict) -> None:
        assert automaqa_entry["source"]["source"] == "git-subdir"

    def test_source_url_targets_automaqa_git_repo(self, automaqa_entry: dict) -> None:
        assert automaqa_entry["source"]["url"] == "https://github.com/trackmind-ai/AutomaQA.git"

    def test_source_path_points_at_plugin_subdirectory(self, automaqa_entry: dict) -> None:
        assert automaqa_entry["source"]["path"] == "plugins/automaqa"

    def test_source_ref_is_pinned(self, automaqa_entry: dict) -> None:
        # Not yet a release tag, but a branch ref is still present, so the
        # validator's "no ref/sha pin" warning must not fire for this entry.
        assert automaqa_entry["source"]["ref"] == "main"

    def test_check_source_reports_no_errors_or_warnings(self, automaqa_entry: dict) -> None:
        result = validate_marketplace.check_source("automaqa", automaqa_entry["source"])
        assert result == automaqa_entry["source"]
        assert validate_marketplace.errors == []
        assert validate_marketplace.warnings == []

    def test_check_source_requires_git_subdir_fields(self, automaqa_entry: dict) -> None:
        # Negative case: dropping a required field (`path`) for a git-subdir
        # source must be caught by the validator.
        broken_source = dict(automaqa_entry["source"])
        del broken_source["path"]
        validate_marketplace.check_source("automaqa", broken_source)
        assert any("requires field 'path'" in e for e in validate_marketplace.errors)

    def test_check_source_warns_when_unpinned(self, automaqa_entry: dict) -> None:
        # Negative case: removing both `ref` and `sha` should produce the
        # "no pin" warning rather than silently passing.
        unpinned_source = dict(automaqa_entry["source"])
        del unpinned_source["ref"]
        validate_marketplace.check_source("automaqa", unpinned_source)
        assert not validate_marketplace.errors
        assert any("no 'ref' or 'sha' pin" in w for w in validate_marketplace.warnings)

    def test_check_source_flags_unknown_extra_field(self, automaqa_entry: dict) -> None:
        # Negative case: an extra, unsupported field on a git-subdir source
        # should be reported as a warning, not silently accepted.
        extra_field_source = dict(automaqa_entry["source"])
        extra_field_source["branch"] = "main"
        validate_marketplace.check_source("automaqa", extra_field_source)
        assert any("does not use field 'branch'" in w for w in validate_marketplace.warnings)


# ---------------------------------------------------------------------------
# README <-> manifest agreement
# ---------------------------------------------------------------------------


class TestReadmeAgreesWithManifest:
    def test_readme_mentions_automaqa(self, readme_text: str) -> None:
        assert "automaqa" in readme_text

    def test_readme_has_a_table_row_for_automaqa(self, readme_text: str) -> None:
        row = self._find_row(readme_text)
        assert row is not None, "no markdown table row found for the automaqa plugin"

    def test_readme_row_links_to_manifest_homepage(
        self, readme_text: str, automaqa_entry: dict
    ) -> None:
        row = self._find_row(readme_text)
        link_match = re.search(r"\[automaqa\]\((?P<url>[^)]+)\)", row)
        assert link_match is not None
        assert link_match.group("url") == automaqa_entry["homepage"]

    def test_readme_row_description_matches_manifest_description(
        self, readme_text: str, automaqa_entry: dict
    ) -> None:
        row = self._find_row(readme_text)
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        assert len(cells) == 3, f"expected a 3-column table row, got {cells!r}"
        _plugin_cell, description_cell, repo_cell = cells
        assert description_cell == automaqa_entry["description"]
        assert repo_cell == "`trackmind-ai/AutomaQA`"

    @staticmethod
    def _find_row(readme_text: str) -> str | None:
        for line in readme_text.splitlines():
            if line.strip().startswith("|") and "automaqa" in line:
                return line
        return None

    def test_all_manifest_plugin_names_appear_in_readme(
        self, manifest_data: dict, readme_text: str
    ) -> None:
        # Mirrors the drift check in scripts/validate_marketplace.py:main().
        for plugin in manifest_data["plugins"]:
            assert plugin["name"] in readme_text, (
                f"{plugin['name']!r} is listed in the manifest but not mentioned in README.md"
            )


# ---------------------------------------------------------------------------
# Full end-to-end validator run (mirrors what CI executes)
# ---------------------------------------------------------------------------


class TestFullValidatorRun:
    def test_validator_passes_with_no_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["validate_marketplace.py"])
        exit_code = validate_marketplace.main()
        assert exit_code == 0
        assert validate_marketplace.errors == []

    def test_validator_check_sources_flag_does_not_error_on_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # We don't want a network call in this test, but --check-sources must
        # still parse and run the non-network checks without raising.
        monkeypatch.setattr(sys, "argv", ["validate_marketplace.py", "--check-sources"])
        monkeypatch.setattr(
            validate_marketplace, "check_remote", lambda *_args, **_kwargs: None
        )
        exit_code = validate_marketplace.main()
        assert exit_code == 0
        assert validate_marketplace.errors == []