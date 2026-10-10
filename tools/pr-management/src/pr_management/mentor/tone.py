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
"""The mentoring tone checks that are a phrase list or a count, run on a draft.

Rules run in their documented order and the first failure stops the run, as
`tone-checks.md` prescribes; every failure is still listed for the revision.
Rules 2 (the paraphrase half), 11 (beyond the known meta openers) and 13 are
judgement: they are returned under `judgement` for the agent to apply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

FOOTER_TOKEN = "<ai_attribution_footer>"

RULES: dict[int, tuple[str, str]] = {
    1: ("hard", "No praise without specificity."),
    2: ("hard", "No restating the contributor's message."),
    3: ("hard", "No AI self-reference outside the footer."),
    4: ("hard", "No speaking for the maintainer."),
    5: ("hard", "No hedging."),
    6: ("hard", "One ask per comment."),
    7: ("hard", "Footer present and verbatim."),
    8: ("hard", "Author tagged once."),
    9: ("hard", "No paraphrased docs."),
    10: ("hard", "No predictions about review outcome."),
    11: ("soft", "First line states the action."),
    12: ("soft", "Comment is short."),
    13: ("soft", "Plain English."),
    14: ("soft", "No exclamation marks outside the footer."),
}

PHRASES: dict[int, tuple[str, ...]] = {
    1: ("great question", "thanks for the contribution", "awesome", "amazing", "fantastic", "love this"),
    2: ("so what you're saying is", "if i understand correctly", "you mentioned that"),
    3: (
        "as an ai",
        "i'm an ai",
        "i cannot",
        "as a language model",
        "i was trained",
        "my training",
        "i don't have access to",
    ),
    4: ("the maintainers will probably", "the maintainers want", "the team would prefer"),
    5: ("it seems like", "perhaps", "i think maybe", "this might possibly", "i'm not sure but"),
    10: (
        "looks good",
        "this should be approved",
        "this will probably be merged",
        "i don't think this will land",
    ),
    11: ("i'm reaching out", "i am reaching out", "i wanted to", "just a quick note", "i noticed that"),
}

SENTENCE_CAP = 6
QUOTE_CAP = 2

_FENCE = re.compile(r"```.*?```", flags=re.DOTALL)
_INLINE = re.compile(r"`[^`]*`")


@dataclass
class Failure:
    rule: int
    severity: str
    offending_text: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "summary": RULES[self.rule][1],
            "offending_text": self.offending_text,
        }


def _norm(text: str) -> str:
    return text.replace("\u2019", "'")


def _split_footer(draft: str, footer: str | None) -> tuple[str, bool, str]:
    """The body before the footer, whether the draft ends with the footer, and what follows it."""
    text = draft.rstrip()
    for candidate in [footer.strip() if footer else None, FOOTER_TOKEN]:
        if candidate and candidate in text:
            index = text.rindex(candidate)
            tail = text[index + len(candidate) :].strip()
            return text[:index], tail == "", tail
    return text, False, ""


def _sentence_with(body: str, phrase: str) -> str:
    flat = re.sub(r"\s+", " ", body)
    for sentence in re.split(r"(?<=[.!?])\s+", flat):
        if phrase in _norm(sentence.lower()):
            return sentence.strip()
    return phrase


def _prose(body: str) -> str:
    return _INLINE.sub("", _FENCE.sub("", body))


def sentences(body: str) -> list[str]:
    prose = "\n".join(ln for ln in _prose(body).splitlines() if not ln.lstrip().startswith(">"))
    flat = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", re.sub(r"\s+", " ", prose)).strip()
    flat = re.sub(r"^@\S+\s*[—-]\s*", "", flat)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z@`\[])", flat) if p.strip()]
    return [p for p in parts if re.search(r"[A-Za-z]", p)]


def check(draft: str, *, author: str | None, footer: str | None) -> dict[str, Any]:
    body, ends_with_footer, tail = _split_footer(draft, footer)
    lowered = _norm(body.lower())
    failures: list[Failure] = []

    for rule in (1, 2, 3, 4, 5):
        for phrase in PHRASES[rule]:
            if phrase in lowered:
                failures.append(Failure(rule, RULES[rule][0], _sentence_with(body, phrase)))
                break
    questions = _prose(body).count("?")
    if questions > 1:
        failures.append(Failure(6, "hard", f"{questions} questions"))
    if not ends_with_footer:
        failures.append(
            Failure(7, "hard", f"text after the footer: {tail[:80]!r}" if tail else "footer missing")
        )
    if author is not None:
        tagged = len(
            re.findall(rf"(?<![\w`])@{re.escape(author)}\b", _INLINE.sub("", body), flags=re.IGNORECASE)
        )
        if tagged != 1:
            failures.append(Failure(8, "hard", f"@{author} appears {tagged} times"))
    run: list[str] = []
    for line in [*body.splitlines(), ""]:
        if line.lstrip().startswith(">"):
            run.append(line)
            continue
        if len(run) > QUOTE_CAP:
            failures.append(Failure(9, "hard", "\n".join(run)))
            break
        run = []
    for phrase in PHRASES[10]:
        if phrase in lowered:
            failures.append(Failure(10, "hard", _sentence_with(body, phrase)))
            break
    found = sentences(body)
    if found:
        first = _norm(found[0].lower())
        if any(first.startswith(p) or p in first[:60] for p in PHRASES[11]):
            failures.append(Failure(11, "soft", found[0]))
    if len(found) > SENTENCE_CAP:
        failures.append(Failure(12, "soft", f"{len(found)} sentences (cap {SENTENCE_CAP})"))
    if "!" in _prose(body):
        failures.append(Failure(14, "soft", _sentence_with(body, "!")))

    failures.sort(key=lambda f: f.rule)
    first_failure = failures[0] if failures else None
    if first_failure is None:
        result = "pass"
    else:
        result = "hard_fail" if first_failure.severity == "hard" else "soft_fail"
    return {
        "docs": sorted({f"classifications/tone-rule-{f.rule}.md" for f in failures}),
        "result": result,
        "rule": first_failure.rule if first_failure else None,
        "offending_text": first_failure.offending_text if first_failure else None,
        "failures": [f.as_dict() for f in failures],
        "judgement": [
            {"rule": 2, "check": "no sentence paraphrases the contributor's most recent message"},
            {"rule": 11, "check": "the first sentence is a question or imperative aimed at the contributor"},
            {"rule": 13, "check": "no project-internal term outside a linked label"},
        ],
    }
