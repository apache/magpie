# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Tests for spec-status-index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_status_index import (
    READY_STATUSES,
    SKIP_FILES,
    STATUS_ORDER,
    SpecEntry,
    format_json,
    format_table,
    load_specs,
    parse_frontmatter,
)

# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_parses_scalar_fields(self) -> None:
        text = "---\ntitle: My Spec\nstatus: stable\nkind: feature\nmode: Triage\n---\n# body\n"
        fm = parse_frontmatter(text)
        assert fm["title"] == "My Spec"
        assert fm["status"] == "stable"
        assert fm["kind"] == "feature"
        assert fm["mode"] == "Triage"

    def test_no_frontmatter_returns_empty(self) -> None:
        text = "# Just a heading\nno frontmatter here\n"
        assert parse_frontmatter(text) == {}

    def test_block_scalar_ignored(self) -> None:
        # Multi-line block scalars (source: >) are not captured; single-line fields are.
        text = "---\ntitle: Spec Title\nstatus: proposed\nsource: >\n  Some long text\n  on multiple lines\n---\n"
        fm = parse_frontmatter(text)
        assert fm["title"] == "Spec Title"
        assert fm["status"] == "proposed"
        # 'source' starts a block scalar — not captured as a simple field.
        assert "source" not in fm or fm.get("source") in (">", None, "")

    def test_strips_whitespace_from_values(self) -> None:
        text = "---\ntitle:   Padded Title   \nstatus: experimental\n---\n"
        fm = parse_frontmatter(text)
        assert fm["title"] == "Padded Title"

    def test_empty_frontmatter_block(self) -> None:
        text = "---\n---\n# body\n"
        fm = parse_frontmatter(text)
        assert fm == {}

    def test_parses_frontmatter_after_leading_spdx_comment(self) -> None:
        # Real specs open with an SPDX licence comment before the `---` block.
        text = (
            "<!-- SPDX-License-Identifier: Apache-2.0\n"
            "     https://www.apache.org/licenses/LICENSE-2.0 -->\n\n"
            "---\ntitle: Commented Spec\nstatus: experimental\nkind: feature\n"
            "mode: Triage\n---\n# body\n"
        )
        fm = parse_frontmatter(text)
        assert fm["status"] == "experimental"
        assert fm["title"] == "Commented Spec"

    def test_strips_comments_from_readme_template(self) -> None:
        text = """---
title: <functional area>
status: experimental   # stable | experimental | proposed | off
kind: feature          # feature | fix | docs | chore
mode: Triage           # Triage | Mentoring | Drafting | Pairing | infra
source: <MISSION.md clause / code paths this area is grounded in>
acceptance:
  - <verifiable criterion>
---
"""
        fm = parse_frontmatter(text)
        assert fm["status"] == "experimental"
        assert fm["kind"] == "feature"
        assert fm["mode"] == "Triage"

    def test_inline_comment_boundaries_and_quoted_guard(self) -> None:
        text = '---\nmode: Triage\t# modes\ntitle: C# tooling\nsummary: "a # b"\n---\n'
        fm = parse_frontmatter(text)
        assert fm["mode"] == "Triage"
        assert fm["title"] == "C# tooling"
        assert fm["summary"] == '"a # b"'

    def test_hash_after_non_breaking_space_is_kept(self) -> None:
        # YAML separates a comment only with a space or tab.
        fm = parse_frontmatter("---\ntitle: a\u00a0#b\n---\n")
        assert fm["title"] == "a\u00a0#b"


# ---------------------------------------------------------------------------
# load_specs (uses a temp directory with synthetic spec files)
# ---------------------------------------------------------------------------


def _write_spec(
    directory: Path, filename: str, title: str, status: str, kind: str = "feature", mode: str = "infra"
) -> Path:
    """Write a minimal spec file and return the path."""
    path = directory / filename
    path.write_text(f"---\ntitle: {title}\nstatus: {status}\nkind: {kind}\nmode: {mode}\n---\n\n# {title}\n")
    return path


class TestLoadSpecs:
    def test_loads_valid_specs(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "alpha.md", "Alpha Feature", "stable")
        _write_spec(tmp_path, "beta.md", "Beta Feature", "proposed")
        entries = load_specs(tmp_path)
        assert len(entries) == 2
        titles = {e.title for e in entries}
        assert "Alpha Feature" in titles
        assert "Beta Feature" in titles

    def test_skip_files_are_excluded(self, tmp_path: Path) -> None:
        for name in SKIP_FILES:
            (tmp_path / name).write_text("---\ntitle: Skip Me\nstatus: stable\n---\n")
        _write_spec(tmp_path, "real.md", "Real Spec", "stable")
        entries = load_specs(tmp_path)
        assert len(entries) == 1
        assert entries[0].title == "Real Spec"

    def test_files_without_status_are_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "no-status.md").write_text("---\ntitle: No Status\n---\n# body\n")
        _write_spec(tmp_path, "good.md", "Good Spec", "experimental")
        entries = load_specs(tmp_path)
        assert len(entries) == 1
        assert entries[0].title == "Good Spec"

    def test_status_containing_only_comment_is_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "comment-status.md").write_text("---\ntitle: No Status\nstatus: # todo\n---\n")
        assert load_specs(tmp_path) == []

    def test_readme_template_status_is_ready(self, tmp_path: Path) -> None:
        (tmp_path / "new-area.md").write_text(
            """---
title: New area
status: experimental   # stable | experimental | proposed | off
kind: feature          # feature | fix | docs | chore
mode: Triage           # Triage | Mentoring | Drafting | Pairing | infra
source: MISSION.md
acceptance:
  - something verifiable
---
"""
        )
        entries = load_specs(tmp_path)
        ready = [entry for entry in entries if entry.status in READY_STATUSES]
        assert len(ready) == 1
        assert ready[0].status == "experimental"

    def test_entries_sorted_by_status_then_title(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "c.md", "Charlie", "stable")
        _write_spec(tmp_path, "a.md", "Alpha", "proposed")
        _write_spec(tmp_path, "b.md", "Bravo", "experimental")
        entries = load_specs(tmp_path)
        statuses = [e.status for e in entries]
        # proposed (0) < experimental (1) < stable (2)
        assert statuses == ["proposed", "experimental", "stable"]

    def test_same_status_sorted_alphabetically(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "z.md", "Zebra Spec", "stable")
        _write_spec(tmp_path, "a.md", "Apple Spec", "stable")
        entries = load_specs(tmp_path)
        assert entries[0].title == "Apple Spec"
        assert entries[1].title == "Zebra Spec"

    def test_empty_directory(self, tmp_path: Path) -> None:
        entries = load_specs(tmp_path)
        assert entries == []

    def test_fields_populated_correctly(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "myspec.md", "My Spec", "experimental", kind="fix", mode="Triage")
        entries = load_specs(tmp_path)
        assert len(entries) == 1
        e = entries[0]
        assert e.title == "My Spec"
        assert e.status == "experimental"
        assert e.kind == "fix"
        assert e.mode == "Triage"
        assert e.file.name == "myspec.md"


# ---------------------------------------------------------------------------
# READY_STATUSES
# ---------------------------------------------------------------------------


class TestReadyStatuses:
    def test_ready_includes_proposed_and_experimental(self) -> None:
        assert "proposed" in READY_STATUSES
        assert "experimental" in READY_STATUSES

    def test_ready_excludes_stable_and_off(self) -> None:
        assert "stable" not in READY_STATUSES
        assert "off" not in READY_STATUSES


# ---------------------------------------------------------------------------
# format_table
# ---------------------------------------------------------------------------


class TestFormatTable:
    def _make_entry(
        self, title: str, status: str, kind: str = "feature", mode: str = "infra", filename: str = "spec.md"
    ) -> SpecEntry:
        return SpecEntry(file=Path(filename), title=title, status=status, kind=kind, mode=mode)

    def test_empty_list(self) -> None:
        output = format_table([])
        assert "no specs matched" in output

    def test_contains_header(self) -> None:
        entry = self._make_entry("My Spec", "stable")
        output = format_table([entry])
        assert "Title" in output
        assert "Status" in output
        assert "Kind" in output
        assert "Mode" in output
        assert "File" in output

    def test_contains_spec_data(self) -> None:
        entry = self._make_entry("My Spec", "proposed", mode="Triage")
        output = format_table([entry])
        assert "My Spec" in output
        assert "proposed" in output
        assert "Triage" in output
        assert "spec.md" in output

    def test_multiple_statuses_have_blank_separator(self) -> None:
        entries = [
            self._make_entry("Spec A", "proposed", filename="a.md"),
            self._make_entry("Spec B", "stable", filename="b.md"),
        ]
        output = format_table(entries)
        # There should be a blank line between the status groups.
        assert "\n\n" in output


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------


class TestFormatJson:
    def test_valid_json_output(self) -> None:
        entries = [
            SpecEntry(file=Path("spec.md"), title="My Spec", status="stable", kind="feature", mode="infra")
        ]
        output = format_json(entries)
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["title"] == "My Spec"
        assert parsed[0]["status"] == "stable"
        assert parsed[0]["file"] == "spec.md"

    def test_empty_list(self) -> None:
        output = format_json([])
        parsed = json.loads(output)
        assert parsed == []

    def test_all_fields_present(self) -> None:
        entries = [SpecEntry(file=Path("x.md"), title="X", status="proposed", kind="fix", mode="Triage")]
        parsed = json.loads(format_json(entries))
        assert set(parsed[0].keys()) == {"title", "status", "kind", "mode", "file"}


# ---------------------------------------------------------------------------
# STATUS_ORDER
# ---------------------------------------------------------------------------


class TestStatusOrder:
    def test_proposed_before_experimental(self) -> None:
        assert STATUS_ORDER["proposed"] < STATUS_ORDER["experimental"]

    def test_experimental_before_stable(self) -> None:
        assert STATUS_ORDER["experimental"] < STATUS_ORDER["stable"]

    def test_stable_before_off(self) -> None:
        assert STATUS_ORDER["stable"] < STATUS_ORDER["off"]


# ---------------------------------------------------------------------------
# Integration: load real specs if present
# ---------------------------------------------------------------------------


class TestRealSpecs:
    """Smoke-test against the actual specs directory when present."""

    @pytest.fixture
    def specs_dir(self) -> Path | None:
        # Walk up from the test file to find the repo root.
        p = Path(__file__).resolve().parent
        while p != p.parent:
            candidate = p / "tools" / "spec-loop" / "specs"
            if candidate.is_dir():
                return candidate
            p = p.parent
        return None

    def test_real_specs_loadable(self, specs_dir: Path | None) -> None:
        if specs_dir is None:
            pytest.skip("spec-loop/specs directory not found")
        entries = load_specs(specs_dir)
        # There should be at least a few specs.
        assert len(entries) >= 3

    def test_real_specs_have_known_statuses(self, specs_dir: Path | None) -> None:
        from spec_status_index import KNOWN_STATUSES

        if specs_dir is None:
            pytest.skip("spec-loop/specs directory not found")
        entries = load_specs(specs_dir)
        known = set(KNOWN_STATUSES)
        for e in entries:
            assert e.status in known, f"{e.file.name} has unknown status {e.status!r}"

    def test_ready_filter_subset_of_all(self, specs_dir: Path | None) -> None:
        if specs_dir is None:
            pytest.skip("spec-loop/specs directory not found")
        all_entries = load_specs(specs_dir)
        ready = [e for e in all_entries if e.status in READY_STATUSES]
        assert len(ready) <= len(all_entries)
        # Every ready entry must appear in all_entries.
        all_titles = {e.title for e in all_entries}
        for e in ready:
            assert e.title in all_titles
