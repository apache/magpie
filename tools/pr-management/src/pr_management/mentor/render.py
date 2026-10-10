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
"""Render a mentoring comment or the hand-off from its template, then tone-check it.

The four intervention templates and the hand-off ship as package data. The
renderer refuses rather than emitting a half-rendered body: a missing pointer
label or URL, a missing footer, or a placeholder left over is an error.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any

from . import tone
from .config import MentoringConfig

INTERVENTIONS = ("missing-repro", "missing-version", "convention-pointer", "why-question")
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_PLACEHOLDER = re.compile(r"<[a-z_]+>")


def _template(name: str) -> str:
    text = (
        resources.files("pr_management.mentor")
        .joinpath("templates", f"{name}.tmpl")
        .read_text(encoding="utf-8")
    )
    return re.sub(r"\A<!--.*?-->\n*", "", text, flags=re.DOTALL)


def _link_numbers(text: str, upstream: str | None) -> str:
    if not upstream:
        return text
    return re.sub(
        r"(?<![\w\[/#])#(\d+)\b(?!\])",
        lambda m: f"[#{m.group(1)}](https://github.com/{upstream}/issues/{m.group(1)})",
        text,
    )


def _silence_mentions(text: str, allowed: set[str]) -> str:
    """Backtick every @-mention except the allowed ones, so a body never notifies anyone else."""

    def sub(m: re.Match[str]) -> str:
        return m.group(0) if m.group(1).lower() in allowed else f"`@{m.group(1)}`"

    return re.sub(r"(?<![\w`])@([A-Za-z0-9][A-Za-z0-9-]{0,38}(?:/[A-Za-z0-9_.-]+)?)", sub, text)


def render(
    cfg: MentoringConfig,
    *,
    kind: str,
    author: str | None,
    pointer: str | None = None,
    open_question: str | None = None,
    upstream: str | None = None,
    out: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    if cfg.footer is None:
        errors.append("ai_attribution_footer is not configured")
    if kind == "hand-off":
        handle = cfg.maintainer_team_handle or ""
        question = " ".join((open_question or "").split())
        if not question:
            errors.append("the hand-off needs a one-line open question")
        if not handle.startswith("@"):
            errors.append("maintainer_team_handle must be an @org/team handle")
        if errors:
            return {"ok": False, "errors": errors}
        question = _silence_mentions(_link_numbers(question, upstream), set())
        body = (
            _template("hand-off")
            .replace("<maintainer_team_handle>", handle)
            .replace("<open_question>", question)
            .replace("<ai_attribution_footer>", cfg.footer or "")
        )
        mentions = [handle]
    else:
        if kind not in INTERVENTIONS:
            return {"ok": False, "errors": [f"unknown intervention {kind!r}; one of {list(INTERVENTIONS)}"]}
        if author is None or not _LOGIN.match(author):
            errors.append(f"author {author!r} is not a GitHub login")
        row = next((p for p in cfg.pointers if pointer and p.trigger.lower() == pointer.lower()), None)
        if row is None:
            errors.append(
                f"no convention_pointers row named {pointer!r}; rows: {[p.trigger for p in cfg.pointers]}"
            )
        elif not (row.url and row.label):
            errors.append(f"the convention_pointers row {row.trigger!r} has no link or label")
        if errors or row is None or author is None:
            return {"ok": False, "errors": errors}
        body = (
            _template(kind)
            .replace("<author>", author)
            .replace("<doc_label>", row.label or "")
            .replace("<doc_url>", row.url or "")
            .replace("<ai_attribution_footer>", cfg.footer or "")
        )
        mentions = [f"@{author}"]
    leftover = sorted(set(_PLACEHOLDER.findall(body)))
    if leftover:
        return {"ok": False, "errors": [f"unresolved placeholder(s) {leftover}"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    checked = tone.check(body, author=author if kind != "hand-off" else None, footer=cfg.footer)
    if kind == "hand-off":
        # The hand-off tags the team, not the author; rule 8 does not apply.
        checked["failures"] = [f for f in checked["failures"] if f["rule"] != 8]
    return {
        "ok": True,
        "kind": kind,
        "body_file": str(out),
        "mentions": mentions,
        "tone": checked,
        "preview": body,
    }
