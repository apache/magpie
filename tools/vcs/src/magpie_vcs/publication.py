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

"""Publication helpers: which fix flow a backend takes, and the pre-publish scrub.

On a distributed backend a change becomes public at ``push`` (and, for the
security fix flow, when the pull request opens). On a centralized backend
(Subversion) it becomes public at ``commit`` and ``new-branch``, which write
straight to the server. This module holds the deterministic pieces a skill
needs to gate that moment:

- :func:`fix_flow` — the fix flow for the working copy's backend, checked
  against what the project manifest declares;
- :func:`scrub` — the embargo scrub over a commit message, a diff and a
  branch name (CVE ids, security framing, vulnerability-class names, the
  CVE-tool URL, and verbatim text from private files such as the tracker);
- :func:`commit_proposal` — the scrubbed commit proposal for a centralized
  working copy: what would be committed, what blocks it, and the exact
  ``magpie-vcs`` commands to show the user.

The term list mirrors the forbidden-term list of the ``security-issue-fix``
skill (``implementation-plan.md`` section 5c), which stays the source of
truth for the wording; this is its machine-checkable subset.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from magpie_vcs import VCSBackend

#: Manifest spellings of the *Tools enabled -> Source control* entry, by backend.
DECLARED_ALIASES: dict[str, str] = {
    "git": "git",
    "github": "git",
    "gitlab": "git",
    "forgejo": "git",
    "gitea": "git",
    "svn": "svn",
    "subversion": "svn",
    "asf-svn": "svn",
    "hg": "hg",
    "mercurial": "hg",
    "fossil": "fossil",
}

FLOW_PULL_REQUEST = "pull-request"
FLOW_PATCH_THEN_COMMIT = "patch-then-commit"

#: (label, pattern) pairs, matched case-insensitively.
DEFAULT_TERMS: tuple[tuple[str, str], ...] = (
    ("CVE id", r"\bCVE-\d{4}-\d{4,}\b"),
    ("CVE", r"\bCVEs?\b"),
    ("vulnerability", r"\bvulnerab(?:le|ility|ilities)\b"),
    ("security fix", r"\bsecurity[\s_-]+fix(?:es|ed)?\b"),
    ("advisory", r"\badvisor(?:y|ies)\b"),
    ("security@", r"\bsecurity@"),
    ("CVE-tool URL", r"cveprocess\.apache\.org"),
    ("exploit", r"\bexploit(?:s|able|ed)?\b"),
    ("SSRF", r"\bSSRF\b"),
    ("XSS", r"\bXSS\b"),
    ("CSRF", r"\bCSRF\b"),
    ("RCE", r"\bRCE\b"),
    ("SQL injection", r"\bSQL[\s_-]+injection\b"),
    ("path traversal", r"\b(?:path|directory)[\s_-]+traversal\b"),
    ("remote code execution", r"\b(?:remote|arbitrary)[\s_-]+code[\s_-]+execution\b"),
    ("privilege escalation", r"\bprivilege[\s_-]+escalation\b"),
    ("auth bypass", r"\b(?:auth|authentication|authorization)[\s_-]+bypass\b"),
    ("buffer overflow", r"\b(?:buffer|heap|stack)[\s_-]+overflow\b"),
    ("use-after-free", r"\buse[\s_-]+after[\s_-]+free\b"),
)

#: Consecutive words a public text may share with a private file before it is
#: reported as a verbatim copy.
VERBATIM_WORDS = 8

_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


class PublicationError(Exception):
    """A publication helper was given input it cannot act on."""


@dataclass(frozen=True)
class Hit:
    """One scrub finding."""

    surface: str  # "message", "diff" or "branch"
    term: str
    match: str
    line: int | None = None
    file: str | None = None


def normalise_declared(value: str | None) -> str | None:
    """Map a manifest *Source control* value onto a backend name (``None`` when unset)."""
    if value is None or not value.strip():
        return None
    key = value.strip().lower()
    if key not in DECLARED_ALIASES:
        known = ", ".join(sorted(DECLARED_ALIASES))
        raise PublicationError(f"unknown source-control value {value!r} (known: {known})")
    return DECLARED_ALIASES[key]


def fix_flow(detected: str | None, distributed: bool | None, declared: str | None) -> dict[str, Any]:
    """Choose the security fix flow.

    ``detected`` / ``distributed`` describe the working copy (``None`` when no
    working copy was found); ``declared`` is the manifest's *Source control*
    value. A working copy that contradicts the manifest is an error: the
    skill would otherwise publish through the wrong flow.
    """
    want = normalise_declared(declared)
    if detected is None and want is None:
        raise PublicationError("no working copy found and no declared source-control backend")
    if detected is not None and want is not None and detected != want:
        raise PublicationError(
            f"the manifest declares {declared!r} ({want}) but the working copy is {detected}; "
            f"fix the manifest or point at the right working copy"
        )
    backend = detected or want
    if distributed is None:
        distributed = backend != "svn"
    return {
        "backend": backend,
        "declared": declared,
        "detected": detected,
        "distributed": distributed,
        "flow": FLOW_PULL_REQUEST if distributed else FLOW_PATCH_THEN_COMMIT,
        "publishes_at": ["push"] if distributed else ["new-branch", "commit"],
    }


def _compile_terms(extra: Sequence[str], allow: Sequence[str]) -> list[tuple[str, re.Pattern[str]]]:
    allowed = {a.strip().lower() for a in allow}
    terms = [(label, re.compile(rx, re.IGNORECASE)) for label, rx in DEFAULT_TERMS]
    terms += [(t, re.compile(re.escape(t), re.IGNORECASE)) for t in extra if t.strip()]
    return [(label, rx) for label, rx in terms if label.lower() not in allowed]


def _scan(
    surface: str,
    lines: Iterable[tuple[int | None, str | None, str]],
    terms: Sequence[tuple[str, re.Pattern[str]]],
) -> list[Hit]:
    hits: list[Hit] = []
    for lineno, path, text in lines:
        for label, rx in terms:
            for m in rx.finditer(text):
                hits.append(Hit(surface, label, m.group(0), lineno, path))
    return hits


def added_lines(diff: str) -> list[tuple[int | None, str | None, str]]:
    """``(line in the diff, file, text)`` for every line a unified diff adds.

    Removed and context lines are already public, so only added lines are
    scrubbed. ``Index:`` (svn) and ``+++`` (both) headers name the file.
    """
    out: list[tuple[int | None, str | None, str]] = []
    current: str | None = None
    for n, line in enumerate(diff.splitlines(), start=1):
        if line.startswith("Index: "):
            current = line[len("Index: ") :].strip()
        elif line.startswith("+++ "):
            name = line[4:].split("\t", 1)[0].strip()
            current = name.removeprefix("b/") if name != "/dev/null" else current
        elif line.startswith("+"):
            out.append((n, current, line[1:]))
    return out


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _shingles(text: str, width: int) -> set[tuple[str, ...]]:
    words = _words(text)
    return {tuple(words[i : i + width]) for i in range(len(words) - width + 1)}


def _verbatim(message: str, private_texts: Sequence[str], width: int) -> list[Hit]:
    private: set[tuple[str, ...]] = set()
    for text in private_texts:
        private |= _shingles(text, width)
    if not private:
        return []
    hits: list[Hit] = []
    for n, line in enumerate(message.splitlines(), start=1):
        words = _words(line)
        for i in range(len(words) - width + 1):
            if tuple(words[i : i + width]) in private:
                hits.append(Hit("message", "verbatim private text", " ".join(words[i : i + width]), n))
                break
    return hits


def scrub(
    *,
    message: str | None = None,
    diff: str | None = None,
    branch: str | None = None,
    extra_files: Sequence[tuple[str, str]] = (),
    extra_terms: Sequence[str] = (),
    allow: Sequence[str] = (),
    private_texts: Sequence[str] = (),
) -> dict[str, Any]:
    """Scrub the surfaces a publication exposes and return ``{clean, hits}``.

    ``extra_files`` are ``(path, content)`` pairs for new files a commit will
    add that the diff does not show yet (unversioned files about to be
    staged); every line of them counts as added. ``allow`` drops a term by
    its label — the user's explicit call, never the skill's. The verbatim
    check against ``private_texts`` runs on the message only: the diff may
    rightly carry a fix snippet agreed in the private discussion.
    """
    terms = _compile_terms(extra_terms, allow)
    hits: list[Hit] = []
    if message is not None:
        hits += _scan("message", ((n, None, t) for n, t in enumerate(message.splitlines(), 1)), terms)
        if "verbatim private text" not in {a.strip().lower() for a in allow}:
            hits += _verbatim(message, private_texts, VERBATIM_WORDS)
    if diff is not None:
        hits += _scan("diff", added_lines(diff), terms)
    for path, content in extra_files:
        hits += _scan("diff", ((n, path, t) for n, t in enumerate(content.splitlines(), 1)), terms)
    if branch is not None:
        # Separators hide words from \b patterns (`security-fix`), so scan the
        # name as written and with separators turned into spaces.
        spaced = re.sub(r"[-_/.]+", " ", branch)
        seen: set[str] = set()
        for hit in _scan("branch", [(None, None, branch), (None, None, spaced)], terms):
            if hit.term not in seen:
                seen.add(hit.term)
                hits.append(hit)
    return {"clean": not hits, "hits": [asdict(h) for h in hits]}


def _under(path: str, roots: Sequence[str]) -> bool:
    norm = path.strip("/")
    return any(norm == r.strip("/") or norm.startswith(r.strip("/") + "/") for r in roots)


def _read_new_files(root: Path, paths: Sequence[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for rel in paths:
        p = root / rel
        files = sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else [p] if p.is_file() else []
        for f in files:
            out.append((f.relative_to(root).as_posix(), f.read_text(errors="replace")))
    return out


def commit_proposal(
    backend: VCSBackend,
    *,
    message: str,
    message_file: str,
    branch: str | None = None,
    expect: Sequence[str] = (),
    extra_terms: Sequence[str] = (),
    allow: Sequence[str] = (),
    private_files: Sequence[str] = (),
    tool: Sequence[str] = ("magpie-vcs",),
) -> dict[str, Any]:
    """Build the scrubbed commit proposal for a centralized working copy.

    Lists what the commit would publish (SVN commits every versioned change in
    the working copy), the paths outside ``expect`` (the agreed file list,
    required) that would ride along, and
    the scrub result over the message, the diff, the new files and the branch
    name. ``commands`` is filled only when nothing blocks; each command that
    publishes carries ``--scrub`` so the gate runs again at execution time.
    """
    if backend.distributed:
        raise PublicationError(
            f"{backend.name} is distributed: the change becomes public at push, so the pull-request "
            f"flow's own checks apply, not this proposal"
        )
    if not expect:
        raise PublicationError(
            "name the agreed file list (--expect): SVN commits every change in the working copy"
        )
    changes = backend.changed_paths()
    to_commit = [p for item, p in changes if item in ("modified", "added", "deleted", "replaced")]
    unversioned = [p for item, p in changes if item == "unversioned"]
    missing = [p for item, p in changes if item == "missing"]
    troubled = [p for item, p in changes if item in ("conflicted", "obstructed", "incomplete")]
    to_stage = [p for p in unversioned + missing if _under(p, expect)]
    unexpected = [p for p in to_commit + troubled if not _under(p, expect)]
    left_out = [p for p in unversioned + missing if not _under(p, expect)]
    privates = [Path(f).read_text(errors="replace") for f in private_files]
    result = scrub(
        message=message,
        diff=backend.diff(),
        branch=branch,
        extra_files=_read_new_files(backend.root, [p for p in to_stage if p not in missing]),
        extra_terms=extra_terms,
        allow=allow,
        private_texts=privates,
    )
    gate: list[str] = ["--scrub"]
    for t in extra_terms:
        gate += ["--term", t]
    for a in allow:
        gate += ["--allow", a]
    for f in private_files:
        gate += ["--private-file", f]
    blocked: list[str] = []
    if not result["clean"]:
        blocked.append("scrub hits")
    if unexpected:
        blocked.append("paths outside the agreed file list would be committed")
    if troubled:
        blocked.append("the working copy has conflicted, obstructed or incomplete paths")
    if not (to_commit or to_stage):
        blocked.append("nothing to commit")
    base = [*tool, "-C", str(backend.root)]
    commands: list[list[str]] = []
    if not blocked:
        if branch:
            commands.append([*base, "new-branch", *gate, branch])
        if to_stage:
            commands.append([*base, "stage", *to_stage])
        commands.append([*base, "commit", *gate, "--message-file", message_file])
    return {
        "backend": backend.name,
        "flow": FLOW_PATCH_THEN_COMMIT,
        "publishes_at": ["new-branch", "commit"],
        "line_of_work": backend.current_branch(),
        "would_commit": sorted(set(to_commit + to_stage)),
        "unexpected_paths": unexpected,
        "troubled_paths": troubled,
        "left_unversioned": left_out,
        "clean": result["clean"],
        "hits": result["hits"],
        "ready": not blocked,
        "blocked_by": blocked,
        "commands": commands,
    }
