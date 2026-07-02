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

"""todo.sr.ht ticket integration."""

from __future__ import annotations

from typing import Any

from magpie_sourcehut.client import query_graphql


def _normalize_owner(owner: str) -> str:
    """Ensure the owner username starts with '~'."""
    if not owner.startswith("~"):
        return f"~{owner}"
    return owner


def get_ticket(owner: str, name: str, ticket_id: int) -> dict[str, Any]:
    """Retrieve ticket details from todo.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    query GetTicket($owner: String!, $name: String!, $id: Int!) {
      tracker(owner: $owner, name: $name) {
        id
        name
        ticket(id: $id) {
          id
          title
          description
          status
          resolution
          labels {
            id
            name
          }
          comments {
            id
            body
            author {
              username
            }
          }
        }
      }
    }
    """
    res = query_graphql("todo", q, {"owner": owner, "name": name, "id": ticket_id})
    tracker = res.get("tracker") or {}
    return tracker.get("ticket") or {}


def submit_ticket(owner: str, name: str, title: str, description: str) -> dict[str, Any]:
    """Submit a new ticket to todo.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    mutation CreateTicket($owner: String!, $name: String!, $input: SubmitTicketInput!) {
      submitTicket(trackerOwner: $owner, trackerName: $name, input: $input) {
        id
        title
        status
      }
    }
    """
    variables = {
        "owner": owner,
        "name": name,
        "input": {
            "title": title,
            "description": description,
        },
    }
    res = query_graphql("todo", q, variables)
    return res.get("submitTicket") or {}


def submit_comment(owner: str, name: str, ticket_id: int, body: str) -> dict[str, Any]:
    """Add a comment to an existing ticket on todo.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    mutation CreateComment($owner: String!, $name: String!, $ticketId: Int!, $input: SubmitCommentInput!) {
      submitComment(trackerOwner: $owner, trackerName: $name, ticketId: $ticketId, input: $input) {
        id
        body
      }
    }
    """
    variables = {
        "owner": owner,
        "name": name,
        "ticketId": ticket_id,
        "input": {
            "body": body,
        },
    }
    res = query_graphql("todo", q, variables)
    return res.get("submitComment") or {}


def label_ticket(owner: str, name: str, ticket_id: int, label_id: int) -> dict[str, Any]:
    """Add a label to a ticket on todo.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    mutation LabelTicket($owner: String!, $name: String!, $ticketId: Int!, $labelId: Int!) {
      labelTicket(trackerOwner: $owner, trackerName: $name, ticketId: $ticketId, labelId: $labelId) {
        id
      }
    }
    """
    variables = {
        "owner": owner,
        "name": name,
        "ticketId": ticket_id,
        "labelId": label_id,
    }
    res = query_graphql("todo", q, variables)
    return res.get("labelTicket") or {}


def unlabel_ticket(owner: str, name: str, ticket_id: int, label_id: int) -> dict[str, Any]:
    """Remove a label from a ticket on todo.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    mutation UnlabelTicket($owner: String!, $name: String!, $ticketId: Int!, $labelId: Int!) {
      unlabelTicket(trackerOwner: $owner, trackerName: $name, ticketId: $ticketId, labelId: $labelId) {
        id
      }
    }
    """
    variables = {
        "owner": owner,
        "name": name,
        "ticketId": ticket_id,
        "labelId": label_id,
    }
    res = query_graphql("todo", q, variables)
    return res.get("unlabelTicket") or {}


def update_ticket_status(
    owner: str, name: str, ticket_id: int, status: str, resolution: str | None = None
) -> dict[str, Any]:
    """Update ticket status (resolve / close) on todo.sr.ht."""
    owner = _normalize_owner(owner)
    q = """
    mutation UpdateStatus($owner: String!, $name: String!, $ticketId: Int!, $status: TicketStatus!, $resolution: TicketResolution) {
      updateTicketStatus(trackerOwner: $owner, trackerName: $name, id: $ticketId, status: $status, resolution: $resolution) {
        id
        status
        resolution
      }
    }
    """
    variables = {
        "owner": owner,
        "name": name,
        "ticketId": ticket_id,
        "status": status,
        "resolution": resolution,
    }
    res = query_graphql("todo", q, variables)
    return res.get("updateTicketStatus") or {}
