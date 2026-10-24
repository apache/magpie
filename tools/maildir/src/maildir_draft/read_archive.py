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

"""Read side (``contract:mail-source``) for a local mail archive.

Serves ``list_recent_threads``, ``read_thread`` and ``thread_url`` over the
three on-disk shapes an adopter can point at: a single mbox file, a Maildir
directory, or a directory of ``.eml`` files. Read-only by construction — no
operation here writes to the archive, and there is no draft or send path
(that is ``maildir-draft-create``'s half of the vendor).

Thread identity is the RFC-5322 ``Message-ID`` of the thread root in the
bracketed form (``<root@host>``), which is what the IMAP backend emits under
the same ``thread_id_kind``. The root itself is the first ``References`` ID,
else the first ``In-Reply-To`` ID, else the message's own ``Message-ID`` —
``imap_source.searching.thread_root_of`` applies the same rule, including when
that root is not in the archive. Both halves have to agree: an ID recorded by a
``-sync`` run against one backend is compared verbatim against the other's.

The archive is scanned whole on every call. These files are forensics /
air-gapped snapshots measured in tens of megabytes, not live mailboxes; an
index would be a second thing to keep consistent for no gain.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import email
import email.header
import email.utils
import hashlib
import html
import json
import mailbox
import re
import sys
import urllib.parse
from email.errors import HeaderParseError
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path
from typing import Any

THREAD_ID_KIND = "rfc5322-message-id"
"""The ``thread_id_kind`` this backend declares for a real ``Message-ID``."""

KEYLESS_THREAD_ID_KIND = "content-hash"
"""Kind for a message with no ``Message-ID``, identified by its bytes instead."""

DEFAULT_SINCE_DAYS = 30

_MSG_ID = re.compile(r"<[^<>\s]+>")
"""The token shape the IMAP backend extracts, brackets included."""

_KEYLESS_PREFIX = "urn:sha256:"

# A `script`/`style` element and its content. The end tag carries `[^>]*`, not
# just `\s*`: HTML permits `</script\t\n bar>` and `</script foo>`, and a
# pattern that only accepts `</script>` would leave the element's code in the
# body (CodeQL py/bad-tag-filter).
_HTML_DROP = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)\b[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_BLOCK_BREAK = re.compile(
    r"</?(?:p|div|br|tr|td|li|h[1-6]|blockquote|pre|table|hr)\b[^>]*>",
    re.IGNORECASE,
)
_HTML_TAG = re.compile(r"<[^>]+>")


def _normalise_id(raw: str) -> str:
    r"""The canonical bracketed form of a Message-ID: ``<id@host>``.

    The IMAP backend keeps the brackets (``imap_source.threads`` matches
    ``<[^<>\s]+>`` and returns the match as written), and both backends declare
    ``thread_id_kind: rfc5322-message-id``. A bare ``id@host`` here would give
    one thread two spellings under one kind, so the "already tracked?" check
    would miss it as soon as an adopter switches — or falls back — between the
    two backends, and a duplicate tracker would get proposed.
    """
    match = _MSG_ID.search(raw)
    if match:
        return match.group(0)
    inner = raw.strip().strip("<>").strip()
    return f"<{inner}>" if inner else ""


def _message_id(msg: Message) -> str | None:
    """The message's own ``Message-ID``, normalised, or None when absent."""
    raw = msg.get("Message-ID") or msg.get("Message-Id")
    if not raw:
        return None
    return _normalise_id(str(raw)) or None


def _reference_ids(msg: Message) -> list[str]:
    """Ancestor Message-IDs in header order: ``References`` first, then ``In-Reply-To``.

    ``References`` is written root-first, so the first entry is the thread root
    even when that message is missing from the archive. That is the rule the
    IMAP backend keys on, so it is the rule here too.

    Only bracketed tokens count. Comments beside the id — ``In-Reply-To:
    (comment) <a@b>``, which real clients do emit — must not become ancestors:
    the thread would be keyed on a Message-ID that never existed and its
    replies would scatter, which is the split this rule exists to prevent.
    """
    ids: list[str] = []
    for header in ("References", "In-Reply-To"):
        raw = msg.get(header)
        if not raw:
            continue
        for token in _MSG_ID.findall(str(raw)):
            if token not in ids:
                ids.append(token)
    return ids


def _content_id(msg: Message) -> str:
    """A snapshot-stable ID for a message that carries no ``Message-ID``.

    Derived from the message bytes rather than from the mailbox key: an mbox key
    is a position, so the same message would get a different key in the next
    export and a stored ID would stop resolving.
    """
    return f"{_KEYLESS_PREFIX}{hashlib.sha256(msg.as_bytes()).hexdigest()}"


def _thread_id_kind(thread_id: str) -> str:
    """The kind tag for ``thread_id`` — a content hash is not an RFC-5322 ID."""
    return KEYLESS_THREAD_ID_KIND if thread_id.startswith(_KEYLESS_PREFIX) else THREAD_ID_KIND


def _thread_key(raw: str) -> str:
    """The key ``group_threads`` files a caller-supplied thread id under.

    A ``urn:sha256:`` id is already the key. Bracketing it, the way a bare
    Message-ID is bracketed, would make the id this backend emits for a message
    with no ``Message-ID`` impossible to read back: ``list_recent_threads``
    would hand it out and ``read_thread`` would answer "not found".
    """
    text = raw.strip()
    if text.startswith(_KEYLESS_PREFIX):
        return text
    return _normalise_id(text)


def _header_text(msg: Message, name: str) -> str:
    """A header value with RFC-2047 encoded words decoded.

    ``message_from_bytes`` parses with the ``compat32`` policy, which leaves
    ``=?utf-8?b?Q2Fmw6k=?=`` untouched; matching on a ``[SECURITY]``
    prefix, inheriting a subject for a reply, and listing participants all need
    the decoded text.
    """
    raw = msg.get(name)
    if raw is None:
        return ""
    text = str(raw)
    if "=?" in text:
        with contextlib.suppress(HeaderParseError, LookupError, UnicodeDecodeError):
            text = str(make_header(decode_header(text)))
    # A folded header keeps its CRLF and continuation space, so flatten it: a
    # subject carrying "\r\n " never matches a `[SECURITY]` prefix test.
    return " ".join(text.split())


def _parse_date(msg: Message) -> dt.datetime | None:
    """The message ``Date`` as an aware datetime, or None when unparsable."""
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(str(raw))
    except (TypeError, ValueError):
        return None
    # A date without a zone is meaningless for ordering across archives; treat
    # it as UTC rather than dropping the message.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


def _decode_payload(part: Message) -> str:
    """A single part's payload as text; ``""`` only when it has no bytes payload."""
    try:
        payload = part.get_payload(decode=True)
    except (AttributeError, LookupError):
        return ""
    if not isinstance(payload, bytes):
        # A nested ``message/rfc822`` or multipart part holds messages, not text.
        return ""
    try:
        return payload.decode(part.get_content_charset() or "utf-8", "replace")
    except LookupError:
        # An unknown charset is a decoding hint we cannot honour, not a reason to
        # lose the body: UTF-8 with replacement characters beats an empty report.
        return payload.decode("utf-8", "replace")


def _html_to_text(markup: str) -> str:
    """A readable approximation of an HTML body: block breaks kept, tags dropped."""
    text = _HTML_DROP.sub(" ", markup)
    text = _HTML_BLOCK_BREAK.sub("\n", text)
    text = _HTML_TAG.sub("", text)
    text = html.unescape(text)
    lines: list[str] = []
    for line in (raw_line.strip() for raw_line in text.splitlines()):
        if not line and (not lines or not lines[-1]):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _body_text(msg: Message) -> str:
    """The message body as text, preferring ``text/plain``.

    An HTML-only report must not come back empty — an empty body is the worst
    outcome for a security report — so a ``text/html`` part is used, with its
    tags stripped, whenever there is no ``text/plain`` alternative.
    """
    plain: str | None = None
    rich: str | None = None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_filename():
            # An attachment, not the body.
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain" and plain is None:
            plain = _decode_payload(part)
        elif content_type == "text/html" and rich is None:
            rich = _decode_payload(part)
        if plain and rich:
            break
    if plain:
        return plain
    if rich:
        return _html_to_text(rich)
    return ""


def detect_format(path: str | Path) -> str:
    """Classify an archive path as ``maildir``, ``eml-dir`` or ``mbox``.

    Raises ``FileNotFoundError`` when the path does not exist, so a typo in the
    adopter's configuration fails loudly instead of reading as an empty archive.
    """
    root = Path(path).expanduser()
    if not root.exists():
        msg = f"Mail archive not found: {root}"
        raise FileNotFoundError(msg)
    if root.is_dir():
        if (root / "cur").is_dir() or (root / "new").is_dir():
            return "maildir"
        return "eml-dir"
    return "mbox"


def iter_messages(path: str | Path) -> list[tuple[str, Message]]:
    """Every message in the archive as ``(key, message)``.

    The order is whatever the store yields — for a Maildir that is directory
    listing order, which is neither chronological nor stable across copies — so
    nothing downstream relies on it and ordering comes from ``Date`` instead.
    ``key`` is a diagnostic handle only (mailbox key, or the file name for an
    ``.eml`` directory), never a thread identifier.
    """
    root = Path(path).expanduser()
    shape = detect_format(root)
    if shape == "mbox":
        box: mailbox.Mailbox = mailbox.mbox(str(root), create=False)
    elif shape == "maildir":
        box = mailbox.Maildir(str(root), create=False)
    else:
        # A standalone `.eml` carries no mbox `From ` envelope, so parse the file
        # as the message it is instead of dressing it up as an mbox message.
        return [
            (item.name, email.message_from_bytes(item.read_bytes()))
            for item in sorted(root.iterdir())
            if item.is_file() and item.suffix.lower() == ".eml"
        ]
    try:
        return [(key, msg) for key, msg in box.iteritems()]
    finally:
        box.close()


def group_threads(messages: list[tuple[str, Message]]) -> dict[str, list[tuple[str, Message]]]:
    """Group messages under their thread root, keyed the way the IMAP backend keys it.

    The root is the first ``References`` / ``In-Reply-To`` ID, else the message's
    own ``Message-ID`` — and it is used even when that root is absent from the
    archive. Keying on the absent root is what keeps two replies to an
    unarchived ``<r@h>`` together under ``<r@h>`` instead of splitting them into
    ``<r1@h>`` and ``<r2@h>``, and it is what makes the ID agree with IMAP's for
    a truncated archive.
    """
    roots: dict[str, list[tuple[str, Message]]] = {}
    seen: set[str] = set()
    for key, msg in messages:
        own_id = _message_id(msg) or _content_id(msg)
        if own_id in seen:
            # A second copy of a message already threaded — a report Cc'd to two
            # lists and exported twice — must not inflate `message_count` or
            # repeat the body.
            continue
        seen.add(own_id)
        ancestors = _reference_ids(msg)
        root = ancestors[0] if ancestors else own_id
        roots.setdefault(root, []).append((key, msg))
    return roots


def _thread_subject(thread_id: str, members: list[tuple[str, Message]]) -> str:
    """The thread's subject, taken from its root message whenever the archive has it.

    A Maildir yields its keys in directory-listing order, so ``members[0]`` can
    easily be a ``Re:`` reply; the subject a thread should be listed under comes
    from the root, or failing that from its earliest dated message.
    """
    for _, msg in members:
        if _message_id(msg) == thread_id:
            return _header_text(msg, "Subject")
    dated = [(_parse_date(msg), msg) for _, msg in members]
    dated.sort(key=lambda item: item[0] or dt.datetime.max.replace(tzinfo=dt.UTC))
    return _header_text(dated[0][1], "Subject") if dated else ""


def _thread_summary(thread_id: str, members: list[tuple[str, Message]]) -> dict[str, Any]:
    """The one-line-per-thread record ``list_recent_threads`` returns."""
    dates = [when for when in (_parse_date(msg) for _, msg in members) if when is not None]
    senders: list[str] = []
    for _, msg in members:
        text = _header_text(msg, "From")
        if not text:
            continue
        sender = email.utils.parseaddr(text)[1] or text
        if sender and sender not in senders:
            senders.append(sender)
    return {
        "thread_id": thread_id,
        "thread_id_kind": _thread_id_kind(thread_id),
        "subject": _thread_subject(thread_id, members),
        "message_count": len(members),
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "participants": senders,
    }


def list_recent_threads(path: str | Path, *, since_days: int = DEFAULT_SINCE_DAYS) -> list[dict[str, Any]]:
    """Threads with at least one message newer than ``since_days``, newest first.

    A thread is kept whole when any of its messages falls inside the window:
    a report whose first message is old but whose last reply is recent is
    still an active thread, and dropping the older messages would hide the
    original report from the import skills.
    """
    if since_days < 0:
        msg = f"since_days must be non-negative, got {since_days}"
        raise ValueError(msg)
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=since_days)
    dated: list[tuple[dt.datetime, dict[str, Any]]] = []
    for thread_id, members in group_threads(iter_messages(path)).items():
        dates = [when for when in (_parse_date(msg) for _, msg in members) if when is not None]
        if dates and max(dates) < cutoff:
            continue
        # A thread with no parseable date cannot be proven stale, so it is kept
        # and ordered last.
        latest = max(dates) if dates else dt.datetime.min.replace(tzinfo=dt.UTC)
        dated.append((latest, _thread_summary(thread_id, members)))
    # Sort on the aware datetime, never on the ISO string: `12:00+00:00` sorts
    # after `13:00+05:00` (08:00Z) as text but before it in real time.
    dated.sort(key=lambda item: item[0], reverse=True)
    return [summary for _, summary in dated]


def read_thread(path: str | Path, thread_id: str) -> dict[str, Any]:
    """Every message in one thread, oldest first, with its plain-text body.

    Raises ``LookupError`` when the thread is not in the archive, so a stale
    stored ID surfaces as a miss rather than an empty thread.
    """
    wanted = _thread_key(thread_id)
    members = group_threads(iter_messages(path)).get(wanted)
    if members is None:
        msg = f"Thread not found in archive: {wanted}"
        raise LookupError(msg)
    # Undated messages sort last, matching `imap_source.threads.sort_key`.
    ordered = sorted(members, key=lambda item: _parse_date(item[1]) or dt.datetime.max.replace(tzinfo=dt.UTC))
    return {
        "thread_id": wanted,
        "thread_id_kind": _thread_id_kind(wanted),
        "subject": _thread_subject(wanted, members),
        "messages": [_message_record(msg) for _, msg in ordered],
    }


def _message_record(msg: Message) -> dict[str, Any]:
    """One message of a thread, as ``read_thread`` reports it."""
    when = _parse_date(msg)
    return {
        "message_id": _message_id(msg),
        "from": _header_text(msg, "From"),
        "to": _header_text(msg, "To"),
        "date": when.isoformat() if when else None,
        "subject": _header_text(msg, "Subject"),
        "body": _body_text(msg),
    }


def thread_url(
    thread_id: str,
    *,
    archive_template: str | None = None,
    archive_path: str | Path | None = None,
) -> str:
    """A clickable URL for the thread.

    ``archive_template`` is the adopter's public-archive deep link with ``{message_id}``
    where the ID goes (HyperKitty and Pipermail both expose one). Without it the
    URL points at the local snapshot, which is honest about being unreachable to
    anyone else rather than inventing a public address the adopter never declared.
    """
    wanted = _thread_key(thread_id)
    if not wanted:
        msg = "thread_url needs a non-empty thread id"
        raise ValueError(msg)
    # Bare and percent-encoded, exactly as `imap_source.archive_url` builds it: a
    # raw Message-ID carries `+`, `/`, `?` and `#`, any of which breaks the link
    # written into a tracker field.
    bare = wanted.strip("<>")
    encoded = urllib.parse.quote(bare, safe="")
    if archive_template:
        return archive_template.replace("{message_id}", encoded)
    if archive_path is not None:
        # `as_uri()` emits the RFC-8089 form; hand-rolled `file://{path}` loses
        # the third slash on a Windows drive path (`file://C:/...`).
        root = Path(archive_path).expanduser().resolve()
        return f"{root.as_uri()}#{encoded}"
    msg = "thread_url needs either an archive template or the archive path"
    raise ValueError(msg)


def threads_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maildir-source-threads",
        description="List threads in a local mbox / Maildir / .eml archive newer than a window (read-only).",
    )
    parser.add_argument("--archive", required=True, help="Path to the mbox file, Maildir, or .eml directory.")
    parser.add_argument(
        "--since-days",
        type=int,
        default=DEFAULT_SINCE_DAYS,
        help=f"How far back to look, in days (default {DEFAULT_SINCE_DAYS}).",
    )
    args = parser.parse_args(argv)
    if args.since_days < 0:
        parser.error(f"--since-days must be non-negative, got {args.since_days}")
    try:
        threads = list_recent_threads(args.archive, since_days=args.since_days)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    json.dump(threads, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def read_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maildir-source-read",
        description="Print every message in one thread from a local mail archive (read-only).",
    )
    parser.add_argument("--archive", required=True, help="Path to the mbox file, Maildir, or .eml directory.")
    parser.add_argument("--thread-id", required=True, help="Thread root Message-ID, with or without <>.")
    args = parser.parse_args(argv)
    try:
        thread = read_thread(args.archive, args.thread_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    except LookupError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    json.dump(thread, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def url_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maildir-source-thread-url",
        description="Print a clickable URL for one thread in a local mail archive.",
    )
    parser.add_argument("--thread-id", required=True, help="Thread root Message-ID, with or without <>.")
    parser.add_argument(
        "--archive-template",
        default=None,
        help="Public-archive URL with {message_id} where the ID goes (HyperKitty / Pipermail shape).",
    )
    parser.add_argument(
        "--archive",
        default=None,
        help="Archive path, used to build a file:// URL when no template is configured.",
    )
    args = parser.parse_args(argv)
    if not args.archive_template and not args.archive:
        parser.error("either --archive-template or --archive is required")
    print(thread_url(args.thread_id, archive_template=args.archive_template, archive_path=args.archive))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(threads_main())
