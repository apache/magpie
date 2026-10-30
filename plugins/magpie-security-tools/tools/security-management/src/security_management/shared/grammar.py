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
"""The confirmation-reply grammar of the import skills.

Importable candidates default to import, so the user types only to deviate:

- `all` / `go` / `proceed` / `yes` / `ok` / no reply — import every importable
  candidate; with an explicit go word, the proposed non-import actions are
  confirmed too (`non_import_confirmed`).
- `skip N[, M …]` — reject upfront, no tracker, no draft.
- `N:reject-with-canned <name>` — reject upfront and draft the named canned reply.
- `N:reject-with-public-fix <PR-URL>[, <PR-URL> …]` — reject with the
  fix-already-public reply.
- `N:edit <freeform>` — fold a note into the import.
- `N:title <text>`, `N:reporter <text>`, `N:severity <text>` — override one field.
- `keep <threadId>[, …]` — send a pre-filtered thread back through Steps 2 to 5.
- `cancel` / `none` / `hold off` — nothing is created.

A directive's argument runs to the next directive, a `;` or the end of the
line; `skip` counts as a directive only before a number and `keep` only
before a thread id, so a canned-response name may contain either word. Anything the grammar cannot place — free text, an unknown candidate
number, two deviations for one candidate, a form the caller does not allow —
lands in `ambiguous_tokens`, and every candidate number it mentions in
`ambiguous_items`, which are held back from **every** actionable list: the
agent asks back about those and runs the rest. Dispositions resolve per
candidate: an identical repeat is one action, two different ones (`skip 1`
and `1:reject-with-canned X`, two canned names, two values for one field)
make the candidate ambiguous. Free text that names no candidate cannot be
scoped, so it holds **all** actions until the user clarifies. A go word
counts only in a clause that is nothing but go words: a negation anywhere in
the reply (`not`, `don't`, `no`, `stop`, `wait`, …) confirms nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

FORMS = frozenset(
    {
        "go",
        "skip",
        "reject-with-canned",
        "reject-with-public-fix",
        "edit",
        "title",
        "reporter",
        "severity",
        "keep",
        "cancel",
    }
)
OVERRIDE_FIELDS = ("title", "reporter", "severity")

_GO_WORDS = frozenset({"all", "go", "proceed", "yes", "ok", "okay", "lgtm", "y"})
_NEGATION = re.compile(
    r"\b(?:not|no|never|don'?t|do\s+not|stop|wait|hold|cancel|nope)\b|n't\b", re.IGNORECASE
)
_CANCEL = re.compile(r"^(?:cancel|none|hold off|abort|stop)$")
_DIRECTIVE = re.compile(
    r"(?P<numbered>#?(?P<item>\d+)\s*:\s*(?P<verb>reject-with-canned|reject-with-public-fix|edit|title|reporter|severity)\b:?)"
    r"|(?P<word>\bskip(?=\s+#?\d)|\bkeep(?=\s+[A-Za-z0-9_-]{6,}))",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"#?(\d+)")
_URL = re.compile(r"https?://\S+")
_THREAD_ID = re.compile(r"[A-Za-z0-9_-]+")


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in re.split(r"[;\n]", text) if c.strip()]


def _split_list(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,]+|\band\b", text.strip()) if t]


def _numbers(text: str) -> list[int]:
    return [int(m.group(1)) for m in _NUMBER.finditer(text)]


def _empty(action: str, ambiguous: list[str], held: list[int]) -> dict[str, Any]:
    return {
        "action": action,
        "import_items": [],
        "skip_items": [],
        "reject_with_canned": [],
        "reject_with_public_fix": [],
        "edits": [],
        "overrides": [],
        "keep": [],
        "non_import_confirmed": [],
        "ambiguous_tokens": ambiguous,
        "ambiguous_items": held,
    }


def parse_reply(
    text: str,
    candidates: Sequence[Mapping[str, Any]],
    allowed_forms: Iterable[str] = FORMS,
) -> dict[str, Any]:
    """The action plan for `text` over `candidates` (`{"n": int, "importable": bool}` each)."""
    allowed = frozenset(allowed_forms)
    known = {int(c["n"]): bool(c.get("importable", True)) for c in candidates}
    # Per candidate, the rejection it was given: (kind, argument key) -> payload.
    rejections: dict[int, dict[tuple[str, str], dict[str, Any]]] = {}
    edits: list[dict[str, Any]] = []
    overrides: dict[tuple[int, str], set[str]] = {}
    keep: list[str] = []
    ambiguous: list[str] = []
    unscoped = False
    go = False
    cancel = False

    def reject(item: int, kind: str, key: str, payload: dict[str, Any], token: str) -> None:
        nonlocal unscoped
        if item not in known:
            ambiguous.append(token)
            unscoped = True  # a rejection aimed at no candidate we can name
            return
        rejections.setdefault(item, {})[(kind, key)] = payload

    negated = bool(_NEGATION.search(text))
    for clause in _clauses(text):
        starts = list(_DIRECTIVE.finditer(clause))
        preamble = clause[: starts[0].start()] if starts else clause
        words = re.sub(r"[^\w\s']", " ", preamble.lower()).split()
        if words:
            if _CANCEL.match(" ".join(words)):
                if "cancel" in allowed:
                    cancel = True
                else:
                    ambiguous.append(preamble.strip())
            elif all(w in _GO_WORDS for w in words) and "go" in allowed and not negated:
                go = True
            else:
                ambiguous.append(preamble.strip())
                if not any(n in known for n in _numbers(preamble)):
                    unscoped = True
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(clause)
            arg = clause[match.end() : end].strip().rstrip(",").strip()
            token = clause[match.start() : end].strip().rstrip(",").strip()
            verb = (match.group("verb") or match.group("word")).lower()
            if verb not in allowed:
                ambiguous.append(token)
                unscoped = unscoped or not any(n in known for n in _numbers(token))
                continue
            if verb == "skip":
                parts = _split_list(arg)
                numbers = [p for p in parts if _NUMBER.fullmatch(p)]
                if not numbers or len(numbers) != len(parts):
                    ambiguous.append(token)
                    continue
                for n in _numbers(" ".join(numbers)):
                    reject(n, "skip", "", {}, token)
                continue
            if verb == "keep":
                ids = _split_list(arg)
                if not ids or not all(_THREAD_ID.fullmatch(i) for i in ids):
                    ambiguous.append(token)
                    unscoped = True
                    continue
                keep.extend(i for i in ids if i not in keep)
                continue
            item = int(match.group("item"))
            if not arg:
                ambiguous.append(token)
                continue
            if verb == "reject-with-canned":
                reject(item, verb, arg, {"item": item, "canned_name": arg}, token)
            elif verb == "reject-with-public-fix":
                urls = _split_list(arg)
                if not all(_URL.fullmatch(u) for u in urls):
                    ambiguous.append(token)
                else:
                    reject(item, verb, " ".join(urls), {"item": item, "pr_urls": urls}, token)
            elif item not in known:
                ambiguous.append(token)
            elif verb == "edit":
                if all(e != {"item": item, "instruction": arg} for e in edits):
                    edits.append({"item": item, "instruction": arg})
            else:
                overrides.setdefault((item, verb), set()).add(arg)

    if cancel:
        return _empty("cancel", [], [])
    conflicted = {n for n, given in rejections.items() if len(given) > 1}
    conflicted |= {n for (n, _), values in overrides.items() if len(values) > 1}
    held = sorted({n for token in ambiguous for n in _numbers(token) if n in known} | conflicted)
    if conflicted:
        ambiguous.extend(f"conflicting dispositions for candidate {n}" for n in sorted(conflicted))
    if unscoped:
        return _empty("ambiguous", ambiguous, held)
    blocked = set(held)
    rejected = {n for n in rejections if n not in blocked}

    def chosen(kind: str) -> list[Any]:
        return [
            payload
            for n in sorted(rejections)
            if n in rejected
            for (k, _), payload in rejections[n].items()
            if k == kind
        ]

    importable = [n for n in sorted(known) if known[n]]
    return {
        "action": "ambiguous" if ambiguous else "import",
        "import_items": [n for n in importable if n not in rejected and n not in blocked],
        "skip_items": sorted(n for n in rejected if ("skip", "") in rejections[n]),
        "reject_with_canned": chosen("reject-with-canned"),
        "reject_with_public_fix": chosen("reject-with-public-fix"),
        "edits": [e for e in edits if e["item"] not in rejections and e["item"] not in blocked],
        "overrides": [
            {"item": n, "field": field, "value": next(iter(values))}
            for (n, field), values in overrides.items()
            if n not in rejections and n not in blocked
        ],
        "keep": keep,
        "non_import_confirmed": (
            [n for n in sorted(known) if not known[n] and n not in rejections and n not in blocked]
            if go
            else []
        ),
        "ambiguous_tokens": ambiguous,
        "ambiguous_items": held,
    }
