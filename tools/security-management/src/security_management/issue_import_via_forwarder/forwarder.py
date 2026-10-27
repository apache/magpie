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
"""Steps 0, 1 and 3 of the forwarder sub-skill, and the bot-credit check of Step 2.

No adapter is named here: every pattern, handle and attribute comes from
`project.md → forwarders` in the input, and "installed" means an adapter
directory under `tools/forwarder-relay/` or a `shipping` row of that
README's adapter table whose reference doc exists. The body arrives already
redacted by the parent; nothing here redacts again, and `N-…` / `E-…`
tokens are just text. Extracting the credit line, and saying which
milestone a sync draft is, stay the model's.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from security_management.issue_import.prefilter import address
from security_management.shared import reuse

PREAMBLE_CHARS = 400
SNIPPET_CHARS = 80
REGISTRY = Path("tools/forwarder-relay")
_SHIPPING_ROW = re.compile(r"^\|\s*`([A-Za-z0-9_-]+)`\s*\|\s*shipping\s*\|.*\]\(([^)]+)\)\s*\|\s*$", re.M)
_NAME = re.compile(r"[A-Za-z0-9_-]+")

# Milestone kinds the routing policy names (docs/security/forwarder-routing-policy.md).
RELAY = frozenset({"receipt", "accepted-valid", "assessed-invalid", "advisory-sent", "info-requested"})
OUTSIDE_POLICY = frozenset({"cve-allocated"})
NEGATIVE_SPACE = frozenset({"workflow-status", "credit-confirmation", "reviewer-comment", "sync-rollup"})
MODES = ("import", "invalidate", "sync")

NO_CONFIG_NOTE = (
    "forwarders.enabled is empty, so no relay handling is configured; "
    "the parent skill proceeds with its direct-reporter path."
)
NOT_INSTALLED = (
    "adapter `{name}` is declared in forwarders.enabled but is not installed under "
    "tools/forwarder-relay/; aborting."
)
MALFORMED = (
    "inbound message is missing a {what}; a relay message stripped of its headers is not "
    "a relay message, so the skill fails fast."
)
NO_MATCH_NOTE = "no registered forwarder adapter matched this message; parent skill proceeds with the direct-reporter path."
PARTIAL_MATCH_NOTE = (
    "only one of an adapter's two relay signals (sender, preamble) matched; relay mode needs both, "
    "so the parent skill proceeds with the direct-reporter path and shows this to the user."
)


def installed(framework: Path) -> set[str]:
    """Adapter names with a directory under the registry, or a `shipping` README row whose doc exists."""
    root = framework / REGISTRY
    names = {p.name for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()
    readme = root / "README.md"
    if readme.is_file():
        for name, doc in _SHIPPING_ROW.findall(readme.read_text(encoding="utf-8")):
            if (root / doc).resolve().is_file():
                names.add(name)
    return names


def preflight(enabled: Sequence[object], available: set[str], message: Mapping[str, Any]) -> dict[str, Any]:
    names = [str(n) for n in enabled]
    if not names:
        return {
            "preflight_passed": False,
            "outcome": "no-forwarder-config",
            "match": None,
            "sub_skill_applied": False,
            "error": None,
            "note": NO_CONFIG_NOTE,
        }

    def abort(error: str) -> dict[str, Any]:
        return {"preflight_passed": False, "outcome": "abort", "error": error, "note": None}

    for name in names:
        if not _NAME.fullmatch(name) or name not in available:
            return abort(NOT_INSTALLED.format(name=name))
    for key, what in (("from", "`From:` header"), ("date", "`Date:` header"), ("body", "non-empty body")):
        if not str(message.get(key) or "").strip():
            return abort(MALFORMED.format(what=what))
    return {"preflight_passed": True, "outcome": "proceed", "error": None, "note": None}


def _snippet(body: str, start: int) -> str:
    end = body.find("\n", start)
    return body[start : end if end >= 0 else len(body)][:SNIPPET_CHARS]


def detect(
    message: Mapping[str, Any], forwarders: Mapping[str, Any], collaborators: Sequence[object] = ()
) -> dict[str, Any]:
    """The first enabled adapter whose sender pattern AND preamble regex both match; later ones are skipped.

    Either signal alone is forgeable by any sender (a `From:` display or a
    pasted preamble), so one signal is not a relay: it is reported in
    `partial_matches` for the parent to surface, and the message stays on the
    direct-reporter path.
    """
    sender = address(str(message.get("from") or ""))
    body = str(message.get("body") or "")
    preamble = body[:PREAMBLE_CHARS]
    tried: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for name in [str(n) for n in forwarders.get("enabled") or []]:
        config = forwarders.get(name) or {}
        sender_pattern, preamble_pattern = config.get("sender_pattern"), config.get("preamble_match")
        if not sender_pattern or not preamble_pattern:
            raise ValueError(f"adapter {name!r}: sender_pattern or preamble_match is not resolved")
        try:
            by_sender = re.search(str(sender_pattern), sender, re.IGNORECASE)
            by_preamble = re.search(str(preamble_pattern), preamble)
        except re.error as exc:
            raise ValueError(f"adapter {name!r}: a pattern does not compile: {exc}") from exc
        tried.append({"adapter": name, "sender": bool(by_sender), "preamble": bool(by_preamble)})
        if bool(by_sender) != bool(by_preamble):
            partial.append({"adapter": name, "signal": "sender" if by_sender else "preamble"})
        if by_sender and by_preamble:
            known = {str(c).strip().lower() for c in collaborators}
            local = sender.split("@", 1)[0]
            return {
                "match": name,
                "sub_skill_applied": True,
                "preamble_snippet": _snippet(body, by_preamble.start()),
                "sender_matched": sender,
                "collaborator_warning": bool(sender) and (sender in known or local in known),
                "adapters": tried,
                "partial_matches": partial,
                "note": None,
            }
    return {
        "match": None,
        "sub_skill_applied": False,
        "preamble_snippet": None,
        "sender_matched": None,
        "collaborator_warning": False,
        "adapters": tried,
        "partial_matches": partial,
        "note": PARTIAL_MATCH_NOTE if partial else NO_MATCH_NOTE,
    }


def credit_kind(name: str, kind_hints: Mapping[str, Sequence[str]] | None = None) -> dict[str, Any]:
    """`kind` for an extracted credit: `tool` under the bot/AI policy, else the adapter's hints, else `human`."""
    text = name.strip()
    if not text:
        return {"name": "", "kind": "unknown", "is_bot": False, "credit_unknown": True}
    is_bot = reuse.is_bot_credit(text)
    kind = "tool" if is_bot else "human"
    if not is_bot:
        for hinted in ("tool", "service"):
            if any(re.search(p, text, re.IGNORECASE) for p in (kind_hints or {}).get(hinted) or []):
                kind = hinted
                break
    return {"name": text, "kind": kind, "is_bot": is_bot, "credit_unknown": False}


def first_name(value: str) -> dict[str, Any]:
    """The salutation name in a display name or a `@handle`; none (generic salutation) for an address."""
    text = re.sub(r"<[^>]*>", "", value).strip().strip('"').strip()
    if not text or re.search(r"\S@\S", text):
        return {"first_name": None, "generic": True}
    word = re.split(r"[\s._-]+", text.lstrip("@"), maxsplit=1)[0]
    if not re.fullmatch(r"[^\W\d_][\w'\u2019]*", word):
        return {"first_name": None, "generic": True}
    return {"first_name": word[:1].upper() + word[1:], "generic": False}


def route(mode: str, milestone: str | None, adapter: Mapping[str, Any]) -> dict[str, Any]:
    """Step 3: recipients, whether to render the addressing block, `question_mode`, suppression."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    kinds = RELAY | OUTSIDE_POLICY | NEGATIVE_SPACE
    if mode == "sync" and milestone not in kinds:
        raise ValueError(f"--milestone must be one of {', '.join(sorted(kinds))} in sync mode")
    if milestone is not None and milestone not in kinds:
        raise ValueError(f"unknown milestone {milestone!r}")
    handles = adapter.get("contact_handle") or []
    handles = [handles] if isinstance(handles, str) else [str(h) for h in handles]
    if not handles:
        raise ValueError("the matched adapter has no contact_handle")
    if mode == "sync" and milestone in NEGATIVE_SPACE:
        return {
            "mode": mode,
            "milestone": milestone,
            "to_recipients": [],
            "addressing_block_emitted": False,
            "negative_space_suppressed": True,
        }
    return {
        "mode": mode,
        "milestone": milestone,
        "to_recipients": handles[:1],
        "fallback_recipients": handles[1:],
        "addressing_block_emitted": True,
        "question_mode": bool(adapter.get("via_forwarder_question_mode")),
        "negative_space_suppressed": False,
    }
