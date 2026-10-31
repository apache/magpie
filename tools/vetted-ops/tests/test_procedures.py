#
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
"""The ``procedure`` backend: rollup and body-field writes on the tracker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vetted_ops import body_field_format, cli, config, ops, procedures, rollup_format

TRACKER = "acme/tracker"
MARKER = rollup_format.ROLLUP_MARKER
LEGACY_MARKER = (
    "<!-- airflow-s status rollup v1 — all bot-authored status updates fold into this single comment. -->"
)

CONFIG_TOML = """
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[callers]
"security-issue-sync" = ["rollup-append", "rollup-amend-latest", "rollup-fold",
                         "body-field-set", "body-field-get"]
"security-issue-triage" = ["body-field-get"]
"""


@pytest.fixture()
def policy_path(tmp_path: Path) -> Path:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))
    return cfg_path


@pytest.fixture()
def policy(policy_path: Path) -> config.Config:
    return config.load(policy_path)


class FakeGh:
    """Answers the reads a procedure makes; records every call, writes included."""

    def __init__(
        self,
        *,
        comments: list[dict[str, object]] | None = None,
        body: str = "",
        legacy: dict[str, object] | None = None,
        fail_on: str | None = None,
        collaborators: list[str] | None = None,
        drop_patches: bool = False,
    ) -> None:
        self.comments = comments or []
        #: A PATCH lands on the matching comment unless this is set (a concurrent overwrite).
        self.drop_patches = drop_patches
        #: Set to None to make the collaborator listing fail, as it does without push access.
        self.collaborators: list[str] | None = ["alice", "bob"] if collaborators is None else collaborators
        self.body = body
        self.legacy = legacy or {}
        self.fail_on = fail_on
        self.calls: list[tuple[list[str], bytes | None]] = []

    def __call__(self, argv: list[str], stdin: bytes | None) -> tuple[int, bytes, bytes]:
        self.calls.append((list(argv), stdin))
        if self.fail_on and self.fail_on in argv:
            return 1, b"", b"HTTP 500\n"
        if argv == ["gh", "api", "user", "--jq", ".login"]:
            return 0, b"alice\n", b""
        if argv == ["gh", "api", f"repos/{TRACKER}/collaborators", "--paginate", "--jq", ".[].login"]:
            if self.collaborators is None:
                return 1, b"", b"HTTP 403\n"
            return 0, "".join(f"{c}\n" for c in self.collaborators).encode(), b""
        if argv[:2] == ["gh", "issue"] and argv[2] == "view" and "comments" in argv:
            return 0, json.dumps({"comments": self.comments}).encode(), b""
        if argv[:2] == ["gh", "issue"] and argv[2] == "view" and "body" in argv:
            return 0, (self.body + "\n").encode(), b""
        if argv[:2] == ["gh", "api"] and "-X" not in argv:
            return 0, json.dumps(self.legacy).encode(), b""
        if argv[:2] == ["gh", "api"] and "PATCH" in argv and stdin is not None and not self.drop_patches:
            target = argv[2].rsplit("/", 1)[-1]
            for comment in self.comments:
                if str(comment.get("url") or "").endswith(f"-{target}"):
                    comment["body"] = stdin.decode()
        if argv[:3] == ["gh", "issue", "comment"]:
            return 0, b"https://github.com/acme/tracker/issues/7#issuecomment-901\n", b""
        return 0, b"", b""

    @property
    def writes(self) -> list[tuple[list[str], bytes | None]]:
        return [
            (a, s)
            for a, s in self.calls
            if (a[:3] in (["gh", "issue", "comment"], ["gh", "issue", "edit"])) or "-X" in a
        ]


def runner(fake: FakeGh, *, writes: bool = True, dry_run: bool = False) -> procedures.Runner:
    return procedures.Runner(TRACKER, allow_writes=writes, dry_run=dry_run, exec_fn=fake)


def rollup_comment(body: str, rest_id: str = "555", author: str = "alice") -> dict[str, object]:
    return {
        "id": "IC_kwDOnode",
        "author": {"login": author},
        "url": f"https://github.com/acme/tracker/issues/7#issuecomment-{rest_id}",
        "body": body,
    }


def existing_rollup(*actions: str, marker: str = MARKER) -> str:
    entries = [
        rollup_format.build_entry(date="2026-01-0" + str(i + 1), user="bob", action=a, body=f"entry {i}")
        for i, a in enumerate(actions)
    ]
    body = f"{marker}\n{entries[0]}"
    for e in entries[1:]:
        body = rollup_format.rebuild_with_appended_entry(body, e)
    return body


# --- the runner: tracker only, gh only ----------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["gh", "api", "repos/acme/product/issues/comments/1"],
        ["gh", "api", "repos/acme/tracker-other/issues/1"],
        ["gh", "api", "repos/acme/tracker/../product/issues/1"],
        ["gh", "api", "graphql", "-f", "query=x"],
        ["gh", "api", "user"],
        ["gh", "api", "repos/acme/tracker/issues/1", "--hostname", "evil.example"],
        ["gh", "api", "repos/acme/tracker/issues/1", "repos/acme/product/issues/1"],
        ["gh", "issue", "view", "1", "--repo", "acme/product", "--json", "body"],
        ["gh", "issue", "view", "1", "--json", "body"],
        ["gh", "issue", "view", "1", "--repo", "acme/tracker", "--repo", "acme/product"],
        ["gh", "issue", "close", "1", "--repo", "acme/tracker"],
        ["gh", "pr", "view", "1", "--repo", "acme/tracker"],
        ["sh", "-c", "gh api repos/acme/tracker/issues/1"],
    ],
)
def test_runner_refuses_anything_but_tracker_gh_calls(argv: list[str]) -> None:
    fake = FakeGh()
    with pytest.raises(procedures.RunnerRefused):
        runner(fake).read(argv)
    assert fake.calls == []


@pytest.mark.parametrize(
    "argv",
    [
        ["gh", "api", "repos/acme/tracker/issues/comments/1", "-X", "PATCH", "-F", "body=@/etc/passwd"],
        ["gh", "api", "repos/acme/tracker/issues/comments/1", "-X", "PATCH", "--input", "/etc/passwd"],
        ["gh", "api", "repos/acme/tracker/issues/comments/1", "-X", "PUT", "-F", "body=@-"],
        ["gh", "issue", "edit", "1", "--repo", "acme/tracker", "--body-file", "/etc/passwd"],
        ["gh", "issue", "comment", "1", "--repo", "acme/product", "--body-file", "-"],
    ],
)
def test_runner_refuses_writes_that_read_local_files_or_leave_the_tracker(argv: list[str]) -> None:
    fake = FakeGh()
    with pytest.raises(procedures.RunnerRefused):
        runner(fake).write(argv, stdin="x")
    assert fake.calls == []


def test_a_read_only_runner_cannot_write() -> None:
    fake = FakeGh()
    with pytest.raises(procedures.RunnerRefused, match="read-only"):
        runner(fake, writes=False).write(
            ["gh", "issue", "edit", "1", "--repo", TRACKER, "--body-file", "-"], stdin="x"
        )
    assert fake.calls == []


def test_a_write_cannot_travel_through_the_read_door() -> None:
    fake = FakeGh()
    with pytest.raises(procedures.RunnerRefused, match="writes"):
        runner(fake).read(["gh", "api", f"repos/{TRACKER}/issues/comments/1", "-X", "DELETE"])
    assert fake.calls == []


# --- rollup-append --------------------------------------------------------------


def test_append_creates_the_rollup_when_absent() -> None:
    fake = FakeGh(comments=[{"id": "x", "url": "u", "body": "a human comment"}])
    rc = procedures.rollup_append(
        runner(fake), number="7", action="Sync", text="  hello  ", date="2026-09-28"
    )
    assert rc == 0
    [(argv, stdin)] = fake.writes
    assert argv == ["gh", "issue", "comment", "7", "--repo", TRACKER, "--body-file", "-"]
    assert stdin is not None
    assert stdin.decode() == (
        "<!-- apache-magpie: status-rollup v1 -->\n"
        "<details><summary>2026-09-28 · @alice · Sync</summary>\n\nhello\n\n</details>"
    )


def test_append_patches_the_existing_rollup_by_its_url_id() -> None:
    old = existing_rollup("Import")
    fake = FakeGh(comments=[{"body": "hi", "url": "x"}, rollup_comment(old)])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="new", date="2026-09-28")
    [(argv, stdin)] = fake.writes
    assert argv == ["gh", "api", f"repos/{TRACKER}/issues/comments/555", "-X", "PATCH", "-F", "body=@-"]
    assert stdin is not None
    expected = rollup_format.rebuild_with_appended_entry(
        old, rollup_format.build_entry(date="2026-09-28", user="alice", action="Sync", body="new")
    )
    assert stdin.decode() == expected


def test_append_prints_the_new_rollup_url_and_nothing_else(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeGh(comments=[])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="hello", date="2026-09-28")
    assert capsys.readouterr().out == "https://github.com/acme/tracker/issues/7#issuecomment-901\n"


def test_append_to_an_existing_rollup_prints_its_url(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeGh(comments=[rollup_comment(existing_rollup("Import"))])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="new", date="2026-09-28")
    assert capsys.readouterr().out == "https://github.com/acme/tracker/issues/7#issuecomment-555\n"


def test_amend_prints_the_rollup_url(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeGh(comments=[rollup_comment(existing_rollup("Import"))])
    procedures.rollup_amend_latest(runner(fake), number="7", action="Import", text="filled in")
    assert capsys.readouterr().out == "https://github.com/acme/tracker/issues/7#issuecomment-555\n"


def test_append_finds_a_legacy_marker_rollup() -> None:
    old = existing_rollup("Import", marker=LEGACY_MARKER)
    fake = FakeGh(comments=[rollup_comment(old)])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="new", date="2026-09-28")
    [(argv, stdin)] = fake.writes
    assert argv == ["gh", "api", f"repos/{TRACKER}/issues/comments/555", "-X", "PATCH", "-F", "body=@-"]
    assert stdin is not None
    # The legacy rollup keeps its own marker line; only a new rollup gets the canonical one.
    assert stdin.decode().startswith(f"{LEGACY_MARKER}\n")


def test_append_finds_a_legacy_rollup_written_for_another_tracker_name() -> None:
    old = existing_rollup("Import", marker=LEGACY_MARKER.replace("airflow-s", "acme-security"))
    fake = FakeGh(comments=[rollup_comment(old)])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="new", date="2026-09-28")
    [(argv, _)] = fake.writes
    assert "-X" in argv and argv[argv.index("-X") + 1] == "PATCH"


def test_append_prefers_the_canonical_rollup_over_an_earlier_legacy_one() -> None:
    legacy = existing_rollup("Import", marker=LEGACY_MARKER)
    canonical = existing_rollup("Import", "Sync")
    fake = FakeGh(comments=[rollup_comment(legacy, rest_id="111"), rollup_comment(canonical, rest_id="222")])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="new", date="2026-09-28")
    [(argv, stdin)] = fake.writes
    assert argv[2] == f"repos/{TRACKER}/issues/comments/222"
    assert stdin is not None
    assert stdin.decode().startswith(f"{MARKER}\n")
    assert [e.action for e in rollup_format.iter_entries(stdin.decode())] == ["Import", "Sync", "Sync"]


def test_append_never_creates_a_second_rollup_beside_a_canonical_one() -> None:
    fake = FakeGh(comments=[{"body": "hi", "url": "x"}, rollup_comment(existing_rollup("Import"))])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="new", date="2026-09-28")
    [(argv, _)] = fake.writes
    assert argv[:3] == ["gh", "api", f"repos/{TRACKER}/issues/comments/555"]


def test_amend_prefers_the_canonical_rollup_over_an_earlier_legacy_one() -> None:
    legacy = existing_rollup("Sync", marker=LEGACY_MARKER)
    canonical = existing_rollup("Import", "Sync")
    fake = FakeGh(comments=[rollup_comment(legacy, rest_id="111"), rollup_comment(canonical, rest_id="222")])
    procedures.rollup_amend_latest(runner(fake), number="7", action="Sync", text="rewritten")
    [(argv, stdin)] = fake.writes
    assert argv[2] == f"repos/{TRACKER}/issues/comments/222"
    assert stdin is not None
    assert [e.body for e in rollup_format.iter_entries(stdin.decode())] == ["entry 0", "rewritten"]


# --- rollup_format: markers ---------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "canonical", "rollup"),
    [
        ("<!-- apache-magpie: status-rollup v1 -->\n<details>", True, True),
        ("<!-- apache-magpie: status-rollup v2 -->", True, True),
        (f"{LEGACY_MARKER}\n<details>", False, True),
        ("<!-- acme-security status rollup v1 — x -->", False, True),
        ("<!-- apache-magpie: release-manager-handoff v1 -->", False, False),
        ("<!-- apache-magpie: status-rollup-x v1 -->", False, False),
        ("a reply quoting <!-- apache-magpie: status-rollup v1 -->", False, False),
        ("", False, False),
    ],
)
def test_marker_detection(body: str, canonical: bool, rollup: bool) -> None:
    assert rollup_format.is_canonical_rollup_body(body) is canonical
    assert rollup_format.is_rollup_body(body) is rollup


def test_find_rollup_index_prefers_canonical_then_first_legacy() -> None:
    canonical = existing_rollup("Import")
    legacy = existing_rollup("Import", marker=LEGACY_MARKER)
    assert rollup_format.find_rollup_index(["hi", legacy, canonical]) == 2
    assert rollup_format.find_rollup_index(["hi", legacy, legacy]) == 1
    assert rollup_format.find_rollup_index(["hi", "there"]) is None
    assert rollup_format.find_rollup_index([]) is None


def test_new_rollup_body_starts_with_the_canonical_marker_whatever_the_tracker() -> None:
    entry = rollup_format.build_entry(date="2026-09-28", user="alice", action="Sync", body="x")
    for name in ("", "airflow-s", "acme-security"):
        body = rollup_format.build_new_rollup_body(entry, name)
        assert body == f"<!-- apache-magpie: status-rollup v1 -->\n{entry}"
        assert rollup_format.is_canonical_rollup_body(body)


def test_iter_entries_skips_the_canonical_marker_line() -> None:
    entries = rollup_format.iter_entries(existing_rollup("Import", "Sync"))
    assert [(e.action, e.body) for e in entries] == [("Import", "entry 0"), ("Sync", "entry 1")]


def test_dry_run_makes_no_writes_and_never_echoes_the_body(capsys: pytest.CaptureFixture[str]) -> None:
    old = existing_rollup("Import")
    fake = FakeGh(comments=[rollup_comment(old)])
    procedures.rollup_append(
        runner(fake, dry_run=True), number="7", action="Sync", text="SECRET-TEXT", date="2026-09-28"
    )
    assert fake.writes == []
    out = capsys.readouterr()
    assert "would run: gh api repos/acme/tracker/issues/comments/555 -X PATCH -F body=@-" in out.out
    assert "bytes)" in out.out
    assert "SECRET-TEXT" not in out.out + out.err
    assert "entry 0" not in out.out + out.err


# --- rollup-amend-latest ----------------------------------------------------------


def test_amend_refuses_when_the_latest_action_differs() -> None:
    fake = FakeGh(comments=[rollup_comment(existing_rollup("Import", "Sync"))])
    with pytest.raises(procedures.ProcedureRefused, match="refusing to amend"):
        procedures.rollup_amend_latest(runner(fake), number="7", action="CVE allocated", text="x")
    assert fake.writes == []


def test_amend_replaces_only_the_latest_entry_keeping_date_and_user() -> None:
    old = existing_rollup("Import", "Sync")
    fake = FakeGh(comments=[rollup_comment(old)])
    procedures.rollup_amend_latest(runner(fake), number="7", action="Sync", text="rewritten")
    [(_, stdin)] = fake.writes
    assert stdin is not None
    entries = rollup_format.iter_entries(stdin.decode())
    assert [(e.date, e.user, e.action, e.body) for e in entries] == [
        ("2026-01-01", "@bob", "Import", "entry 0"),
        ("2026-01-02", "@bob", "Sync", "rewritten"),
    ]


def test_amend_refuses_without_a_rollup() -> None:
    fake = FakeGh(comments=[])
    with pytest.raises(procedures.ProcedureRefused, match="no rollup"):
        procedures.rollup_amend_latest(runner(fake), number="7", action="Sync", text="x")
    assert fake.writes == []


# --- rollup-fold ------------------------------------------------------------------


def legacy_comment(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 999,
        "body": "   Status: assessed\n   more",
        "user": {"login": "carol"},
        "created_at": "2025-12-24T10:00:00Z",
        "issue_url": "https://api.github.com/repos/acme/tracker/issues/7",
    }
    base.update(overrides)
    return base


def test_fold_appends_then_deletes_in_that_order() -> None:
    fake = FakeGh(comments=[rollup_comment(existing_rollup("Import"))], legacy=legacy_comment())
    procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="Legacy status")
    (patch, stdin), (delete, _) = fake.writes
    assert patch[2].endswith("/comments/555") and "PATCH" in patch
    assert delete == ["gh", "api", f"repos/{TRACKER}/issues/comments/999", "-X", "DELETE"]
    assert stdin is not None
    latest = rollup_format.iter_entries(stdin.decode())[-1]
    assert (latest.date, latest.user, latest.action) == ("2025-12-24", "@carol", "Legacy status")
    assert latest.body == "Status: assessed\nmore"


def test_fold_does_not_delete_when_the_append_fails() -> None:
    fake = FakeGh(
        comments=[rollup_comment(existing_rollup("Import"))], legacy=legacy_comment(), fail_on="PATCH"
    )
    with pytest.raises(procedures.CommandFailed):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="Legacy status")
    assert not any("DELETE" in argv for argv, _ in fake.calls)


def test_fold_refuses_the_rollup_itself() -> None:
    fake = FakeGh(legacy=legacy_comment(body=existing_rollup("Import")))
    with pytest.raises(procedures.ProcedureRefused, match="rollup itself"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="555", action="x")
    assert fake.writes == []


def test_fold_refuses_a_legacy_marker_rollup() -> None:
    fake = FakeGh(legacy=legacy_comment(body=existing_rollup("Import", marker=LEGACY_MARKER)))
    with pytest.raises(procedures.ProcedureRefused, match="is the rollup itself"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="555", action="x")
    assert fake.writes == []


def dated_rollup(*dates: str, marker: str = MARKER, user: str = "bob") -> str:
    entries = [
        rollup_format.build_entry(date=d, user=user, action=f"Step {d}", body=f"entry {d}") for d in dates
    ]
    body = f"{marker}\n{entries[0]}"
    for e in entries[1:]:
        body = rollup_format.rebuild_with_appended_entry(body, e)
    return body


def test_fold_merges_a_second_legacy_rollup_by_date() -> None:
    canonical = dated_rollup("2026-01-01", "2026-03-01")
    fake = FakeGh(
        comments=[rollup_comment(canonical)],
        legacy=legacy_comment(
            body=dated_rollup("2026-02-01", "2026-04-01", marker=LEGACY_MARKER, user="carol"),
            user={"login": "bob"},
        ),
    )
    procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    (patch, stdin), (delete, _) = fake.writes
    assert patch[2].endswith("/comments/555") and "PATCH" in patch
    assert delete == ["gh", "api", f"repos/{TRACKER}/issues/comments/999", "-X", "DELETE"]
    assert stdin is not None
    merged = stdin.decode()
    assert [e.date for e in rollup_format.iter_entries(merged)] == [
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
        "2026-04-01",
    ]
    # The canonical rollup's own text survives byte for byte.
    first, second = canonical.split("\n\n---\n\n")
    assert merged.startswith(first) and second in merged


def test_fold_refuses_a_second_rollup_that_is_the_rollup() -> None:
    body = dated_rollup("2026-01-01", marker=LEGACY_MARKER)
    fake = FakeGh(comments=[rollup_comment(body, rest_id="999")], legacy=legacy_comment(body=body))
    with pytest.raises(procedures.ProcedureRefused, match="is the rollup itself"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert fake.writes == []


def test_fold_refuses_a_second_rollup_with_an_unparsed_entry() -> None:
    legacy = f"{LEGACY_MARKER}\n<details><summary>free text</summary>\n\nold\n\n</details>"
    fake = FakeGh(
        comments=[rollup_comment(dated_rollup("2026-01-01"))],
        legacy=legacy_comment(body=legacy, user={"login": "bob"}),
    )
    with pytest.raises(procedures.ProcedureRefused, match="not `date · @user · action`"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert fake.writes == []


def test_fold_refuses_a_second_rollup_with_content_the_parser_skips() -> None:
    # A split open tag is invisible to the parser; deleting the comment after
    # merging only the parsed entry would lose it.
    legacy = (
        dated_rollup("2026-02-01", marker=LEGACY_MARKER)
        + "\n\n---\n\n<details>\n<summary>2026-02-02 · @bob · Split</summary>\n\nlost\n\n</details>"
    )
    fake = FakeGh(
        comments=[rollup_comment(dated_rollup("2026-01-01"))],
        legacy=legacy_comment(body=legacy, user={"login": "bob"}),
    )
    with pytest.raises(procedures.ProcedureRefused, match="content outside its parsed entries"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert fake.writes == []


def test_fold_keeps_the_second_rollup_when_the_merge_did_not_land() -> None:
    # A concurrent rollup write between the read and the PATCH: the merged
    # entries are not there afterwards, so the source must survive.
    fake = FakeGh(
        comments=[rollup_comment(dated_rollup("2026-01-01"))],
        legacy=legacy_comment(body=dated_rollup("2026-02-01", marker=LEGACY_MARKER), user={"login": "bob"}),
        drop_patches=True,
    )
    with pytest.raises(procedures.ProcedureRefused, match="not deleted"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert not any("DELETE" in argv for argv, _ in fake.calls)


def test_fold_refuses_when_an_entry_holds_a_nested_details_block() -> None:
    quoted = "<details><summary>2025-12-01 · @x · Example</summary>\n\nq\n\n</details>"
    canonical = f"{MARKER}\n" + rollup_format.build_entry(
        date="2026-01-01", user="bob", action="A", body=quoted
    )
    fake = FakeGh(
        comments=[rollup_comment(canonical)],
        legacy=legacy_comment(body=dated_rollup("2026-02-01", marker=LEGACY_MARKER), user={"login": "bob"}),
    )
    with pytest.raises(procedures.ProcedureRefused, match="nested <details>"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert fake.writes == []


def test_fold_keeps_the_source_when_another_comment_is_the_rollup_afterwards() -> None:
    # The destination vanished after the PATCH: the lookup now finds the
    # legacy source itself, whose entries would pass a content check.
    source = dated_rollup("2026-02-01", marker=LEGACY_MARKER)
    fake = FakeGh(
        comments=[rollup_comment(dated_rollup("2026-01-01"))],
        legacy=legacy_comment(body=source, user={"login": "bob"}),
    )
    real_call = fake.__call__

    def vanishing(argv: list[str], stdin: bytes | None) -> tuple[int, bytes, bytes]:
        result = real_call(argv, stdin)
        if "PATCH" in argv:
            fake.comments = [rollup_comment(source, rest_id="999")]
        return result

    r = procedures.Runner(TRACKER, allow_writes=True, dry_run=False, exec_fn=vanishing)
    with pytest.raises(procedures.ProcedureRefused, match="not deleted"):
        procedures.rollup_fold(r, number="7", comment_id="999", action="x")
    assert not any("DELETE" in argv for argv, _ in fake.calls)


def test_fold_refuses_a_second_rollup_by_an_untrusted_author() -> None:
    # Its entries claim their own `@user` and date, so a non-collaborator could
    # otherwise forge entries into the rollup.
    fake = FakeGh(
        comments=[rollup_comment(dated_rollup("2026-01-01"))],
        legacy=legacy_comment(
            body=dated_rollup("2026-02-01", marker=LEGACY_MARKER), user={"login": "mallory"}
        ),
    )
    with pytest.raises(procedures.ProcedureRefused, match="is not a collaborator"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert fake.writes == []


def test_fold_identifies_a_second_rollup_by_its_fetched_id() -> None:
    # A zero-padded caller id must not slip past the "is the rollup" check.
    body = dated_rollup("2026-01-01", marker=LEGACY_MARKER)
    fake = FakeGh(
        comments=[rollup_comment(body, rest_id="999")],
        legacy=legacy_comment(body=body, user={"login": "bob"}),
    )
    with pytest.raises(procedures.ProcedureRefused, match="is the rollup itself"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="0999", action="x")
    assert fake.writes == []


def test_fold_refuses_a_comment_from_another_issue() -> None:
    fake = FakeGh(legacy=legacy_comment(issue_url="https://api.github.com/repos/acme/tracker/issues/70"))
    with pytest.raises(procedures.ProcedureRefused, match="does not belong"):
        procedures.rollup_fold(runner(fake), number="7", comment_id="999", action="x")
    assert fake.writes == []


# --- body fields ------------------------------------------------------------------

ISSUE_BODY = "### Summary\n\nA bug.\n\n### CVE tool link\n\n_No response_\n\n### Severity\n\nHigh\n"


def test_body_field_set_is_a_no_op_when_unchanged() -> None:
    fake = FakeGh(body=ISSUE_BODY)
    assert procedures.body_field_set(runner(fake), number="7", field="Severity", text="High\n") == 0
    assert fake.writes == []


def test_body_field_set_replaces_one_section() -> None:
    fake = FakeGh(body=ISSUE_BODY)
    procedures.body_field_set(runner(fake), number="7", field="CVE tool link", text="CVE-2026-1234")
    [(argv, stdin)] = fake.writes
    assert argv == ["gh", "issue", "edit", "7", "--repo", TRACKER, "--body-file", "-"]
    assert stdin is not None
    assert stdin.decode() == body_field_format.replace_field(ISSUE_BODY, "CVE tool link", "CVE-2026-1234")


@pytest.mark.parametrize(
    "body", [ISSUE_BODY.replace("### Severity", "### Impact"), ISSUE_BODY + "\n### Severity\n\nLow\n"]
)
def test_body_field_set_refuses_an_absent_or_duplicated_field(body: str) -> None:
    fake = FakeGh(body=body)
    with pytest.raises(procedures.ProcedureRefused):
        procedures.body_field_set(runner(fake), number="7", field="Severity", text="Low")
    assert fake.writes == []


@pytest.mark.parametrize(
    "nested",
    ["> ### Severity\nCritical\n", "- step\n   ### Severity\n   Critical\n", "1. x\n\n   ### Severity\n"],
)
def test_body_field_get_and_set_refuse_an_ambiguous_field(nested: str) -> None:
    body = f"### The issue description\n\n{nested}\n" + ISSUE_BODY
    fake = FakeGh(body=body)
    with pytest.raises(procedures.ProcedureRefused, match="refusing to guess"):
        procedures.body_field_get(runner(fake, writes=False), number="7", field="Severity")
    with pytest.raises(procedures.ProcedureRefused, match="refusing to guess"):
        procedures.body_field_set(runner(fake), number="7", field="Severity", text="Low")
    assert fake.writes == []


def test_body_field_set_refuses_to_replace_a_span_hiding_another_field() -> None:
    body = "### The issue description\n\nreport\n\n   ### Severity\n\nHigh\n"
    fake = FakeGh(body=body)
    with pytest.raises(procedures.ProcedureRefused, match="heading-shaped"):
        procedures.body_field_set(runner(fake), number="7", field="The issue description", text="new")
    assert fake.writes == []


def test_body_field_set_refuses_a_value_that_would_end_the_field() -> None:
    # The body-field contract: any `###` line at column 0 ends a field, fenced or not.
    fake = FakeGh(body="### A\n\nx\n\n### B\n\ny\n")
    for text in ("```\n### B\n```", "x\n###\n"):
        with pytest.raises(procedures.ProcedureRefused, match="would end the field"):
            procedures.body_field_set(runner(fake), number="7", field="A", text=text)
    assert fake.writes == []


def test_body_field_set_refuses_a_value_that_moves_another_field_into_a_block() -> None:
    fake = FakeGh(body="### A\n\nx\n\n### B\n\n```\n")
    with pytest.raises(procedures.ProcedureRefused, match="another field"):
        procedures.body_field_set(runner(fake), number="7", field="A", text="```")
    assert fake.writes == []


def test_body_field_get_prints_only_the_value(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeGh(body=ISSUE_BODY)
    procedures.body_field_get(runner(fake, writes=False), number="7", field="Severity")
    assert capsys.readouterr().out == "High\n"


# --- parameter validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["", "a" * 81, "two\nlines", "-flag", "</summary>", "a · b", "tab\there", " padded", "bell\x07"]
)
def test_action_validator_rejects_bad_labels(bad: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.action(bad)


@pytest.mark.parametrize("good", ["Sync", "CVE allocated", "Fix PR opened (#123)", "Réimport"])
def test_action_validator_accepts_ordinary_labels(good: str) -> None:
    assert ops.action(good) == good


@pytest.mark.parametrize("bad", ["", "b" * 81, "### Severity", "Sev#", "-x", "a\nb", "trailing "])
def test_field_validator_rejects_bad_names(bad: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.field_name(bad)


def test_field_validator_accepts_a_heading_name() -> None:
    assert ops.field_name("Reporter credited as") == "Reporter credited as"


# --- end to end through the dispatcher ---------------------------------------------


def test_cli_append_runs_through_the_write_dispatcher(
    policy_path: Path, policy: config.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh(comments=[])
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    entry = policy.workspace / "entry.md"
    entry.write_text("did things")
    rc = cli.main(
        [
            "--caller",
            "security-issue-sync",
            "--config",
            str(policy_path),
            "rollup-append",
            "7",
            "Sync",
            str(entry),
        ]
    )
    assert rc == cli.EXIT_OK
    [(argv, stdin)] = fake.writes
    assert argv[:3] == ["gh", "issue", "comment"]
    assert stdin is not None and b"did things" in stdin


def test_cli_dry_run_makes_no_writes(
    policy_path: Path, policy: config.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh(body=ISSUE_BODY)
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    value = policy.workspace / "value.md"
    value.write_text("Low\n")
    argv = ["--caller", "security-issue-sync", "--config", str(policy_path), "--dry-run"]
    rc = cli.main([*argv, "body-field-set", "7", "Severity", str(value)])
    assert rc == cli.EXIT_OK
    assert fake.writes == []


def test_cli_rejects_a_bad_action_before_any_gh_call(
    policy_path: Path, policy: config.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh()
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    entry = policy.workspace / "entry.md"
    entry.write_text("x")
    rc = cli.main(
        [
            "--caller",
            "security-issue-sync",
            "--config",
            str(policy_path),
            "rollup-append",
            "7",
            "Sync</summary>",
            str(entry),
        ]
    )
    assert rc == cli.EXIT_POLICY
    assert fake.calls == []


def test_cli_amend_mismatch_is_a_policy_refusal(
    policy_path: Path, policy: config.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh(comments=[rollup_comment(existing_rollup("Import"))])
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    entry = policy.workspace / "entry.md"
    entry.write_text("x")
    rc = cli.main(
        [
            "--caller",
            "security-issue-sync",
            "--config",
            str(policy_path),
            "rollup-amend-latest",
            "7",
            "Sync",
            str(entry),
        ]
    )
    assert rc == cli.EXIT_POLICY
    assert fake.writes == []


def test_body_field_get_is_reachable_from_the_read_dispatcher(
    policy_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh(body=ISSUE_BODY)
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    rc = cli.main_read(
        ["--caller", "security-issue-triage", "--config", str(policy_path), "body-field-get", "7", "Severity"]
    )
    assert rc == cli.EXIT_OK
    assert capsys.readouterr().out == "High\n"


@pytest.mark.parametrize("op", ["rollup-append", "rollup-amend-latest", "rollup-fold", "body-field-set"])
def test_the_read_dispatcher_refuses_every_procedure_write(
    policy_path: Path, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    fake = FakeGh()
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    rc = cli.main_read(
        ["--caller", "security-issue-sync", "--config", str(policy_path), op, "7", "Sync", "x"]
    )
    assert rc == cli.EXIT_POLICY
    assert fake.calls == []


def test_procedure_ops_refuse_without_a_tracker(tmp_path: Path) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(f"workspace = '{workspace}'\n[repos]\nupstream = \"acme/product\"\n")
    cfg = config.load(cfg_path)
    for name in ("rollup-append", "rollup-amend-latest", "rollup-fold", "body-field-set", "body-field-get"):
        with pytest.raises(ops.ParamError, match="does not configure"):
            ops.OPS[name].build(cfg.as_mapping(), number="7")


def test_only_body_field_get_is_a_read() -> None:
    procedure_ops = {n: o for n, o in ops.OPS.items() if o.backend == "procedure"}
    assert {n for n, o in procedure_ops.items() if not o.writes} == {"body-field-get"}
    assert set(procedure_ops) == {
        "rollup-append",
        "rollup-amend-latest",
        "rollup-fold",
        "body-field-set",
        "body-field-get",
    }


# --- the vendored modules stay identical to their sources ---------------------------

_TOOLS = Path(__file__).resolve().parents[2]
_PKG = Path(__file__).resolve().parents[1] / "src" / "vetted_ops"


@pytest.mark.parametrize(
    ("vendored", "source"),
    [
        ("rollup_format.py", "github-rollup/src/github_rollup/rollup.py"),
        ("body_field_format.py", "github-body-field/src/github_body_field/parser.py"),
    ],
)
def test_vendored_module_matches_its_source(vendored: str, source: str) -> None:
    """
    vetted-ops installs as a copy of its own directory, so it cannot import the
    two tools; it carries copies. A copy that drifts would write a rollup or a
    body the tools no longer parse the same way — so the copy must be exact.
    Skipped in an installed copy, where the source tree is absent.
    """
    src = _TOOLS / source
    if not src.is_file():
        pytest.skip(f"source tree absent: {src}")
    assert (_PKG / vendored).read_bytes() == src.read_bytes(), (
        f"{vendored} differs from tools/{source}; re-copy it: cp tools/{source} "
        f"tools/vetted-ops/src/vetted_ops/{vendored}"
    )


# --- the tracker entry point ----------------------------------------------------------

PROCEDURE_OPS = {"rollup-append", "rollup-amend-latest", "rollup-fold", "body-field-set", "body-field-get"}

CONFIG_WIDE = """
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[values]
labels = ["needs triage"]

[callers]
"security-issue-sync" = ["rollup-append", "body-field-get", "comment-update", "issue-add-label",
                         "cve-check-published", "issue-view"]
"""


@pytest.fixture()
def wide_policy(tmp_path: Path) -> Path:
    root = tmp_path / "wide"
    workspace = root / "scratch"
    workspace.mkdir(parents=True)
    workspace.chmod(0o700)
    cfg_path = root / "config.toml"
    cfg_path.write_text(CONFIG_WIDE.format(workspace=workspace))
    return cfg_path


@pytest.mark.parametrize(
    "argv",
    [
        ["comment-update", "1", "body.md"],
        ["issue-add-label", "1", "needs triage"],
        ["issue-view", "1"],
        ["cve-check-published", "CVE-2026-1234"],
    ],
)
def test_tracker_dispatcher_refuses_every_non_procedure_op(
    wide_policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    """The caller is permitted all of these by policy; the entry point still refuses."""

    def no_subprocess(*_a: object, **_k: object) -> None:
        raise AssertionError("nothing may run")

    monkeypatch.setattr(cli.subprocess, "run", no_subprocess)
    monkeypatch.setattr(procedures, "subprocess_exec", no_subprocess)
    rc = cli.main_tracker(["--caller", "security-issue-sync", "--config", str(wide_policy), *argv])
    assert rc == cli.EXIT_POLICY
    assert "not a tracker procedure" in capsys.readouterr().err


def test_tracker_dispatcher_refuses_before_consulting_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An undeclared caller would be a config error; the entry-point refusal comes first."""
    cfg = tmp_path / "config.toml"
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg.write_text(f"workspace = '{workspace}'\n[repos]\nupstream = \"acme/product\"\n")
    rc = cli.main_tracker(["--caller", "nobody", "--config", str(cfg), "issue-add-label", "1", "x"])
    assert rc == cli.EXIT_POLICY
    assert "not a tracker procedure" in capsys.readouterr().err


def test_tracker_dispatcher_runs_the_procedures(
    wide_policy: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh(comments=[], body=ISSUE_BODY)
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    entry = wide_policy.parent / "scratch" / "entry.md"
    entry.write_text("done")
    base = ["--caller", "security-issue-sync", "--config", str(wide_policy)]
    assert cli.main_tracker([*base, "rollup-append", "7", "Sync", str(entry)]) == cli.EXIT_OK
    assert [a[:3] for a, _ in fake.writes] == [["gh", "issue", "comment"]]
    assert capsys.readouterr().out == "https://github.com/acme/tracker/issues/7#issuecomment-901\n"
    assert cli.main_tracker([*base, "body-field-get", "7", "Severity"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "High\n"


def test_tracker_dispatcher_refuses_a_repeated_caller(
    wide_policy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh(body=ISSUE_BODY)
    monkeypatch.setattr(procedures, "subprocess_exec", fake)
    rc = cli.main_tracker(
        [
            "--caller",
            "security-issue-sync",
            "--caller",
            "security-issue-sync",
            "--config",
            str(wide_policy),
            "body-field-get",
            "7",
            "Severity",
        ]
    )
    assert rc == cli.EXIT_POLICY
    assert fake.calls == []


def test_tracker_dispatcher_lists_only_the_procedures(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main_tracker(["list-ops"]) == cli.EXIT_OK
    listed = {
        line.split()[1] for line in capsys.readouterr().out.splitlines() if line[:5] in ("write", "read ")
    }
    # Plus the one non-procedure tracker write that must run outside the sandbox.
    assert listed == PROCEDURE_OPS | {"tracker-publish"}


def test_tracker_console_script_is_declared() -> None:
    import tomllib

    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert pyproject["project"]["scripts"]["vetted-op-tracker"] == "vetted_ops:main_tracker"


# --- rollup authorship: a marker comment by an outsider is not the rollup ----------


def test_append_ignores_a_marker_comment_by_a_non_collaborator() -> None:
    decoy = rollup_comment(existing_rollup("Import"), rest_id="666", author="outsider")
    real = rollup_comment(existing_rollup("Import"), rest_id="222", author="bob")
    fake = FakeGh(comments=[decoy, real])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="x")
    targets = [a for a, _ in fake.writes]
    assert any("issues/comments/222" in " ".join(a) for a in targets)
    assert not any("666" in " ".join(a) for a in targets)


def test_append_creates_a_rollup_when_only_a_decoy_exists() -> None:
    decoy = rollup_comment(existing_rollup("Import"), rest_id="666", author="outsider")
    fake = FakeGh(comments=[decoy])
    procedures.rollup_append(runner(fake), number="7", action="Sync", text="x")
    ((argv, _stdin),) = fake.writes
    assert argv[:3] == ["gh", "issue", "comment"]


def test_amend_refuses_when_only_a_decoy_exists() -> None:
    decoy = rollup_comment(existing_rollup("Import"), rest_id="666", author="outsider")
    fake = FakeGh(comments=[decoy])
    with pytest.raises(procedures.ProcedureRefused, match="no rollup"):
        procedures.rollup_amend_latest(runner(fake), number="7", action="Import", text="x")
    assert fake.writes == []


def test_without_the_collaborator_list_another_authors_rollup_is_refused() -> None:
    # bob may be a collaborator: appending could start a second rollup.
    by_bob = rollup_comment(existing_rollup("Import"), rest_id="222", author="bob")
    fake = FakeGh(comments=[by_bob])
    fake.collaborators = None
    with pytest.raises(procedures.ProcedureRefused, match="cannot list collaborators"):
        procedures.rollup_append(runner(fake), number="7", action="Sync", text="x")
    assert fake.writes == []
