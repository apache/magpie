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

import datetime as dt
import email
import email.utils
import json
import mailbox
import time
from email.message import EmailMessage

import pytest

from maildir_draft.read_archive import (
    KEYLESS_THREAD_ID_KIND,
    THREAD_ID_KIND,
    detect_format,
    group_threads,
    iter_messages,
    list_recent_threads,
    read_main,
    read_thread,
    thread_url,
    threads_main,
    url_main,
)


def _msg(
    msgid,
    *,
    subject="Security report",
    sender="reporter@example.org",
    days_ago=0,
    when=None,
    body="body\n",
    in_reply_to=None,
    references=None,
):
    msg = EmailMessage()
    if msgid is not None:
        msg["Message-ID"] = f"<{msgid}>"
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = "security@example.org"
    moment = when if when is not None else dt.datetime.now(dt.UTC) - dt.timedelta(days=days_ago)
    msg["Date"] = email.utils.format_datetime(moment)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(f"<{ref}>" for ref in references)
    msg.set_content(body)
    return msg


def _write_mbox(path, messages):
    box = mailbox.mbox(str(path), create=True)
    for msg in messages:
        box.add(msg)
    box.flush()
    box.close()
    return path


def _write_maildir(path, messages):
    box = mailbox.Maildir(str(path), create=True)
    for msg in messages:
        box.add(msg)
    box.flush()
    box.close()
    return path


def _write_eml_dir(path, messages):
    path.mkdir(parents=True, exist_ok=True)
    for index, msg in enumerate(messages):
        (path / f"{index:02d}.eml").write_bytes(msg.as_bytes())
    return path


def _write_raw_eml(path, raws):
    """Write hand-built RFC-822 documents, for shapes `EmailMessage` will not compose."""
    path.mkdir(parents=True, exist_ok=True)
    for index, raw in enumerate(raws):
        (path / f"{index:02d}.eml").write_bytes(raw.encode("utf-8"))
    return path


def test_detect_format_reads_every_supported_shape(tmp_path):
    assert detect_format(_write_mbox(tmp_path / "archive.mbox", [_msg("a@example.org")])) == "mbox"
    assert detect_format(_write_maildir(tmp_path / "Maildir", [_msg("a@example.org")])) == "maildir"
    assert detect_format(_write_eml_dir(tmp_path / "emls", [_msg("a@example.org")])) == "eml-dir"


def test_detect_format_rejects_a_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        detect_format(tmp_path / "nope")


@pytest.mark.parametrize("writer", [_write_mbox, _write_maildir, _write_eml_dir])
def test_every_shape_threads_the_same_way(tmp_path, writer):
    archive = writer(
        tmp_path / "archive",
        [
            _msg("root@example.org", days_ago=5),
            _msg("reply@example.org", days_ago=4, in_reply_to="<root@example.org>"),
            _msg("other@example.org", days_ago=3, subject="Different report"),
        ],
    )

    threads = group_threads(iter_messages(archive))

    assert sorted(threads) == ["<other@example.org>", "<root@example.org>"]
    assert len(threads["<root@example.org>"]) == 2


def test_thread_ids_use_the_bracketed_form_the_imap_backend_emits(tmp_path):
    r"""One `thread_id_kind` must mean one spelling, or the two backends disagree.

    `imap_source` keeps the brackets (`<[^<>\s]+>`), so a bare `root@host` here
    would give the same thread two IDs and a switch between backends would
    propose a duplicate tracker.
    """
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg("root@example.org")])

    threads = list_recent_threads(archive, since_days=30)

    assert threads[0]["thread_id"] == "<root@example.org>"
    assert threads[0]["thread_id_kind"] == THREAD_ID_KIND
    assert read_thread(archive, "root@example.org")["thread_id"] == "<root@example.org>"


def test_references_chain_puts_the_reply_under_the_archive_root(tmp_path):
    """A reply that only carries References still lands in its thread."""
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("root@example.org", days_ago=9),
            _msg("mid@example.org", days_ago=8, in_reply_to="<root@example.org>"),
            _msg("leaf@example.org", days_ago=7, references=["root@example.org", "mid@example.org"]),
        ],
    )

    threads = group_threads(iter_messages(archive))

    assert list(threads) == ["<root@example.org>"]
    assert len(threads["<root@example.org>"]) == 3


def test_replies_to_a_root_missing_from_the_archive_stay_in_one_thread(tmp_path):
    """The archive is truncated at the start of the thread; the replies still group.

    Keying each reply on its own Message-ID split them into `r1@h` and `r2@h`,
    and IMAP keys on the first References ID whether or not that message is
    present, so the two backends also disagreed on the ID.
    """
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("r1@example.org", days_ago=2, in_reply_to="<absent@example.org>"),
            _msg("r2@example.org", days_ago=1, references=["absent@example.org", "r1@example.org"]),
        ],
    )

    threads = group_threads(iter_messages(archive))

    assert list(threads) == ["<absent@example.org>"]
    assert len(threads["<absent@example.org>"]) == 2


def test_a_comment_beside_the_referenced_id_is_not_an_ancestor(tmp_path):
    """`In-Reply-To: (was: report) <r@h>` must key on `<r@h>`, not on `<(was:`.

    RFC 5322 allows a comment in a structured header. Splitting the value on
    whitespace turns that comment into a Message-ID that never existed, and the
    reply lands in a thread of its own — the same split the References rule
    exists to prevent.
    """
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("root@example.org", days_ago=2),
            _msg("reply@example.org", days_ago=1, in_reply_to="(was: report) <root@example.org>"),
        ],
    )

    threads = group_threads(iter_messages(archive))

    assert list(threads) == ["<root@example.org>"]
    assert len(threads["<root@example.org>"]) == 2


def test_list_recent_threads_keeps_a_thread_whole_when_its_reply_is_recent(tmp_path):
    """The old opening report stays visible while the thread is active."""
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("root@example.org", days_ago=200),
            _msg("reply@example.org", days_ago=1, in_reply_to="<root@example.org>"),
            _msg("stale@example.org", days_ago=200, subject="Old and closed"),
        ],
    )

    threads = list_recent_threads(archive, since_days=30)

    assert [t["thread_id"] for t in threads] == ["<root@example.org>"]
    assert threads[0]["message_count"] == 2
    assert threads[0]["thread_id_kind"] == THREAD_ID_KIND


def test_list_recent_threads_sorts_newest_first(tmp_path):
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("older@example.org", days_ago=5),
            _msg("newer@example.org", days_ago=1),
        ],
    )

    threads = list_recent_threads(archive, since_days=30)

    assert [t["thread_id"] for t in threads] == ["<newer@example.org>", "<older@example.org>"]


def test_newest_first_survives_messages_in_different_time_zones(tmp_path):
    """`13:00+05:00` is 08:00Z, so it is older than `12:00+00:00` despite sorting later as text."""
    moment = dt.datetime.now(dt.UTC)
    east = (moment - dt.timedelta(hours=4)).astimezone(dt.timezone(dt.timedelta(hours=5)))
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("east@example.org", when=east),
            _msg("utc@example.org", when=moment),
        ],
    )

    threads = list_recent_threads(archive, since_days=30)

    assert [t["thread_id"] for t in threads] == ["<utc@example.org>", "<east@example.org>"]
    assert threads[1]["last_date"].endswith("+05:00")


def test_duplicate_message_ids_are_counted_once(tmp_path):
    """The same report exported twice must not double `message_count` or the body."""
    first = _msg("root@example.org", days_ago=2, body="original\n")
    second = _msg("root@example.org", days_ago=1, body="original\n")
    second["List-Id"] = "<private.example.org>"
    archive = _write_mbox(tmp_path / "archive.mbox", [first, second])

    threads = list_recent_threads(archive, since_days=30)

    assert threads[0]["message_count"] == 1
    assert [m["body"] for m in read_thread(archive, "<root@example.org>")["messages"]] == ["original\n"]


def test_a_reused_message_id_does_not_hide_a_different_message(tmp_path):
    """Any sender can pick a Message-ID; reusing a report's must not drop the report."""
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("root@example.org", days_ago=2, body="decoy\n"),
            _msg("root@example.org", days_ago=1, body="the real report\n"),
        ],
    )

    bodies = [m["body"] for m in read_thread(archive, "<root@example.org>")["messages"]]

    assert bodies == ["decoy\n", "the real report\n"]


def test_symlinked_messages_are_not_read(tmp_path):
    """A symlink in a snapshot from elsewhere must not pull a local file into the body."""
    secret = tmp_path / "secret.eml"
    secret.write_bytes(_msg("secret@example.org", body="local secret\n").as_bytes())

    emls = tmp_path / "emls"
    emls.mkdir()
    (emls / "report.eml").write_bytes(_msg("report@example.org").as_bytes())
    (emls / "planted.eml").symlink_to(secret)

    maildir = tmp_path / "maildir"
    for sub in ("cur", "tmp"):
        (maildir / sub).mkdir(parents=True)
    (maildir / "cur" / "1700000000.M1P1.host:2,S").write_bytes(_msg("report@example.org").as_bytes())
    (maildir / "cur" / "1700000001.M1P1.host:2,S").symlink_to(secret)
    linked = tmp_path / "linked-new"
    linked.mkdir()
    (linked / "1700000002.M1P1.host").write_bytes(secret.read_bytes())
    (maildir / "new").symlink_to(linked, target_is_directory=True)

    for archive in (emls, maildir):
        ids = [t["thread_id"] for t in list_recent_threads(archive, since_days=30)]

        assert ids == ["<report@example.org>"], archive
        with pytest.raises(LookupError):
            read_thread(archive, "<secret@example.org>")


def test_read_thread_returns_oldest_first_with_bodies(tmp_path):
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg("reply@example.org", days_ago=1, in_reply_to="<root@example.org>", body="second\n"),
            _msg("root@example.org", days_ago=2, body="first\n"),
        ],
    )

    thread = read_thread(archive, "<root@example.org>")

    assert [m["body"] for m in thread["messages"]] == ["first\n", "second\n"]
    assert [m["message_id"] for m in thread["messages"]] == ["<root@example.org>", "<reply@example.org>"]


def test_the_thread_subject_comes_from_the_root_not_the_first_file(tmp_path):
    """Maildir keys come back in listing order, so `members[0]` can be the `Re:` reply."""
    archive = _write_maildir(
        tmp_path / "Maildir",
        [
            _msg(
                "reply@example.org", days_ago=1, in_reply_to="<root@example.org>", subject="Re: Heap overflow"
            ),
            _msg("root@example.org", days_ago=2, subject="Heap overflow"),
        ],
    )

    threads = list_recent_threads(archive, since_days=30)

    assert threads[0]["subject"] == "Heap overflow"
    assert read_thread(archive, "<root@example.org>")["subject"] == "Heap overflow"


def test_read_thread_raises_for_an_unknown_id(tmp_path):
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg("root@example.org")])

    with pytest.raises(LookupError):
        read_thread(archive, "absent@example.org")


def test_encoded_headers_are_decoded(tmp_path):
    """`compat32` leaves `=?utf-8?q?...?=` as-is, which breaks `[SECURITY]` matching."""
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg(
                "root@example.org",
                subject="[SECURITY] Café parser overflow",
                sender="Jöhn Döe <jdoe@example.org>",
            )
        ],
    )

    thread = read_thread(archive, "<root@example.org>")

    assert thread["subject"] == "[SECURITY] Café parser overflow"
    assert thread["messages"][0]["from"] == "Jöhn Döe <jdoe@example.org>"
    assert thread["messages"][0]["subject"] == "[SECURITY] Café parser overflow"


def test_an_html_only_message_still_yields_its_body(tmp_path):
    """An empty body is the worst outcome for a security report."""
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <html@example.org>\r\n"
            "Subject: HTML only\r\n"
            "From: reporter@example.org\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            "MIME-Version: 1.0\r\n"
            'Content-Type: multipart/alternative; boundary="B"\r\n'
            "\r\n"
            "--B\r\n"
            'Content-Type: text/html; charset="utf-8"\r\n'
            "\r\n"
            "<html><body><p>Heap overflow in <b>parser</b></p></body></html>\r\n"
            "--B--\r\n",
        ],
    )

    body = read_thread(archive, "<html@example.org>")["messages"][0]["body"]

    assert "Heap overflow in parser" in body
    assert "<" not in body


def test_script_and_style_content_never_reaches_the_body(tmp_path):
    """The element is dropped whole, however its end tag is spelled.

    HTML permits `</script\\t\\n bar>`. A filter that only accepts `</script>`
    matches nothing, leaves the element's code in the report body, and — worse
    for a security report — puts attacker-supplied script text in front of the
    maintainer as if it were the report (CodeQL py/bad-tag-filter).
    """
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <script@example.org>\r\n"
            "Subject: HTML only\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<html><head><script>var leak = 1;</script\t\n bar></head>"
            "<body><style>p { color: red }</style><p>Heap overflow</p></body></html>\r\n",
        ],
    )

    body = read_thread(archive, "<script@example.org>")["messages"][0]["body"]

    assert "Heap overflow" in body
    assert "leak" not in body
    assert "color" not in body


def test_an_unclosed_script_runs_to_the_end_of_the_document(tmp_path):
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <unclosed@example.org>\r\n"
            "Subject: HTML only\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<p>Heap overflow</p><script>var leak = 1;<p>still script</p>\r\n",
        ],
    )

    body = read_thread(archive, "<unclosed@example.org>")["messages"][0]["body"]

    assert body == "Heap overflow"


def test_hostile_markup_is_stripped_in_linear_time(tmp_path):
    """Runs of `<` and unclosed openers must not make the tag patterns rescan the body."""
    markup = "<p>Heap overflow</p>" + "<" * 400_000 + "<script " * 50_000 + "<p " * 50_000
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <hostile@example.org>\r\n"
            "Subject: HTML only\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            "Content-Type: text/html\r\n"
            "\r\n" + markup + "\r\n",
        ],
    )

    started = time.monotonic()
    body = read_thread(archive, "<hostile@example.org>")["messages"][0]["body"]

    assert body.startswith("Heap overflow")
    # A quadratic pattern takes minutes on this input; the linear one well under a second.
    assert time.monotonic() - started < 10


def test_a_single_part_html_message_is_stripped_to_text(tmp_path):
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <html@example.org>\r\n"
            "Subject: HTML only\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<div>Use after free &amp; overflow</div>\r\n",
        ],
    )

    body = read_thread(archive, "<html@example.org>")["messages"][0]["body"]

    assert body == "Use after free & overflow"


def test_an_unknown_charset_does_not_lose_the_body(tmp_path):
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <charset@example.org>\r\n"
            "Subject: Odd charset\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            'Content-Type: text/plain; charset="x-not-a-charset"\r\n'
            "\r\n"
            "heap overflow\r\n",
        ],
    )

    body = read_thread(archive, "<charset@example.org>")["messages"][0]["body"]

    assert "heap overflow" in body


def test_a_message_without_a_message_id_gets_a_content_derived_id(tmp_path):
    """An mbox key is a position, so it cannot be the stored identifier."""
    archive = _write_mbox(
        tmp_path / "archive.mbox",
        [
            _msg(None, days_ago=1, subject="No Message-ID"),
            _msg(None, days_ago=1, subject="No Message-ID either"),
        ],
    )

    threads = list_recent_threads(archive, since_days=30)

    assert len(threads) == 2
    assert all(t["thread_id"].startswith("urn:sha256:") for t in threads)
    assert all(t["thread_id_kind"] == KEYLESS_THREAD_ID_KIND for t in threads)


def test_a_content_derived_id_can_be_read_back(tmp_path):
    """The id `list_recent_threads` hands out must be the id `read_thread` accepts.

    Bracketing it like a Message-ID makes the one thread this backend can list
    but never read: the sweep sees the report, then fails to open it.
    """
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg(None, days_ago=1, body="no id here\n")])

    thread_id = list_recent_threads(archive, since_days=30)[0]["thread_id"]
    thread = read_thread(archive, thread_id)

    assert thread["thread_id"] == thread_id
    assert thread["thread_id_kind"] == KEYLESS_THREAD_ID_KIND
    assert [message["body"] for message in thread["messages"]] == ["no id here\n"]


def test_a_standalone_eml_is_parsed_as_a_message_not_an_mbox_record(tmp_path):
    """A `.eml` has no `From ` envelope line, and a body line starting with `From ` is not one."""
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <eml@example.org>\r\n"
            "Subject: Standalone\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            'Content-Type: text/plain; charset="utf-8"\r\n'
            "\r\n"
            "From the reporter:\r\n"
            "heap overflow\r\n",
        ],
    )

    messages = iter_messages(archive)

    assert len(messages) == 1
    body = read_thread(archive, "<eml@example.org>")["messages"][0]["body"]
    assert "From the reporter:" in body


def test_thread_url_percent_encodes_the_message_id(tmp_path):
    """A raw Message-ID carries `+`, `/`, `?` and `#`, any of which breaks a tracker link."""
    assert (
        thread_url("a+b/c?d@example.org", archive_template="https://lists.example.org/thread/{message_id}")
        == "https://lists.example.org/thread/a%2Bb%2Fc%3Fd%40example.org"
    )


def test_thread_url_falls_back_to_the_local_snapshot(tmp_path):
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg("root@example.org")])

    url = thread_url("root@example.org", archive_path=archive)

    # `Path.as_uri()` keeps the third slash; `file://{path}` drops it on Windows.
    assert url.startswith("file:///")
    assert url.endswith("#root%40example.org")


def test_thread_url_needs_a_template_or_a_path():
    with pytest.raises(ValueError, match="archive template or the archive path"):
        thread_url("root@example.org")


def test_threads_main_prints_json(tmp_path, capsys):
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg("root@example.org")])

    assert threads_main(["--archive", str(archive), "--since-days", "7"]) == 0

    assert json.loads(capsys.readouterr().out)[0]["thread_id"] == "<root@example.org>"


def test_threads_main_reports_a_missing_archive_without_a_traceback(tmp_path, capsys):
    assert threads_main(["--archive", str(tmp_path / "nope")]) == 1

    assert "Mail archive not found" in capsys.readouterr().err


def test_threads_main_rejects_a_negative_window(tmp_path):
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg("root@example.org")])

    with pytest.raises(SystemExit) as exc:
        threads_main(["--archive", str(archive), "--since-days", "-1"])

    assert exc.value.code == 2


def test_read_main_reports_a_missing_thread(tmp_path, capsys):
    archive = _write_mbox(tmp_path / "archive.mbox", [_msg("root@example.org")])

    assert read_main(["--archive", str(archive), "--thread-id", "absent@example.org"]) == 2

    assert "Thread not found" in capsys.readouterr().err


def test_read_main_reports_a_missing_archive(tmp_path, capsys):
    assert read_main(["--archive", str(tmp_path / "nope"), "--thread-id", "root@example.org"]) == 1

    assert "Mail archive not found" in capsys.readouterr().err


def test_url_main_requires_a_template_or_an_archive(tmp_path):
    with pytest.raises(SystemExit) as exc:
        url_main(["--thread-id", "root@example.org"])

    assert exc.value.code == 2


def test_url_main_prints_the_public_link(capsys):
    assert url_main(["--thread-id", "root@example.org", "--archive-template", "https://x/{message_id}"]) == 0

    assert capsys.readouterr().out.strip() == "https://x/root%40example.org"


def test_a_folded_subject_is_flattened(tmp_path):
    """A folded header keeps its CRLF, which breaks a `[SECURITY]` prefix test."""
    archive = _write_raw_eml(
        tmp_path / "emls",
        [
            "Message-ID: <fold@example.org>\r\n"
            "Subject: [SECURITY] Heap overflow\r\n"
            " in the parser\r\n"
            "From: reporter@example.org\r\n"
            "Date: Sat, 25 Oct 2026 10:00:00 +0000\r\n"
            'Content-Type: text/plain; charset="utf-8"\r\n'
            "\r\n"
            "body\r\n",
        ],
    )

    subject = read_thread(archive, "<fold@example.org>")["subject"]

    assert subject == "[SECURITY] Heap overflow in the parser"
