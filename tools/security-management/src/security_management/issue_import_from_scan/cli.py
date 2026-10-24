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
"""`security-management issue-import-from-scan …` — reads files, prints JSON, runs nothing.

Scan text (titles, evidence, the operator-facing report) is attacker-influenced
and reaches a command only in files the agent wrote with its Write tool.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from security_management.cli import emit, read_json, read_object
from security_management.issue_import_from_scan import oss_scanner, scan

FAMILY = "issue-import-from-scan"


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="security-issue-import-from-scan: bucket rules, report, decision, scrub"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    e = commands.add_parser(
        "parse-email", help="Step A: split an Anthropic OSS Scanner disclosure email into a scan folder"
    )
    e.add_argument(
        "--source", required=True, help="the email: an .eml file, its plain-text body, or a saved Gmail JSON"
    )
    e.add_argument("--out-dir", required=True, help="the scan folder to write (index.json + evidence/)")
    e.add_argument("--archive-dir", help="an operator-decrypted findings archive, to link each REPORT.md")
    e.add_argument(
        "--attachments-dir", help="save the .eml's attachments here (byte-exact; never decrypted or opened)"
    )

    b = commands.add_parser("bucket-action", help="Step C: what a disposition bucket allows")
    b.add_argument("--bucket", required=True, help=f"one of {', '.join(scan.BUCKETS)}")

    r = commands.add_parser("render-report", help="Step D: the per-scan report and the cross-scan analysis")
    r.add_argument(
        "--findings", required=True, help="JSON: scans[] of {name, findings[]} or one findings[] list"
    )
    r.add_argument(
        "--buckets", required=True, help="JSON: {finding id: {bucket, grounding}} (per scan: {scan: {...}})"
    )
    r.add_argument("--title", default="Scan triage report")

    d = commands.add_parser("parse-decision", help="Step E: the operator's reply as an action plan")
    d.add_argument("--input", required=True, help="JSON: reply, findings[] of {n, bucket}")

    s = commands.add_parser("scrub", help="Step F: what a public report must not carry (never rewrites)")
    s.add_argument("--text", required=True, help="the report file")
    s.add_argument("--tracker", required=True, help="<tracker>")
    s.add_argument("--allowed-cves", help="JSON list: CVE IDs already public")


def _scans(findings: Any, buckets: Any) -> list[dict[str, Any]]:
    scans = findings.get("scans") if isinstance(findings, dict) else [{"name": "scan", "findings": findings}]
    out = []
    for entry in scans or []:
        name = str(entry.get("name") or "scan")
        decided = buckets.get(name, buckets) if isinstance(buckets, dict) else {}
        merged = []
        for f in entry.get("findings") or []:
            choice = decided.get(str(f.get("id"))) or {}
            if not choice.get("bucket"):
                raise ValueError(f"finding {f.get('id')!r} in {name} has no bucket")
            merged.append({**f, **choice})
        out.append({"name": name, "findings": merged})
    return out


def dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command == "parse-email":
        body, meta = oss_scanner.load_body(Path(args.source))
        parsed = oss_scanner.parse(body)
        if args.archive_dir:
            oss_scanner.attach_archive(parsed, Path(args.archive_dir))
        summary = oss_scanner.materialise(parsed, meta, Path(args.out_dir))
        if args.attachments_dir:
            summary["attachments"] = oss_scanner.save_attachments(
                Path(args.source), Path(args.attachments_dir)
            )
        emit(summary)
    elif command == "bucket-action":
        emit(scan.bucket_action(args.bucket))
    elif command == "render-report":
        emit(scan.render_report(_scans(read_json(args.findings), read_json(args.buckets)), args.title))
    elif command == "parse-decision":
        data = read_object(args.input)
        emit(scan.parse_decision(str(data.get("reply") or ""), data.get("findings") or []))
    else:
        allowed = read_json(args.allowed_cves) if args.allowed_cves else []
        emit(scan.scrub(Path(args.text).read_text(encoding="utf-8"), args.tracker, allowed))
    return 0
