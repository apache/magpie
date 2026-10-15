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

import json

from maildir_draft.create_draft import build_message, write_draft
from maildir_draft.find_drafts import find_drafts, main


def _draft(drafts, **kwargs):
    defaults = {"sender": "me@example.org", "to": "you@example.org", "subject": "Hi", "body": "b\n"}
    write_draft(build_message(**{**defaults, **kwargs}), drafts)


def test_missing_maildir_yields_nothing_and_creates_nothing(tmp_path):
    drafts = tmp_path / "Drafts"
    assert find_drafts(drafts, subject="anything") == []
    assert not drafts.exists()


def test_matches_by_thread_message_id(tmp_path):
    drafts = tmp_path / "Drafts"
    _draft(
        drafts, subject="Re: report", in_reply_to="<parent@example.org>", references=["<root@example.org>"]
    )
    _draft(drafts, subject="Re: other", in_reply_to="<elsewhere@example.org>")

    by_parent = find_drafts(drafts, message_ids=["<parent@example.org>"])
    assert [d["subject"] for d in by_parent] == ["Re: report"]
    # The root of the chain matches too: References carries it.
    by_root = find_drafts(drafts, message_ids=["<root@example.org>"])
    assert [d["subject"] for d in by_root] == ["Re: report"]
    assert by_root[0]["draft_flag"] is True


def test_subject_ignores_reply_prefixes_and_case(tmp_path):
    drafts = tmp_path / "Drafts"
    _draft(drafts, subject="RE: Re: Path traversal in upload")
    assert len(find_drafts(drafts, subject="path traversal")) == 1
    assert len(find_drafts(drafts, subject="Fwd: path TRAVERSAL in upload")) == 1
    assert find_drafts(drafts, subject="unrelated") == []


def test_matches_recipient_in_to_or_cc(tmp_path):
    drafts = tmp_path / "Drafts"
    _draft(drafts, to="reporter@example.com")
    _draft(drafts, to="someone@example.org", cc="Reporter@Example.com")
    _draft(drafts, to="nobody@example.org")
    assert len(find_drafts(drafts, to="reporter@example.com")) == 2


def test_no_criterion_lists_everything(tmp_path):
    drafts = tmp_path / "Drafts"
    _draft(drafts, subject="one")
    _draft(drafts, subject="two")
    assert sorted(d["subject"] for d in find_drafts(drafts)) == ["one", "two"]


def test_read_only(tmp_path):
    drafts = tmp_path / "Drafts"
    _draft(drafts, subject="keep me")
    before = sorted(p.name for p in (drafts / "cur").iterdir())
    find_drafts(drafts, subject="keep")
    assert sorted(p.name for p in (drafts / "cur").iterdir()) == before


def test_cli_prints_json(tmp_path, capsys):
    drafts = tmp_path / "Drafts"
    _draft(drafts, subject="Re: report", in_reply_to="<parent@example.org>")
    assert main(["--maildir", str(drafts), "--message-id", "<parent@example.org>"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [d["subject"] for d in out] == ["Re: report"]
    assert out[0]["in_reply_to"] == "<parent@example.org>"


def test_message_ids_bare_or_bracketed_and_several_per_flag(tmp_path, capsys):
    drafts = tmp_path / "Drafts"
    _draft(drafts, subject="Re: a", in_reply_to="<a@example.org>")
    _draft(drafts, subject="Re: b", in_reply_to="<b@example.org>")
    assert [d["subject"] for d in find_drafts(drafts, message_ids=["a@example.org"])] == ["Re: a"]
    assert main(["--maildir", str(drafts), "--message-id", "a@example.org", "<b@example.org>"]) == 0
    assert sorted(d["subject"] for d in json.loads(capsys.readouterr().out)) == ["Re: a", "Re: b"]


def test_tilde_in_maildir_path_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _draft("~/Mail/Drafts", subject="home draft")
    assert (tmp_path / "Mail" / "Drafts" / "cur").is_dir()
    assert [d["subject"] for d in find_drafts("~/Mail/Drafts")] == ["home draft"]


def test_subject_of_only_reply_prefixes_matches_nothing(tmp_path):
    drafts = tmp_path / "Drafts"
    _draft(drafts, subject="anything")
    assert find_drafts(drafts, subject="Re: ") == []
