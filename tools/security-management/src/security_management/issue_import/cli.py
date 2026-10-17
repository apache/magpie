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
"""`security-management issue-import …` — every command reads files, prints JSON and runs nothing.

Untrusted report text (bodies, subjects, sender names) reaches a command only
through a file the agent wrote with its Write tool, never through argv.
Nothing here posts, drafts, searches, or decides a classification: the
agent keeps classification, field extraction, PII identification, fuzzy
duplicates, canned-response choice and injection flagging.
"""

from __future__ import annotations

import argparse
from typing import Any

from security_management.cli import emit, read_json, read_object, refuse
from security_management.issue_import import ack, dedup, governance, prefilter, recap, relay, replies
from security_management.shared import body, grammar, keyword, refs, reuse, rollup, titles

FAMILY = "issue-import"


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="security-issue-import: pre-filter, dedup, render, parse, recap")
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str, *flags: tuple[str, str]) -> None:
        p = commands.add_parser(name, help=help_text)
        for flag, flag_help in flags:
            p.add_argument(flag, required=True, help=flag_help)

    command(
        "governance",
        "Step 0 item 5: disclosure_governance keys, ASF defaults when absent",
        ("--config", "path of <project-config>/security-intake-config.md (a missing file is fine)"),
    )
    command(
        "prefilter",
        "Step 1 pre-filter: keep/drop each thread by subject and sender",
        ("--threads", "JSON: upstream, security_list, cve_tool_senders, named_thread_id, threads[]"),
    )
    command(
        "dedup-queries",
        "Step 2: OR'd threadId batches of at most 6",
        ("--thread-ids", "JSON list of threadIds"),
    )
    commands.choices["dedup-queries"].add_argument(
        "--tracker", help="<tracker>: also print each search command"
    )
    command(
        "dedup-attribute",
        "Step 2: attribute search hits to threadIds; flags a truncated (100-hit) batch",
        ("--thread-ids", "JSON list of the batch's threadIds"),
        ("--hits", "the batch's `gh search issues --json number,title,state,url,body` output"),
    )
    command(
        "relay-prescreen",
        "Step 3: whether the via-forwarder sub-skill can match this root message",
        ("--message", "JSON: from, body (the root message)"),
        ("--forwarders", "JSON: project.md forwarders block, patterns resolved"),
    )
    keyword_p = commands.add_parser("keyword", help="Steps 2a/2b/2c: allowlist-clean search keywords")
    keyword_p.add_argument("--file", required=True, help="file the Write tool put the raw keywords in")
    keyword_p.add_argument("--kind", default="keywords", choices=sorted(keyword.ALLOWLISTS))
    command(
        "title",
        "Step 4: strip mail-subject prefixes (the paraphrase stays the model's)",
        ("--input", "JSON: subject"),
    )
    command("linkify", "link every bare #NNN / owner/repo#NNN", ("--input", "JSON: text, repo, kind"))
    command(
        "render-body",
        "Step 7.1: render the tracker body, the description as an inert block",
        ("--input", "JSON: fields{role: value}, body_fields, callout"),
    )
    command("render-rollup", "Step 7.5: the import rollup entry", ("--input", "JSON: see the README"))
    command("render-ledger", "Step 7 non-import 4: the rejection v1 record", ("--input", "JSON"))
    command("render-fix-public-reply", "Step 5: the fix-already-public reply", ("--input", "JSON"))
    command("ack-decision", "Step 7.4: receipt draft or not, and what to record", ("--input", "JSON"))
    command("render-recap", "Step 8: the recap", ("--state", "JSON: what Step 7 recorded"))
    command("parse-reply", "Step 6: the confirmation reply as an action plan", ("--input", "JSON"))


def _render_body(data: dict[str, Any]) -> dict[str, Any]:
    fields = dict(data.get("fields") or {})
    cleaned = body.inert_block(str(fields.get("issue_description") or ""))
    if not cleaned["ok"]:
        return {
            "ok": False,
            "refused": f"the report body is malformed ({cleaned['indicator']}); it is not rendered",
            "malformed_indicator": cleaned["indicator"],
        }
    fields["issue_description"] = cleaned["text"]
    text = body.render(fields, data.get("body_fields"), callout=bool(data.get("callout")))
    problem = body.verify(text, data.get("body_fields"))
    if problem is not None:
        return {"ok": False, "refused": f"{problem}; it is not rendered", "malformed_indicator": None}
    expected = list(body.headings(data.get("body_fields")).values())
    parsed = reuse.fields(text)
    credit = str(fields.get("reporter_credit") or "").strip()
    return {
        "ok": True,
        "text": text,
        "sanitised": True,
        "sanitised_fields": body.sanitised_fields(fields),
        "escaped_lines": cleaned["escaped_lines"],
        "malformed_indicator": None,
        "fields": parsed,
        "fields_ok": parsed == expected,
        "extra_fields": [f for f in parsed if f not in expected],
        "reporter_credit_is_bot": reuse.is_bot_credit(credit) if credit else False,
        "bare_refs": refs.bare_refs(text),
    }


def dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command == "governance":
        emit(governance.resolve(args.config))
        return 0
    if command == "prefilter":
        emit(prefilter.classify(read_object(args.threads)))
        return 0
    if command in ("dedup-queries", "dedup-attribute"):
        result = (
            dedup.queries(read_json(args.thread_ids), args.tracker)
            if command == "dedup-queries"
            else dedup.attribute(read_json(args.thread_ids), read_json(args.hits))
        )
        if not result["ok"]:
            return refuse(result["refused"], rejected_ids=result["rejected_ids"])
        emit(result)
        return 0
    if command == "relay-prescreen":
        emit(relay.prescreen(read_object(args.message), read_object(args.forwarders)))
        return 0
    if command == "keyword":
        cleaned = keyword.clean_file(args.file, args.kind)
        emit({"cleaned": cleaned, "empty": not cleaned})
        return 0
    if command == "render-recap":
        emit(recap.render(read_object(args.state)))
        return 0

    data = read_object(args.input)
    if command == "title":
        emit({"title": titles.strip_mail_prefixes(str(data["subject"]))})
        return 0
    if command == "linkify":
        text = str(data["text"])
        emit(
            {
                "bare_refs": refs.bare_refs(text),
                "text": refs.linkify(text, str(data["repo"]), str(data.get("kind") or "issues")),
            }
        )
        return 0
    if command == "render-body":
        rendered = _render_body(data)
        if not rendered["ok"]:
            return refuse(str(rendered["refused"]), malformed_indicator=rendered["malformed_indicator"])
        emit(rendered)
        return 0
    if command == "ack-decision":
        emit(ack.decide(data))
        return 0
    if command == "parse-reply":
        forms = data.get("allowed_forms") or grammar.FORMS
        emit(grammar.parse_reply(str(data.get("reply") or ""), data.get("candidates") or [], forms))
        return 0
    renderers = {
        "render-rollup": rollup.import_mail,
        "render-ledger": replies.ledger,
        "render-fix-public-reply": replies.fix_public_reply,
    }
    result = renderers[command](data)
    if not result.get("ok"):
        return refuse(str(result.get("refused")))
    emit(result)
    return 0
