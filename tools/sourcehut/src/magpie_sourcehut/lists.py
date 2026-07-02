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

"""lists.sr.ht patchsets integration and mapping."""

from __future__ import annotations

import contextlib
from typing import Any

from magpie_sourcehut.client import query_graphql


def _normalize_owner(owner: str) -> str:
    """Ensure the owner username starts with '~'."""
    if not owner.startswith("~"):
        return f"~{owner}"
    return owner


def get_patchset(owner: str, list_name: str, patchset_id: int) -> dict[str, Any]:
    """Retrieve patchset details from lists.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    query GetPatchset($owner: String!, $name: String!, $id: Int!) {
      list(owner: $owner, name: $name) {
        id
        name
        patchset(id: $id) {
          id
          subject
          version
          status
          patches {
            id
            subject
            diff
          }
          thread {
            id
            emails {
              edges {
                node {
                  id
                  subject
                  body
                  sender {
                    canonicalName
                  }
                  date
                }
              }
            }
          }
        }
      }
    }
    """
    res = query_graphql("lists", q, {"owner": owner, "name": list_name, "id": patchset_id})
    mlist = res.get("list") or {}
    return mlist.get("patchset") or {}


def list_patchsets(owner: str, list_name: str) -> list[dict[str, Any]]:
    """List patchsets on a specific mailing list on lists.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    query ListPatchsets($owner: String!, $name: String!) {
      list(owner: $owner, name: $name) {
        id
        name
        patches {
          edges {
            node {
              id
              subject
              version
              status
            }
          }
        }
      }
    }
    """
    res = query_graphql("lists", q, {"owner": owner, "name": list_name})
    mlist = res.get("list") or {}
    patches_conn = mlist.get("patches") or {}
    edges = patches_conn.get("edges") or []
    return [edge.get("node") for edge in edges if edge and edge.get("node")]


def map_patchset_to_pr(patchset: dict[str, Any]) -> dict[str, Any]:
    """Map a lists.sr.ht patchset to a uniform PR/MR review abstraction structure.

    Args:
        patchset: A dictionary representing the patchset retrieved via GraphQL.

    Returns:
        A dictionary containing the uniform PR/MR fields.
    """
    if not patchset:
        return {}

    # Extract thread emails for description & comments
    thread = patchset.get("thread") or {}
    emails_conn = thread.get("emails") or {}
    edges = emails_conn.get("edges") or []
    emails = [edge.get("node") for edge in edges if edge and edge.get("node")]

    # Sort emails by date if possible
    with contextlib.suppress(Exception):
        emails.sort(key=lambda x: x.get("date", ""))

    # The cover letter / description is the first email (or patchset subject)
    description = ""
    author = "Unknown"
    if emails:
        first_email = emails[0]
        description = first_email.get("body", "")
        sender = first_email.get("sender") or {}
        author = sender.get("canonicalName", "Unknown")

    # Map patchset status to a standardized PR state (OPEN, MERGED, CLOSED)
    status = patchset.get("status", "PROPOSED")
    state = "OPEN"
    if status == "ACCEPTED":
        state = "MERGED"
    elif status in ("REJECTED", "SUPERSEDED"):
        state = "CLOSED"

    # Map patches inside the patchset to commits
    commits = []
    for patch in patchset.get("patches") or []:
        if patch:
            commits.append(
                {
                    "id": str(patch.get("id")),
                    "subject": patch.get("subject", ""),
                    "diff": patch.get("diff", ""),
                }
            )

    # Map replies (all emails except the first/cover letter) to review comments
    comments = []
    for email in emails[1:]:
        sender = email.get("sender") or {}
        comments.append(
            {
                "id": str(email.get("id")),
                "author": sender.get("canonicalName", "Unknown"),
                "body": email.get("body", ""),
                "date": email.get("date", ""),
            }
        )

    return {
        "id": str(patchset.get("id")),
        "title": patchset.get("subject", ""),
        "description": description,
        "author": author,
        "state": state,
        "commits": commits,
        "comments": comments,
        "raw_status": status,
        "version": patchset.get("version"),
    }
