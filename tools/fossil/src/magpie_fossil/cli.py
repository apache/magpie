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

"""Command line interface for magpie-fossil."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from magpie_fossil import forum, ticket, wiki
from magpie_fossil.client import FossilError, find_repo_db


def _print_json(data: dict | list) -> None:
    """Helper to pretty print JSON data to stdout."""
    print(json.dumps(data, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magpie-fossil",
        description="Fossil SCM forge and tracker bridge capability wrapper.",
    )
    parser.add_argument(
        "-C", "--cwd", default=".", help="Checkout directory to search for repository database."
    )
    parser.add_argument("-R", "--repository", help="Direct path to the Fossil repository database file.")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # tickets
    p_ticket = subparsers.add_parser("ticket", help="Interact with Fossil tickets.")
    t_sub = p_ticket.add_subparsers(dest="action", required=True)

    t_sub.add_parser("list", help="List all tickets.")

    p_t_get = t_sub.add_parser("get", help="Get details of a ticket.")
    p_t_get.add_argument("uuid", help="Ticket UUID (or prefix).")

    p_t_create = t_sub.add_parser("create", help="Create a ticket.")
    p_t_create.add_argument("--title", required=True, help="Ticket title.")
    p_t_create.add_argument("--body", required=True, help="Ticket description/body.")
    p_t_create.add_argument(
        "--field", action="append", nargs=2, metavar=("NAME", "VALUE"), help="Extra ticket field value pairs."
    )

    p_t_edit = t_sub.add_parser("edit", help="Update ticket fields.")
    p_t_edit.add_argument("uuid", help="Ticket UUID (or prefix).")
    p_t_edit.add_argument(
        "--field",
        action="append",
        nargs=2,
        required=True,
        metavar=("NAME", "VALUE"),
        help="Ticket field value pairs to update.",
    )

    p_t_comment = t_sub.add_parser("comment", help="Comment on a ticket.")
    p_t_comment.add_argument("uuid", help="Ticket UUID (or prefix).")
    p_t_comment.add_argument("--body", required=True, help="Comment body.")

    # wiki
    p_wiki = subparsers.add_parser("wiki", help="Interact with Fossil wiki.")
    w_sub = p_wiki.add_subparsers(dest="action", required=True)

    w_sub.add_parser("list", help="List all wiki page names.")
    p_w_read = w_sub.add_parser("read", help="Read a wiki page.")
    p_w_read.add_argument("name", help="Wiki page name.")

    # forum
    p_forum = subparsers.add_parser("forum", help="Interact with Fossil forums.")
    f_sub = p_forum.add_subparsers(dest="action", required=True)

    f_sub.add_parser("list", help="List all forum threads.")
    p_f_read = f_sub.add_parser("read", help="Read all posts in a forum thread.")
    p_f_read.add_argument("thread_uuid", help="Thread root UUID.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)

    # Resolve repository file path
    repo_path: Path | None = None
    if ns.repository:
        repo_path = Path(ns.repository).resolve()
    else:
        start_dir = Path(ns.cwd).resolve()
        repo_path = find_repo_db(start_dir)

    if not repo_path or not repo_path.exists():
        print(
            "Error: Fossil repository database file not found. "
            "Ensure you are running inside a Fossil checkout or specify the database path with -R/--repository.",
            file=sys.stderr,
        )
        return 1

    res: Any = None
    try:
        if ns.subcommand == "ticket":
            if ns.action == "list":
                res = ticket.list_tickets(repo_path)
                _print_json(res)
            elif ns.action == "get":
                res = ticket.get_ticket(repo_path, ns.uuid)
                _print_json(res)
            elif ns.action == "create":
                fields = dict(ns.field) if ns.field else {}
                uuid = ticket.submit_ticket(repo_path, ns.title, ns.body, fields)
                _print_json({"tkt_uuid": uuid})
            elif ns.action == "edit":
                fields = dict(ns.field)
                uuid = ticket.update_ticket_fields(repo_path, ns.uuid, fields)
                _print_json({"tkt_uuid": uuid})
            elif ns.action == "comment":
                uuid = ticket.submit_comment(repo_path, ns.uuid, ns.body)
                _print_json({"tkt_uuid": uuid})

        elif ns.subcommand == "wiki":
            if ns.action == "list":
                res = wiki.list_wiki(repo_path)
                _print_json(res)
            elif ns.action == "read":
                res = wiki.read_wiki(repo_path, ns.name)
                # Output page content as plain string
                sys.stdout.write(res)

        elif ns.subcommand == "forum":
            if ns.action == "list":
                res = forum.list_forum_threads(repo_path)
                _print_json(res)
            elif ns.action == "read":
                res = forum.read_forum_thread(repo_path, ns.thread_uuid)
                _print_json(res)

    except FossilError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    return 0
