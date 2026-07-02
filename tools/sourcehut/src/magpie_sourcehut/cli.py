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

"""Command line interface for magpie-sourcehut."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from magpie_sourcehut.builds import get_job
from magpie_sourcehut.client import SourceHutError, query_graphql
from magpie_sourcehut.lists import get_patchset, list_patchsets, map_patchset_to_pr
from magpie_sourcehut.repo import get_repo
from magpie_sourcehut.todo import (
    get_ticket,
    label_ticket,
    submit_comment,
    submit_ticket,
    unlabel_ticket,
    update_ticket_status,
)


def _print_json(data: dict | list) -> None:
    """Helper to pretty print JSON data to stdout."""
    print(json.dumps(data, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magpie-sourcehut",
        description="SourceHut forge bridge capability wrapper.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # raw graphql query
    p_graphql = subparsers.add_parser("graphql", help="Run a raw GraphQL query.")
    p_graphql.add_argument("service", help="sr.ht service subdomain (e.g. todo, lists, builds).")
    p_graphql.add_argument("query", help="GraphQL query/mutation string.")
    p_graphql.add_argument("--variables", help="Optional query variables as a JSON string.")

    # tickets
    p_ticket = subparsers.add_parser("ticket", help="Interact with todo.sr.ht tickets.")
    t_sub = p_ticket.add_subparsers(dest="action", required=True)

    p_t_get = t_sub.add_parser("get", help="Get details of a ticket.")
    p_t_get.add_argument("owner", help="Owner of the tracker.")
    p_t_get.add_argument("name", help="Name of the tracker.")
    p_t_get.add_argument("id", type=int, help="Ticket ID.")

    p_t_create = t_sub.add_parser("create", help="Create a ticket.")
    p_t_create.add_argument("owner", help="Owner of the tracker.")
    p_t_create.add_argument("name", help="Name of the tracker.")
    p_t_create.add_argument("--title", required=True, help="Ticket title.")
    p_t_create.add_argument("--body", required=True, help="Ticket description/body.")

    p_t_comment = t_sub.add_parser("comment", help="Comment on a ticket.")
    p_t_comment.add_argument("owner", help="Owner of the tracker.")
    p_t_comment.add_argument("name", help="Name of the tracker.")
    p_t_comment.add_argument("id", type=int, help="Ticket ID.")
    p_t_comment.add_argument("--body", required=True, help="Comment body.")

    p_t_label = t_sub.add_parser("label", help="Manage ticket labels.")
    p_t_label.add_argument("owner", help="Owner of the tracker.")
    p_t_label.add_argument("name", help="Name of the tracker.")
    p_t_label.add_argument("id", type=int, help="Ticket ID.")
    p_t_label.add_argument("--add", type=int, help="Label ID to add.")
    p_t_label.add_argument("--remove", type=int, help="Label ID to remove.")

    p_t_close = t_sub.add_parser("close", help="Close/resolve a ticket.")
    p_t_close.add_argument("owner", help="Owner of the tracker.")
    p_t_close.add_argument("name", help="Name of the tracker.")
    p_t_close.add_argument("id", type=int, help="Ticket ID.")
    p_t_close.add_argument("--status", default="RESOLVED", help="Status (e.g. RESOLVED, WONTFIX).")
    p_t_close.add_argument("--resolution", help="Optional ticket resolution.")

    # patchsets
    p_patch = subparsers.add_parser("patchset", help="Interact with lists.sr.ht patchsets.")
    pa_sub = p_patch.add_subparsers(dest="action", required=True)

    p_p_get = pa_sub.add_parser("get", help="Get details of a patchset.")
    p_p_get.add_argument("owner", help="Owner of the mailing list.")
    p_p_get.add_argument("list_name", help="Name of the mailing list.")
    p_p_get.add_argument("id", type=int, help="Patchset ID.")

    p_p_list = pa_sub.add_parser("list", help="List patchsets on a mailing list.")
    p_p_list.add_argument("owner", help="Owner of the mailing list.")
    p_p_list.add_argument("list_name", help="Name of the mailing list.")

    p_p_map = pa_sub.add_parser("pr-map", help="Map a patchset to a uniform PR abstraction.")
    p_p_map.add_argument("owner", help="Owner of the mailing list.")
    p_p_map.add_argument("list_name", help="Name of the mailing list.")
    p_p_map.add_argument("id", type=int, help="Patchset ID.")

    # builds
    p_build = subparsers.add_parser("build", help="Interact with builds.sr.ht.")
    b_sub = p_build.add_subparsers(dest="action", required=True)

    p_b_get = b_sub.add_parser("get", help="Get build status.")
    p_b_get.add_argument("id", type=int, help="Build job ID.")

    # repo
    p_repo = subparsers.add_parser("repo", help="Interact with git/hg repositories.")
    r_sub = p_repo.add_subparsers(dest="action", required=True)

    p_r_get = r_sub.add_parser("get", help="Get repository details.")
    p_r_get.add_argument("service", choices=["git", "hg"], help="VCS type ('git' or 'hg').")
    p_r_get.add_argument("owner", help="Owner of the repository.")
    p_r_get.add_argument("name", help="Name of the repository.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)

    try:
        if ns.subcommand == "graphql":
            vars_dict = None
            if ns.variables:
                vars_dict = json.loads(ns.variables)
            res = query_graphql(ns.service, ns.query, vars_dict)
            _print_json(res)

        elif ns.subcommand == "ticket":
            if ns.action == "get":
                res = get_ticket(ns.owner, ns.name, ns.id)
                _print_json(res)
            elif ns.action == "create":
                res = submit_ticket(ns.owner, ns.name, ns.title, ns.body)
                _print_json(res)
            elif ns.action == "comment":
                res = submit_comment(ns.owner, ns.name, ns.id, ns.body)
                _print_json(res)
            elif ns.action == "label":
                if not ns.add and not ns.remove:
                    parser.error("At least one of --add or --remove must be specified")
                if ns.add:
                    label_ticket(ns.owner, ns.name, ns.id, ns.add)
                if ns.remove:
                    unlabel_ticket(ns.owner, ns.name, ns.id, ns.remove)
                # Fetch and print updated ticket details
                res = get_ticket(ns.owner, ns.name, ns.id)
                _print_json(res)
            elif ns.action == "close":
                res = update_ticket_status(ns.owner, ns.name, ns.id, ns.status, ns.resolution)
                _print_json(res)

        elif ns.subcommand == "patchset":
            if ns.action == "get":
                res = get_patchset(ns.owner, ns.list_name, ns.id)
                _print_json(res)
            elif ns.action == "list":
                patchsets = list_patchsets(ns.owner, ns.list_name)
                _print_json(patchsets)
            elif ns.action == "pr-map":
                raw = get_patchset(ns.owner, ns.list_name, ns.id)
                res = map_patchset_to_pr(raw)
                _print_json(res)

        elif ns.subcommand == "build":
            if ns.action == "get":
                res = get_job(ns.id)
                _print_json(res)

        elif ns.subcommand == "repo":
            if ns.action == "get":
                res = get_repo(ns.service, ns.owner, ns.name)
                _print_json(res)

        return 0
    except (SourceHutError, json.JSONDecodeError) as e:
        print(f"magpie-sourcehut error: {e}", file=sys.stderr)
        return 2
