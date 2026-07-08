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

"""Fossil forum subsystem integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from magpie_fossil.client import FossilError, query_db, run_fossil


def parse_forum_artifact(content: str) -> dict[str, Any]:
    """Parse a Fossil forum post artifact manifest."""
    lines = content.splitlines()
    author = "anonymous"
    date = ""
    parent = None
    title = ""
    body_lines = []

    in_payload = False
    for line in lines:
        if in_payload:
            body_lines.append(line)
        elif line.startswith("U "):
            author = line[2:].strip()
        elif line.startswith("D "):
            date = line[2:].strip().replace("T", " ")
        elif line.startswith("I "):
            parent = line[2:].strip()
        elif line.startswith("W "):
            title = line[2:].strip()
        elif line.startswith("Z "):
            in_payload = True

    return {
        "author": author,
        "date": date,
        "parent": parent,
        "title": title,
        "body": "\n".join(body_lines).strip(),
    }


def list_forum_threads(repo_path: Path) -> list[dict[str, Any]]:
    """List all forum threads in the repository."""
    # Find distinct thread root IDs and their UUIDs
    rows = query_db(
        repo_path,
        """
        SELECT DISTINCT forumpost.froot AS root_id, blob.uuid AS root_uuid
        FROM forumpost
        JOIN blob ON forumpost.froot = blob.rid
        ORDER BY forumpost.fmtime DESC
        """,
    )

    threads = []
    for r in rows:
        root_uuid = r["root_uuid"]
        try:
            art_text = run_fossil(["artifact", root_uuid, "-R", str(repo_path)])
            parsed = parse_forum_artifact(art_text)
            threads.append(
                {
                    "thread_uuid": root_uuid,
                    "title": parsed["title"] or "Untitled Thread",
                    "author": parsed["author"],
                    "date": parsed["date"],
                }
            )
        except Exception as exc:
            import sys

            print(
                f"Warning: skipped corrupt or missing forum post artifact '{root_uuid}': {exc}",
                file=sys.stderr,
            )
    return threads


def read_forum_thread(repo_path: Path, thread_uuid: str) -> list[dict[str, Any]]:
    """Read all posts in a specific forum thread."""
    # Resolve the root integer ID from the UUID
    r_rows = query_db(repo_path, "SELECT rid FROM blob WHERE uuid = ?", (thread_uuid,))
    if not r_rows:
        raise FossilError(f"Thread root artifact with UUID '{thread_uuid}' not found.")
    root_id = r_rows[0]["rid"]

    # Fetch all posts in the thread
    rows = query_db(
        repo_path,
        """
        SELECT forumpost.fpid, blob.uuid, forumpost.firt, blob_parent.uuid AS parent_uuid
        FROM forumpost
        JOIN blob ON forumpost.fpid = blob.rid
        LEFT JOIN blob blob_parent ON forumpost.firt = blob_parent.rid
        WHERE forumpost.froot = ?
        ORDER BY forumpost.fmtime ASC
        """,
        (root_id,),
    )

    posts = []
    for r in rows:
        post_uuid = r["uuid"]
        parent_uuid = r["parent_uuid"]
        try:
            art_text = run_fossil(["artifact", post_uuid, "-R", str(repo_path)])
            parsed = parse_forum_artifact(art_text)
            posts.append(
                {
                    "post_uuid": post_uuid,
                    "parent_uuid": parent_uuid,
                    "author": parsed["author"],
                    "date": parsed["date"],
                    "title": parsed["title"],
                    "body": parsed["body"],
                }
            )
        except Exception as exc:
            import sys

            print(
                f"Warning: skipped corrupt or missing forum post artifact '{post_uuid}': {exc}",
                file=sys.stderr,
            )
    return posts
