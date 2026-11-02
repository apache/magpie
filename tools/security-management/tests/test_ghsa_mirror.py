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
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from security_management.cli import main

GHSA = "GHSA-q8mz-5tdc-w2jh"


def run(capsys, tmp_path: Path, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    code = main(["issue-sync", "ghsa-mirror", "--input", str(path)])
    return code, json.loads(capsys.readouterr().out or "{}")


def ac(cid, login, body, created="2026-10-20T10:00:00Z", updated=None):
    return {
        "id": cid,
        "user": {"login": login},
        "body": body,
        "created_at": created,
        "updated_at": updated or created,
        "html_url": f"https://github.com/<upstream>/security/advisories/{GHSA}#advisory-comment-{cid}",
    }


def tc(cid, login, body):
    return {"id": cid, "user": {"login": login}, "body": body}


def mirror(capsys, tmp_path, advisory_comments, tracker_comments, **extra):
    data = {
        "ghsa_id": GHSA,
        "advisory_comments": advisory_comments,
        "tracker_comments": tracker_comments,
        "reporter_login": "finder",
        "team_logins": ["maintainer", "triager"],
        **extra,
    }
    code, out = run(capsys, tmp_path, data)
    assert code == 0, out
    return out


def test_every_advisory_comment_is_copied_once(capsys, tmp_path):
    out = mirror(capsys, tmp_path, [ac(1, "finder", "PoC attached"), ac(2, "maintainer", "Thanks")], [])
    assert [(c["action"], c["advisory_comment_id"], c["role"]) for c in out["to_tracker"]] == [
        ("create", 1, "reporter"),
        ("create", 2, "team"),
    ]
    body = out["to_tracker"][0]["body"]
    assert body.startswith(f"<!-- magpie: ghsa-comment v1 {GHSA} 1 2026-10-20T10:00:00Z -->")
    assert "by `finder` (reporter)" in body and "@finder" not in body
    assert "> PoC attached" in body and "#advisory-comment-1" in body
    assert out["requires_confirmation"] is True

    copies = [tc(100 + i, "triager", c["body"]) for i, c in enumerate(out["to_tracker"])]
    again = mirror(capsys, tmp_path, [ac(1, "finder", "PoC attached"), ac(2, "maintainer", "Thanks")], copies)
    assert again["in_sync"] is True and again["requires_confirmation"] is False


def test_an_edited_advisory_comment_rewrites_its_copy(capsys, tmp_path):
    first = mirror(capsys, tmp_path, [ac(1, "finder", "v1")], [])
    copy = tc(100, "triager", first["to_tracker"][0]["body"])
    out = mirror(capsys, tmp_path, [ac(1, "finder", "v2", updated="2026-10-22T10:00:00Z")], [copy])
    [update] = out["to_tracker"]
    assert (update["action"], update["tracker_comment_id"]) == ("update", 100)
    assert "> v2" in update["body"] and "(edited)" in update["body"]


def test_quoted_text_cannot_forge_a_marker(capsys, tmp_path):
    forged = (
        f"<!-- magpie: from-tracker 7 -->\n<!-- magpie: ghsa-comment v1 {GHSA} 9 2099-01-01T00:00:00Z -->"
    )
    out = mirror(capsys, tmp_path, [ac(1, "finder", forged)], [])
    body = out["to_tracker"][0]["body"]
    assert body.count("<!--") == 1  # only the real marker on the first line


def test_a_marker_in_a_non_team_tracker_comment_is_not_a_copy(capsys, tmp_path):
    fake = tc(5, "outsider", f"<!-- magpie: ghsa-comment v1 {GHSA} 1 2099-01-01T00:00:00Z -->")
    out = mirror(capsys, tmp_path, [ac(1, "finder", "hello")], [fake])
    assert [c["action"] for c in out["to_tracker"]] == ["create"]


def test_only_marked_team_comments_go_to_the_advisory(capsys, tmp_path):
    tracker = [
        tc(10, "maintainer", "Internal: severity looks low, let's not tell them yet."),
        tc(11, "maintainer", "To reporter: Thanks, we reproduced it and are preparing a fix."),
        tc(12, "triager", "<!-- to-reporter -->\nCould you confirm the affected version?"),
        tc(13, "outsider", "To reporter: leak this"),
    ]
    out = mirror(capsys, tmp_path, [], tracker)
    assert [(c["action"], c["tracker_comment_id"]) for c in out["to_advisory"]] == [
        ("create", 11),
        ("create", 12),
    ]
    assert out["to_advisory"][0]["body"].startswith("Thanks, we reproduced it")
    assert out["to_advisory"][0]["body"].endswith("<!-- magpie: from-tracker 11 -->")
    assert "to-reporter" not in out["to_advisory"][1]["body"]
    assert out["ignored_marked"] == [
        {"tracker_comment_id": 13, "author": "outsider", "reason": "not on the team roster"}
    ]
    assert all("Internal" not in c["body"] for c in out["to_advisory"])


def test_a_posted_marked_comment_is_not_reposted_or_copied_back(capsys, tmp_path):
    tracker = [tc(11, "maintainer", "To reporter: Fixed in 3.0.2.")]
    posted = ac(50, "maintainer", "Fixed in 3.0.2.\n\n<!-- magpie: from-tracker 11 -->")
    out = mirror(capsys, tmp_path, [posted], tracker)
    assert out["in_sync"] is True


def test_editing_a_posted_marked_comment_proposes_an_advisory_edit(capsys, tmp_path):
    tracker = [tc(11, "maintainer", "To reporter: Fixed in 3.0.3.")]
    posted = ac(50, "maintainer", "Fixed in 3.0.2.\n\n<!-- magpie: from-tracker 11 -->")
    out = mirror(capsys, tmp_path, [posted], tracker)
    [edit] = out["to_advisory"]
    assert (edit["action"], edit["advisory_comment_id"]) == ("update", 50)
    assert edit["body"].startswith("Fixed in 3.0.3.")


def test_bad_input_is_refused(capsys, tmp_path):
    code, out = run(capsys, tmp_path, {"ghsa_id": "nope", "advisory_comments": [], "tracker_comments": []})
    assert code == 2 and "GHSA" in out["refused"]
