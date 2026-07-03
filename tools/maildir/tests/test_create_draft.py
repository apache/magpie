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

import mailbox
from email import message_from_bytes
from pathlib import Path

import pytest

from maildir_draft.create_draft import build_message, main, write_draft


def test_build_message_is_single_plain_text_part():
    msg = build_message(sender="me@example.org", to="you@example.org", subject="Hi", body="Hello\n")
    assert msg["From"] == "me@example.org"
    assert msg["To"] == "you@example.org"
    assert msg["Subject"] == "Hi"
    assert msg["Message-ID"]  # generated
    assert msg["Date"]
    # Plain text only — the contract forbids an HTML alternative.
    assert not msg.is_multipart()
    assert msg.get_content_type() == "text/plain"
    assert msg.get_content() == "Hello\n"


def test_build_message_threading_headers():
    msg = build_message(
        sender="me@example.org",
        to="you@example.org",
        subject="Re: Hi",
        body="reply",
        cc="cc@example.org",
        in_reply_to="<parent@example.org>",
        references=["<root@example.org>"],
    )
    assert msg["Cc"] == "cc@example.org"
    assert msg["In-Reply-To"] == "<parent@example.org>"
    # References = parent chain + immediate parent, parent folded in once.
    assert msg["References"] == "<root@example.org> <parent@example.org>"


def test_build_message_reference_not_duplicated_when_already_tail():
    msg = build_message(
        sender="me@example.org",
        to="you@example.org",
        subject="Re: Hi",
        body="x",
        in_reply_to="<parent@example.org>",
        references=["<root@example.org>", "<parent@example.org>"],
    )
    assert msg["References"] == "<root@example.org> <parent@example.org>"


def test_write_draft_files_into_maildir_with_draft_flag(tmp_path: Path):
    box_path = tmp_path / "Drafts"
    msg = build_message(
        sender="me@example.org",
        to="you@example.org",
        subject="Hi",
        body="body",
        message_id="<fixed@example.org>",
    )
    written = write_draft(msg, box_path)

    # File exists, lives in cur/, and carries the Maildir Draft flag.
    assert written.exists()
    assert written.parent.name == "cur"
    assert ":2," in written.name
    assert "D" in written.name.split(":2,")[1]

    # It is readable back as the same message with the Draft flag set.
    box = mailbox.Maildir(str(box_path))
    (key,) = list(box.iterkeys())
    stored = box[key]
    assert "D" in stored.get_flags()
    parsed = message_from_bytes(written.read_bytes())
    assert parsed["Message-ID"] == "<fixed@example.org>"
    assert parsed["Subject"] == "Hi"


def test_write_draft_creates_maildir_if_absent(tmp_path: Path):
    box_path = tmp_path / "new_store" / "Drafts"
    assert not box_path.exists()
    msg = build_message(sender="a@b.c", to="d@e.f", subject="s", body="b")
    write_draft(msg, box_path)
    for sub in ("tmp", "new", "cur"):
        assert (box_path / sub).is_dir()


def test_main_writes_draft_and_prints_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    body = tmp_path / "body.txt"
    body.write_text("hello from the body")
    box_path = tmp_path / "Drafts"
    rc = main(
        [
            "--from",
            "me@example.org",
            "--to",
            "you@example.org",
            "--subject",
            "Subject here",
            "--body-file",
            str(body),
            "--maildir",
            str(box_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert Path(out).exists()
    assert Path(out).read_text().count("hello from the body") == 1


def test_main_send_mode_is_rejected(tmp_path: Path):
    body = tmp_path / "body.txt"
    body.write_text("x")
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--from",
                "me@example.org",
                "--to",
                "you@example.org",
                "--subject",
                "s",
                "--body-file",
                str(body),
                "--maildir",
                str(tmp_path / "Drafts"),
                "--mode",
                "send",
            ]
        )
    # argparse error() exits with code 2 and never creates a draft.
    assert exc.value.code == 2
    assert not (tmp_path / "Drafts").exists()
