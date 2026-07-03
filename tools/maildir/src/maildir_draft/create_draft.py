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

"""Create an editable outbound mail *draft* in a local Maildir.

This is a ``contract:mail-create`` backend whose vendor is the Maildir
format itself — no cloud provider, no credentials, no network. It composes
a plain-text RFC 5322 message and files it into a Maildir with the ``D``
(draft) flag, where any Maildir-aware mail client (Thunderbird, mutt,
Evolution, aerc, …) picks it up in its Drafts view for the human to review,
edit, and send by hand.

Like every ``contract:mail-create`` backend it **only creates drafts**. The
contract models a future ``send`` mode as a declared-but-unimplemented seam;
this backend raises rather than sending, because a message must never leave
without a human reviewing (and freely editing) the draft first.
"""

from __future__ import annotations

import argparse
import email.utils
import mailbox
import sys
from email.message import EmailMessage
from pathlib import Path

DRAFT_MODE = "draft"
SEND_MODE = "send"


def build_message(
    *,
    sender: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    date: str | None = None,
    message_id: str | None = None,
) -> EmailMessage:
    """Compose a single-part ``text/plain`` RFC 5322 message.

    ``contract:mail-create`` is plain-text only — no ``text/html`` part is
    ever added. Threading headers (``In-Reply-To`` / ``References``) are set
    when supplied so the recipient's client threads the reply correctly.
    """
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = date or email.utils.formatdate(localtime=True)
    msg["Message-ID"] = message_id or email.utils.make_msgid()

    refs = list(references or [])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        # RFC 5322: the References of a reply is the parent's References plus
        # the parent's Message-ID. Callers pass the parent chain via
        # --references and the immediate parent via --in-reply-to; fold the
        # parent id in if it is not already the tail of the chain.
        if in_reply_to not in refs:
            refs.append(in_reply_to)
    if refs:
        msg["References"] = " ".join(refs)

    # Single text/plain part — never set_content twice and never add_alternative.
    msg.set_content(body)
    return msg


def write_draft(msg: EmailMessage, maildir_path: str | Path) -> Path:
    """File ``msg`` into the Maildir at ``maildir_path`` as a draft.

    Creates the Maildir (``tmp``/``new``/``cur``) if it does not exist. The
    message is stored in ``cur`` carrying the Maildir ``D`` (draft) flag, the
    convention Maildir clients read as "unsent draft". Returns the path of the
    written message file.
    """
    # mailbox.Maildir(create=True) creates the maildir's own tmp/new/cur but
    # not any missing parent directories — make those first.
    Path(maildir_path).parent.mkdir(parents=True, exist_ok=True)
    box = mailbox.Maildir(str(maildir_path), create=True)
    md_msg = mailbox.MaildirMessage(msg)
    md_msg.set_subdir("cur")
    md_msg.add_flag("D")
    key = box.add(md_msg)
    box.flush()

    for subdir in ("cur", "new"):
        folder = Path(maildir_path) / subdir
        if not folder.is_dir():
            continue
        for entry in folder.iterdir():
            # Maildir filenames are "<key>" (new) or "<key>:2,<flags>" (cur).
            if entry.name == key or entry.name.startswith(f"{key}:"):
                return entry
    raise RuntimeError(f"draft was written but its file could not be located under {maildir_path!r}")


def _read_body(body_file: str) -> str:
    if body_file == "-":
        return sys.stdin.read()
    return Path(body_file).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maildir-draft-create",
        description="Create an editable outbound mail draft in a local Maildir (never sends).",
    )
    parser.add_argument("--from", dest="sender", required=True, help="From: address.")
    parser.add_argument("--to", required=True, help="To: address(es).")
    parser.add_argument("--cc", default=None, help="Cc: address(es).")
    parser.add_argument("--subject", required=True, help="Subject line.")
    parser.add_argument(
        "--body-file",
        required=True,
        help="Path to a file holding the plain-text body, or '-' to read stdin.",
    )
    parser.add_argument(
        "--maildir",
        required=True,
        help="Path to the Maildir the draft is filed into (created if absent).",
    )
    parser.add_argument("--in-reply-to", default=None, help="Message-ID this draft replies to.")
    parser.add_argument(
        "--references",
        default=None,
        help="Space-separated parent References chain (for correct threading).",
    )
    parser.add_argument(
        "--message-id",
        default=None,
        help="Override the generated Message-ID (mainly for reproducible output).",
    )
    parser.add_argument(
        "--mode",
        choices=(DRAFT_MODE, SEND_MODE),
        default=DRAFT_MODE,
        help="draft (default): file an editable draft. send: declared but not implemented.",
    )
    args = parser.parse_args(argv)

    if args.mode == SEND_MODE:
        parser.error(
            "send mode is a declared-but-unimplemented seam of contract:mail-create — "
            "this backend only creates drafts. Review and send the draft from your mail "
            "client after editing it."
        )

    msg = build_message(
        sender=args.sender,
        to=args.to,
        cc=args.cc,
        subject=args.subject,
        body=_read_body(args.body_file),
        in_reply_to=args.in_reply_to,
        references=args.references.split() if args.references else None,
        message_id=args.message_id,
    )
    path = write_draft(msg, args.maildir)
    print(path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
