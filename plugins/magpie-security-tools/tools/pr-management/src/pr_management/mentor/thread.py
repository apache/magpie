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
"""Read one saved thread and decide, deterministically, whether the skill may draft.

Inputs are `vetted-op-read --save` outputs:

* an issue: `repo-issue-view <N>` (carries its comments);
* a PR: `pr-view-with-body <N>` plus `pr-comments <N>` (the REST list).

Decision order, first match wins: a missing config value aborts; the four
hand-off triggers in the order 4 → 3 → 1 → 2; a maintainer already engaged
exits silently; otherwise the skill may pick an intervention, which stays the
agent's call.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..model import parse_time
from ..people import Maintainers, is_bot
from .config import MentoringConfig

#: Trigger 4 — the contributor asks for a human.
WANTS_HUMAN = (
    "can a maintainer",
    "can someone from the team",
    "is anyone there",
    "can a human",
    "can a real person",
    "a real person",
    "talk to a human",
    "speak to a maintainer",
)

#: Trigger 2 — the contributor disagrees with the answer to a why-question.
PUSHBACK = (
    "i don't think that applies",
    "i don't think that policy",
    "i do not think that applies",
    "but in my case",
    "doesn't make sense",
    "does not make sense",
    "that doesn't apply",
    "that does not apply",
    "i disagree",
)

#: What the why-question template (template 4) says, so its answer is recognised.
WHY_ANSWER_SIGNATURES = ("that's covered here:", "a maintainer will weigh in")

#: The comments read beyond `max_agent_turns`: older context is not the audience.
EXTRA_CONTEXT = 5


@dataclass(frozen=True)
class Message:
    author: str
    association: str
    created: dt.datetime | None
    body: str


@dataclass
class Thread:
    kind: str
    number: int
    title: str
    author: str
    body: str
    state: str
    messages: list[Message]

    @property
    def resolved(self) -> bool:
        return self.state.upper() in ("CLOSED", "MERGED")


def _comment(node: dict[str, Any]) -> Message:
    author = (node.get("author") or node.get("user") or {}).get("login") or "ghost"
    return Message(
        author=str(author),
        association=str(node.get("authorAssociation") or node.get("author_association") or "NONE").upper(),
        created=parse_time(node.get("createdAt") or node.get("created_at")),
        body=str(node.get("body") or ""),
    )


def load(kind: str, number: int, view: Path, comments: Path | None) -> Thread:
    data = json.loads(view.read_text(encoding="utf-8"))
    nodes: list[dict[str, Any]] = list(data.get("comments") or [])
    if comments is not None:
        document = json.loads(comments.read_text(encoding="utf-8"))
        pages = document if isinstance(document, list) else [document]
        for page in pages:
            nodes.extend(page if isinstance(page, list) else [page])
    messages = sorted(
        (_comment(n) for n in nodes if n),
        key=lambda m: m.created or dt.datetime.min.replace(tzinfo=dt.UTC),
    )
    return Thread(
        kind=kind,
        number=number,
        title=str(data.get("title") or ""),
        author=str((data.get("author") or {}).get("login") or "ghost"),
        body=str(data.get("body") or ""),
        state=str(data.get("state") or "OPEN"),
        messages=messages,
    )


def _contains(text: str, phrases: tuple[str, ...] | list[str]) -> str | None:
    lowered = re.sub(r"\s+", " ", text.lower()).replace("\u2019", "'")
    for phrase in phrases:
        if phrase in lowered:
            return phrase
    return None


def out_of_scope(text: str, cfg: MentoringConfig) -> dict[str, str] | None:
    """The first out-of-scope topic whose keyword starts a word in `text`."""
    lowered = text.lower()
    for topic, words in cfg.keywords().items():
        for word in words:
            if re.search(r"(?<![a-z0-9])" + re.escape(word), lowered):
                return {"topic": topic, "keyword": word}
    return None


def assess(thread: Thread, cfg: MentoringConfig, viewer: str, people: Maintainers) -> dict[str, Any]:
    """The pre-draft decision for one thread."""
    result: dict[str, Any] = {
        "thread": {
            "kind": thread.kind,
            "number": thread.number,
            "title": thread.title,
            "author": thread.author,
        },
    }
    if cfg.missing:
        result.update(
            outcome="config_error",
            missing=cfg.missing,
            reason="mentoring-config.md is missing required values; copy the template and fill them in",
        )
        return result
    turns = cfg.max_agent_turns or 2
    window = thread.messages[-(turns + EXTRA_CONTEXT) :]
    agent = [m for m in thread.messages if m.author.lower() == viewer.lower()]
    humans = [m for m in window if m.author.lower() != viewer.lower() and not is_bot(m.author)]
    contributor = [m for m in humans if not people.is_maintainer(m.author, m.association)]
    latest = contributor[-1] if contributor else None
    latest_is_contributor = bool(window) and latest is not None and window[-1] is latest
    result["agent_comments"] = len(agent)
    result["max_agent_turns"] = turns

    trigger: dict[str, Any] | None = None
    if latest_is_contributor and latest is not None:
        hit = _contains(latest.body, WANTS_HUMAN)
        if hit:
            trigger = {"trigger": 4, "matched": hit}
        if trigger is None:
            scope = out_of_scope(latest.body, cfg)
            if scope:
                trigger = {"trigger": 3, **scope}
    if trigger is None and not agent:
        scope = out_of_scope(" ".join([thread.title, *(m.body for m in window)]), cfg)
        if scope:
            trigger = {"trigger": 3, **scope}
    if trigger is None and len(agent) >= turns and not thread.resolved:
        trigger = {"trigger": 1, "matched": f"{len(agent)} of {turns} agent turns used"}
    if trigger is None and latest_is_contributor and latest is not None:
        answered = [m for m in agent if _contains(m.body, WHY_ANSWER_SIGNATURES)]
        if answered and answered[-1].created and latest.created and latest.created > answered[-1].created:
            hit = _contains(latest.body, PUSHBACK)
            if hit:
                trigger = {"trigger": 2, "matched": hit}
    if trigger is not None:
        result.update(outcome="handoff", handoff=trigger)
        return result

    recent = thread.messages[-turns:] if turns else []
    engaged = [
        m.author
        for m in recent
        if m.author.lower() != viewer.lower() and people.is_maintainer(m.author, m.association)
    ]
    if engaged:
        result.update(outcome="maintainer_engaged", maintainers=sorted(set(engaged)))
        return result
    result.update(
        outcome="draft",
        pointers=[{"trigger": p.trigger, "label": p.label, "url": p.url} for p in cfg.pointers],
        unresolved_maintainers=sorted(people.unresolved),
    )
    return result
