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
"""`security-management issue-import-via-forwarder …` — reads files, prints JSON, runs nothing.

The relay message, its sender and any extracted credit are attacker-controlled
and reach a command only in files the agent wrote with its Write tool.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from security_management.cli import emit, read_json, read_object, refuse
from security_management.issue_import_via_forwarder import forwarder

FAMILY = "issue-import-via-forwarder"


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="security-issue-import-via-forwarder: preflight, detect, route")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("preflight", help="Step 0: enabled adapters installed, message well-formed")
    p.add_argument("--forwarders", required=True, help="JSON: project.md forwarders block")
    p.add_argument("--message", required=True, help="JSON: from, date, body of the in-hand message")
    p.add_argument("--framework", required=True, help="<framework>: where tools/forwarder-relay/ lives")

    d = commands.add_parser("detect", help="Step 1: the first enabled adapter whose detect() matches")
    d.add_argument("--message", required=True, help="JSON: from, body")
    d.add_argument("--forwarders", required=True, help="JSON: forwarders block, patterns resolved")
    d.add_argument("--collaborators", help="JSON list: the collaborator logins / addresses from Step 0")

    for name, help_text in (
        ("credit-kind", "Step 2: tool / service / human for the extracted credit (bot/AI policy)"),
        ("first-name", "Step 3: the salutation first name of a handle or display name"),
    ):
        c = commands.add_parser(name, help=help_text)
        c.add_argument("--input", required=True, help="JSON: name (credit-kind adds kind_hints)")

    r = commands.add_parser("route", help="Step 3: recipients, addressing block, question mode, suppression")
    r.add_argument("--mode", required=True, choices=forwarder.MODES)
    r.add_argument(
        "--milestone",
        choices=sorted(forwarder.RELAY | forwarder.OUTSIDE_POLICY | forwarder.NEGATIVE_SPACE),
        help="the milestone kind the draft is for; required in sync mode",
    )
    r.add_argument("--adapter", required=True, help="JSON: the matched adapter's forwarders.<name> block")


def dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command == "preflight":
        forwarders = read_object(args.forwarders)
        result = forwarder.preflight(
            forwarders.get("enabled") or [],
            forwarder.installed(Path(args.framework)),
            read_object(args.message),
        )
        emit(result)
        return 0 if result["outcome"] != "abort" else 2
    if command == "detect":
        collaborators = read_json(args.collaborators) if args.collaborators else []
        emit(forwarder.detect(read_object(args.message), read_object(args.forwarders), collaborators))
        return 0
    if command == "route":
        emit(forwarder.route(args.mode, args.milestone, read_object(args.adapter)))
        return 0
    data = read_object(args.input)
    if command == "credit-kind":
        emit(forwarder.credit_kind(str(data.get("name") or ""), data.get("kind_hints")))
    elif command == "first-name":
        emit(forwarder.first_name(str(data.get("name") or "")))
    else:
        return refuse(f"unknown command {command}")
    return 0
