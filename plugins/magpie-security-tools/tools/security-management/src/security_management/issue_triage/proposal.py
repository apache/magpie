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
"""Step 4 proposal comment and the Step 6 pre-post scrub.

`render` lays out the comment the agent's prose goes into: the two markers
the pre-flight skip reads back, the class line, the severity guess (never a
CVSS score or vector), the fix shape, action items and the `@`-mention line.
It adds what a class always carries (the DEFENSE-IN-DEPTH sentence, the
INFO-ONLY canned heading, the PROBABLE-DUP next command, the
FIX-ALREADY-PUBLIC reporter-reply draft), links every bare `#NNN`, and refuses
a comment it would have to guess about: an unknown class, more than 3
handles, a handle off the roster, a canned heading that is not in
`canned-responses.md`, a severity that is a score.

`scrub` replaces bare display names from the name map with `@`-handles
(word-bounded, outside code spans, URLs and existing handles) and links
bare references. Flagging an injection attempt stays the agent's call.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import dispositions, refs
from security_management.shared.rollup import one_line
from security_management.shell import w

DID_SENTENCE = "defense-in-depth fix is welcome via public PR; not a CVE."
UNCERTAIN_LINE = "**Low-confidence proposal, please challenge.**"
_SCORE = re.compile(r"CVSS|\b\d{1,2}\.\d\b|\bAV:[NALP]\b|\b\d{1,2}\s*/\s*10\b", re.IGNORECASE)
_CVE = re.compile(r"(?<![\w/=\[-])CVE-\d{4}-\d{4,7}\b(?!\]\()")
_CODE_OR_URL = re.compile(r"(`+).*?\1|https?://\S+|\[[^\]\n]*\]\([^)\n]*\)")


def _pr_link(upstream: str, number: object) -> str:
    return f"[`{upstream}#{int(str(number))}`](https://github.com/{upstream}/pull/{int(str(number))})"


def fix_public_reply(upstream: str, prs: Sequence[Mapping[str, Any]]) -> str:
    """The FIX-ALREADY-PUBLIC reporter-reply draft of `classification.md`, one entry per candidate PR."""
    if not prs:
        raise ValueError("FIX-ALREADY-PUBLIC needs at least one candidate PR")
    described = []
    for pr in prs:
        author = one_line(pr["author"])
        when = "merged" if str(pr.get("state", "")).lower() == "merged" else "open since"
        described.append(
            f"{_pr_link(upstream, pr['number'])}\n> ([`{author}`](https://github.com/{author}), {when} "
            f"{one_line(pr['date'])[:10]})"
        )
    links = " and ".join(_pr_link(upstream, pr["number"]) for pr in prs)
    lead = "\n> and ".join(described)
    return (
        f"> Thanks for the report. We noticed that\n> {lead}\n"
        "> already appears to address what you described. Per our policy,\n"
        "> we do not credit a finder when the fix to the reported issue\n"
        "> is already public at the time of report — but we very much\n"
        "> appreciate you taking the time to write to us.\n"
        ">\n"
        f"> Could you check whether\n> {links}\n"
        "> fixes the behaviour you observed? If it does, no further\n"
        "> action is needed on your side. If after testing with the PR\n"
        "> you still see the issue, please reply on this thread with\n"
        "> the failing reproduction and we will reopen the discussion.\n"
    )


# A quote mark, straight or curly; code spans are masked before scanning.
_QUOTE_MARK = re.compile(r"[\"“”]")
_CODE_SPAN = re.compile(r"(`+).*?\1", re.DOTALL)
# What may join two quotes that cite the same source: `"A" and "B" ([model](…))`.
_JOINER = re.compile(r"^[\s,;:]*(?:and|or)?[\s,;:]*$", re.IGNORECASE)
# Shorter quoted spans are terms ("Connection String"), not sentences.
_MIN_QUOTE = 20
# What separates the fragments of a quote that leaves something out.
_ELISION = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|…|\.\.\.)\s*")
# How far after a quote its citation link may start and still be its own.
_CITATION_REACH = 300


def _normalise_prose(text: str) -> str:
    """Prose as compared: no inline markup, plain quotes, single spaces."""
    text = re.sub(r"[*`]", "", text)
    # Curly quotes as escapes (left/right single, left/right double).
    for curly, plain in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"')):
        text = text.replace(curly, plain)
    return re.sub(r"\s+", " ", text).strip()


def check_model_quotes(summary: str, data: Mapping[str, Any]) -> tuple[str | None, list[str]]:
    """Refuse a summary that presents as Security Model text anything the model does not say.

    A quote counts as a model quote when a link to `model_url` follows it
    within `_CITATION_REACH` characters, before the next quote starts. Every
    such quote must appear verbatim in `model_file` (the copy of the model
    the run fetched and cached, Step 2.5), up to inline markup, quote style
    and whitespace; an elided quote (`[...]`, `…`) must match fragment by
    fragment, in order. Returns (refusal or None, the quotes verified).
    """
    url = str(data.get("model_url") or "").strip().rstrip("/")
    if not url or url not in summary:
        return None, []
    path = str(data.get("model_file") or "").strip()
    if not path:
        return (
            "the summary cites the Security Model; pass `model_file`, the copy of the model this run "
            "fetched (Step 2.5), so every quote can be checked against it",
            [],
        )
    try:
        with open(path, encoding="utf-8") as fh:
            document = _normalise_prose(fh.read())
    except OSError as exc:
        return f"cannot read model_file {path!r}: {exc.strerror}", []
    # Pair quote marks in order (open, close, open, close ...) on a copy with
    # code spans blanked out, so `open(path, "a")` is not half a quote.
    masked = _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), summary)
    marks = [m.start() for m in _QUOTE_MARK.finditer(masked)]
    spans = [(marks[i], marks[i + 1] + 1) for i in range(0, len(marks) - 1, 2)]
    # Quotes joined only by `and` / punctuation cite the same source: group them.
    groups: list[list[tuple[int, int]]] = []
    for span in spans:
        if groups and _JOINER.match(summary[groups[-1][-1][1] : span[0]]):
            groups[-1].append(span)
        else:
            groups.append([span])
    cited: list[str] = []
    for i, group in enumerate(groups):
        end = group[-1][1]
        limit = groups[i + 1][0][0] if i + 1 < len(groups) else len(summary)
        if url not in summary[end : min(limit, end + _CITATION_REACH)]:
            continue
        cited.extend(summary[a + 1 : b - 1] for a, b in group if b - a - 2 >= _MIN_QUOTE)
    for quote in cited:
        position = 0
        for fragment in _ELISION.split(quote):
            wanted = _normalise_prose(fragment).strip(" .,;:")
            if not wanted:
                continue
            found = document.find(wanted, position)
            if found < 0:
                return (
                    f"Security Model quote not found verbatim in the model: {wanted!r}; "
                    "quote the model's own words from model_file (never a quote copied from a tracker "
                    "comment) or drop the quotation marks and paraphrase without presenting it as the model",
                    [],
                )
            position = found + len(wanted)
    return None, cited


def _replace_outside_protected(text: str, pattern: re.Pattern[str], repl: str) -> tuple[str, int]:
    out: list[str] = []
    count = 0
    last = 0
    for match in _CODE_OR_URL.finditer(text):
        piece, n = pattern.subn(repl, text[last : match.start()])
        out.append(piece)
        count += n
        out.append(match.group(0))
        last = match.end()
    piece, n = pattern.subn(repl, text[last:])
    out.append(piece)
    return "".join(out), count + n


def scrub(text: str, names: Mapping[str, str], tracker: str) -> dict[str, Any]:
    """`text` with each bare display name replaced by its `@`-handle, and bare references linked."""
    replacements = []
    # Longest names first, so "Alice Smith" wins over a "Smith" entry.
    for name in sorted(names, key=len, reverse=True):
        handle = "@" + str(names[name]).strip().lstrip("@")
        if not name.strip():
            continue
        # A name inside link text is still bare: rewrite [Alice Smith](…) to @alice first.
        link = re.compile(r"\[" + re.escape(name) + r"\]\([^)\n]*\)")
        text, linked = link.subn(handle, text)
        bare = re.compile(r"(?<![@\w])" + re.escape(name) + r"(?!\w)")
        text, count = _replace_outside_protected(text, bare, handle)
        if linked + count:
            replacements.append({"bare_name": name, "handle": handle, "count": linked + count})
    found = refs.bare_refs(text)
    return {"text": refs.linkify(text, tracker), "replacements_made": replacements, "linked_refs": found}


def render(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    number = int(data["number"])
    raw_class = str(data.get("class") or "").strip().upper()
    uncertain = raw_class == "UNCERTAIN"
    klass = dispositions.normalise_class(data.get("tentative_class") if uncertain else raw_class)
    if klass is None:
        what = "tentative_class for UNCERTAIN" if uncertain else "class"
        return {"ok": False, "refused": f"{what} must be one of {', '.join(dispositions.CLASSES)}"}
    severity = one_line(data.get("severity"))
    if not severity or _SCORE.search(severity):
        return {
            "ok": False,
            "refused": "severity must be a qualitative guess (`my read is Medium-ish, team-scoring expected`), "
            "never a CVSS score or vector",
        }
    roster = {str(r).strip().lstrip("@").lower() for r in data.get("roster") or []}
    viewer = str(data.get("viewer") or "").strip().lstrip("@").lower()
    handles = [str(h).strip().lstrip("@") for h in data.get("handles") or [] if str(h).strip()]
    if not handles:
        return {"ok": False, "refused": "no @-mention: route at least one handle (routing-failure fallback)"}
    if len(handles) > 3:
        return {"ok": False, "refused": f"{len(handles)} handles; the cap is 3, prefer 2"}
    off = [h for h in handles if h.lower() not in roster or h.lower() == viewer]
    if off:
        return {"ok": False, "refused": f"not mentionable (off the roster, or the triager): {', '.join(off)}"}
    summary = str(data.get("summary") or "").strip()
    question = one_line(data.get("question")).rstrip("?")
    if not summary or not question:
        return {"ok": False, "refused": "summary and question are required"}
    quote_problem, verified_quotes = check_model_quotes(summary, data)
    if quote_problem:
        return {"ok": False, "refused": quote_problem}
    fix_shape = str(data.get("fix_shape") or "").strip()
    extra: list[str] = []
    if klass == "DEFENSE-IN-DEPTH" and DID_SENTENCE.lower() not in fix_shape.lower():
        fix_shape = f"{fix_shape} {DID_SENTENCE[0].upper()}{DID_SENTENCE[1:]}".strip()
    if klass == "INFO-ONLY":
        canned = one_line(data.get("canned_heading"))
        headings = [one_line(h) for h in data.get("canned_headings") or []]
        if not canned or (headings and canned not in headings):
            return {"ok": False, "refused": "INFO-ONLY names an exact heading from canned-responses.md"}
        extra.append(f"Canned response: *{canned}*.")
    if klass == "PROBABLE-DUP":
        kept = data.get("kept_tracker")
        if not kept:
            return {"ok": False, "refused": "PROBABLE-DUP needs the kept tracker"}
        extra.append(
            f"Kept tracker: {refs.tracker_link(tracker, kept)}; next: `security-issue-deduplicate {int(kept)} {number}`."
        )
    if klass == "FIX-ALREADY-PUBLIC":
        try:
            extra.append(
                "Draft reporter reply (sent later by `security-issue-invalidate`, not here):\n\n"
                + fix_public_reply(str(data["upstream"]), data.get("prs") or [])
            )
        except (KeyError, ValueError) as exc:
            return {"ok": False, "refused": f"FIX-ALREADY-PUBLIC: {exc}"}
    open_question = one_line(data.get("open_question"))
    severity_line = f"Severity: {severity.rstrip('.')}."
    if open_question:
        severity_line += f" Final scoring per the team after assessing {open_question.rstrip('.')}."
    items = [one_line(i) for i in data.get("action_items") or [] if one_line(i)]
    parts = [dispositions.PROPOSAL_HEADER, ""]
    if uncertain:
        parts += [UNCERTAIN_LINE, ""]
    parts += [summary, "", f"{dispositions.DISPOSITION_PREFIX}{klass}.**", "", severity_line]
    if fix_shape:
        parts += ["", fix_shape]
    for block in extra:
        parts += ["", block.rstrip("\n")]
    if len(items) > 1:
        parts += ["", "Action items:", "", *(f"{i}. {item}" for i, item in enumerate(items, 1))]
    elif items:
        parts += ["", items[0]]
    parts += ["", f"{' '.join('@' + h for h in handles)} — {question}?"]
    text = "\n".join(parts) + "\n"
    scrubbed = scrub(text, data.get("names") or {}, tracker)
    text = scrubbed["text"]
    # The comment is posted through the vetted `issue-comment` operation,
    # which accepts a body file only from its workspace; `scratch` stays
    # the fallback for callers that do not pass one.
    workspace = str(data.get("workspace") or data.get("scratch") or "").rstrip("/")
    path = f"{workspace}/triage-{number}.md"
    return {
        "ok": True,
        "text": text,
        "class": klass,
        "uncertain": uncertain,
        "handles": [f"@{h}" for h in handles],
        "replacements_made": scrubbed["replacements_made"],
        "linked_refs": scrubbed["linked_refs"],
        "unlinked_cves": _unlinked_cves(text),
        "model_quotes_verified": verified_quotes,
        "file": path,
        "command": (
            "uv run --project ~/.claude/magpie/vetted-ops vetted-op "
            f"--caller security-issue-triage issue-comment {number} {w(path)}"
        ),
    }


def _unlinked_cves(text: str) -> list[str]:
    stripped = re.sub(r"\[[^\]\n]*\]\([^)\n]*\)", "", text)
    return sorted(set(_CVE.findall(stripped)))
