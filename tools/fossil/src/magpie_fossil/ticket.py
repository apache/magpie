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

"""Fossil ticket subsystem integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from magpie_fossil.client import FossilError, query_db, run_fossil


def get_ticket(repo_path: Path, tkt_uuid: str) -> dict[str, Any]:
    """Retrieve ticket details and comments by UUID prefix."""
    # Find the ticket uuid match
    rows = query_db(repo_path, "SELECT * FROM ticket WHERE tkt_uuid LIKE ?", (tkt_uuid + "%",))
    if not rows:
        raise FossilError(f"Ticket with UUID prefix '{tkt_uuid}' not found.")
    if len(rows) > 1:
        raise FossilError(f"Ambiguous UUID prefix '{tkt_uuid}': matched {len(rows)} tickets.")

    tkt = rows[0]

    # Try fetching comments from the ticket_chng table if it exists
    comments = []
    try:
        chng_rows = query_db(
            repo_path, "SELECT * FROM ticket_chng WHERE tkt_id = ? ORDER BY tkt_mtime ASC", (tkt["tkt_id"],)
        )
        for idx, chng in enumerate(chng_rows):
            # Check fields that commonly represent a comment or change note
            c_text = chng.get("comment") or chng.get("comment_text") or chng.get("c_text")
            user = chng.get("login") or chng.get("user") or chng.get("username") or "anonymous"
            mtime = chng.get("tkt_mtime") or chng.get("mtime")
            if c_text:
                comments.append({"id": idx + 1, "body": c_text, "author": user, "date": mtime})
    except FossilError as exc:
        import sys

        print(f"Warning: failed to query ticket comments (schema might be custom): {exc}", file=sys.stderr)

    # If the main ticket body has a comment, and no change comments were found,
    # we can treat that as the initial comment
    main_comment = tkt.get("comment") or tkt.get("description")
    if main_comment and not comments:
        comments.append(
            {
                "id": 1,
                "body": main_comment,
                "author": tkt.get("username") or tkt.get("login") or "anonymous",
                "date": tkt.get("tkt_mtime") or tkt.get("mtime"),
            }
        )

    tkt_dict = dict(tkt)
    tkt_dict["comments"] = comments
    return tkt_dict


def list_tickets(repo_path: Path) -> list[dict[str, Any]]:
    """List all tickets in the repository."""
    return query_db(
        repo_path,
        "SELECT tkt_id, tkt_uuid, title, status, type, severity, priority, mtime FROM ticket ORDER BY mtime DESC",
    )


def submit_ticket(repo_path: Path, title: str, body: str, extra_fields: dict[str, str] | None = None) -> str:
    """Create a new ticket using Fossil CLI."""
    args = ["ticket", "add", "-R", str(repo_path), "--", "title", title, "comment", body]
    if extra_fields:
        for k, v in extra_fields.items():
            args.extend([k, v])

    # Fossil ticket add outputs: "Created new ticket <UUID>"
    out = run_fossil(args)
    # Extract UUID
    for word in out.split():
        if len(word) >= 12 and all(c in "0123456789abcdefABCDEF" for c in word):
            return word
    return out.strip()


def update_ticket_fields(repo_path: Path, tkt_uuid: str, fields: dict[str, str]) -> str:
    """Update fields on an existing ticket."""
    # First resolve full UUID to be safe
    tkt = get_ticket(repo_path, tkt_uuid)
    full_uuid = tkt["tkt_uuid"]

    args = ["ticket", "set", full_uuid, "-R", str(repo_path), "--"]
    for k, v in fields.items():
        args.extend([k, v])

    run_fossil(args)
    return full_uuid


def submit_comment(repo_path: Path, tkt_uuid: str, body: str) -> str:
    """Add a comment to an existing ticket."""
    return update_ticket_fields(repo_path, tkt_uuid, {"+comment": body})
