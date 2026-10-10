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
"""The mechanical scans of Steps 3 and 4.

Each returns candidate findings in the Step 4 shape (`file`, `category`,
`severity`, `reason`, plus evidence). The agent still reads the diff and owns
every finding it posts; these are the parts a rule decides on its own —
security-disclosure language, the AI-authorship disclosure, compiled artifacts,
images, third-party licence categories, missing / mis-applied headers and the
header-tool exclusion that masks one.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from ..triage.signals import SECURITY_PATTERNS
from . import diff as difflib
from .data import PR

# --- Step 3: security-disclosure language --------------------------------------


def _context(text: str, start: int, end: int) -> str:
    """The clause around a match: the sentence it sits in, joined across line breaks."""
    flat = re.sub(r"\s+", " ", text)
    offset = len(re.sub(r"\s+", " ", text[:start]))
    stop = max(flat.rfind(". ", 0, offset), flat.rfind(", ", 0, offset))
    left = stop + 2 if stop != -1 else 0
    right_candidates = [i for i in (flat.find(". ", offset), flat.find(", ", offset)) if i != -1]
    right = min(right_candidates) if right_candidates else len(flat)
    return flat[left:right].strip().rstrip(".")


def security_disclosure(pr: PR) -> dict[str, Any]:
    places: list[tuple[str, str]] = [("title", pr.title), ("body", pr.body)]
    places += [("commit", c.message) for c in pr.commits]
    matches: list[dict[str, str]] = []
    for where, text in places:
        for _label, pattern in SECURITY_PATTERNS:
            for match in re.finditer(pattern, text or "", flags=re.IGNORECASE):
                if any(
                    m["location"] == where and m["matched_text"].lower() in match.group(0).lower()
                    for m in matches
                ):
                    continue
                matches.append(
                    {
                        "location": where,
                        "matched_text": match.group(0),
                        "context": _context(text, match.start(), match.end()),
                    }
                )
                break
    # "exploit" also matches inside "exploitable": keep the longer one.
    pruned = [
        m
        for m in matches
        if not any(
            o is not m
            and o["location"] == m["location"]
            and m["matched_text"].lower() in o["matched_text"].lower()
            and len(o["matched_text"]) > len(m["matched_text"])
            for o in matches
        )
    ]
    return {"triggered": bool(pruned), "matches": pruned}


# --- Step 3: AI-authorship disclosure -----------------------------------------------

_DISCLOSURE_HEADING = re.compile(
    r"(generative[- ]ai|ai[- ]assist|ai tooling|generated-by|co-author)", re.IGNORECASE
)
_AI_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "test-plan task list",
        re.compile(r"^#+\s*test plan\s*$(?:\n(?!#).*)*?\n\s*- \[[ xX]\]", re.IGNORECASE | re.MULTILINE),
    ),
    ("echoed title line", re.compile(r"^\*\*(title|summary):\*\*", re.IGNORECASE | re.MULTILINE)),
    (
        "tool trailer",
        re.compile(
            r"(generated[- ]with|🤖|co-authored-by:\s*(claude|copilot|cursor|devin|gpt|gemini))",
            re.IGNORECASE,
        ),
    ),
    ("first-person tool", re.compile(r"\bI \((claude|cursor|copilot|devin|gpt|gemini)", re.IGNORECASE)),
)
_STRUCTURED = re.compile(r"^##\s*(summary|changes|test plan)\s*$", re.IGNORECASE | re.MULTILINE)
_AFFIRMED = (
    re.compile(r"^\s*[-*] \[[xX]\]\s*yes", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*generated-by:\s*\S", re.IGNORECASE | re.MULTILINE),
)


def ai_disclosure(body: str, template: str | None, criteria_requires: bool = False) -> dict[str, Any]:
    requires = criteria_requires or bool(template and _DISCLOSURE_HEADING.search(template))
    signals = [name for name, pattern in _AI_SIGNALS if pattern.search(body)]
    template_headings = set(_STRUCTURED.findall(template or ""))
    if len(_STRUCTURED.findall(body)) >= 2 and not template_headings:
        signals.append("structured headings replacing the template")
    visible = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    affirmed = any(p.search(visible) for p in _AFFIRMED)
    ai = bool(signals)
    return {
        "requires_disclosure": requires,
        "ai_authored": ai,
        "signals": signals,
        "disclosure_affirmed": affirmed,
        "finding": requires and ai and not affirmed,
        "severity": "minor",
        "category": "AI-generated code signals",
    }


# --- Step 4: compiled artifacts and images --------------------------------------------

COMPILED = (
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".o",
    ".a",
    ".whl",
    ".egg",
)
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")
COMPILED_REASON = (
    "Compiled artifacts must not be committed to the source tree — ASF releases are source-only; remove this file "
    "and ensure it is generated at build time."
)
RELEASED_REASON = (
    "This compiled native artifact would be included in the release archive, violating the ASF Release Policy "
    "which requires source-only releases."
)


def compiled_artifacts(added: list[str], in_release: set[str] | None = None) -> list[dict[str, Any]]:
    """`major` per added artifact; `blocking` for one the agent confirmed lands in a release archive."""
    found = []
    for path in added:
        if path.lower().endswith(COMPILED):
            released = path in (in_release or set())
            found.append(
                {
                    "file": path,
                    "category": "Quality signals to check",
                    "severity": "blocking" if released else "major",
                    "reason": RELEASED_REASON if released else COMPILED_REASON,
                    "judge": None
                    if released
                    else "escalate to blocking if the file would ship in a release archive",
                }
            )
    return found


def images(added: list[str]) -> list[str]:
    """Added images: the agent judges diagram/screenshot (no finding) against logo/brand asset (ask)."""
    return [p for p in added if p.lower().endswith(IMAGES)]


# --- Step 4: third-party licences ------------------------------------------------------

_SPDX = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+(?:\s+(?:OR|AND|WITH)\s+[A-Za-z0-9.+-]+)*)")
_LICENCE_BLOCKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GPL-3.0", re.compile(r"GNU (Affero )?General Public License", re.IGNORECASE)),
    ("LGPL", re.compile(r"GNU Lesser General Public License", re.IGNORECASE)),
    ("MIT", re.compile(r"\bMIT License\b|Permission is hereby granted, free of charge", re.IGNORECASE)),
    ("BSD-3-Clause", re.compile(r"Redistribution and use in source and binary forms", re.IGNORECASE)),
    ("MPL-2.0", re.compile(r"Mozilla Public License", re.IGNORECASE)),
    ("EPL-2.0", re.compile(r"Eclipse Public License", re.IGNORECASE)),
    ("CDDL", re.compile(r"Common Development and Distribution License", re.IGNORECASE)),
)
_COPYRIGHT = re.compile(r"Copyright\s*(?:\(c\)|©)?\s*(?:\d{4}[-\u2013, \d]*)?\s*(.+)", re.IGNORECASE)
_ADAPTED = re.compile(r"\b(adapted|derived|ported|copied|vendored) from\b|\bbased on\b", re.IGNORECASE)

CATEGORY_X = ("GPL", "AGPL", "LGPL", "CDDL", "BUSL", "SSPL")
CATEGORY_B = ("MPL", "EPL")
CATEGORY_A = ("MIT", "BSD", "ISC", "APACHE-2.0", "0BSD", "ZLIB", "PSF", "UNLICENSE")
_LEGAL = re.compile(r"(^|/)(LICENSE|LICENCE|NOTICE|DISCLAIMER|COPYING)(\.[A-Za-z]+)?$", re.IGNORECASE)


def licence_category(identifier: str) -> str | None:
    upper = identifier.upper()
    if upper.startswith(CATEGORY_X) or "GPL" in upper:
        return "X"
    if upper.startswith(CATEGORY_B):
        return "B"
    if upper.startswith(CATEGORY_A):
        return "A"
    return None


def _licence_of(head: str) -> str | None:
    spdx = _SPDX.search(head)
    if spdx:
        return spdx.group(1).strip()
    for name, pattern in _LICENCE_BLOCKS:
        if pattern.search(head):
            return name
    return None


def _third_party(head: str) -> bool:
    """A non-ASF copyright line or an "adapted from" note: the file came from elsewhere."""
    for match in _COPYRIGHT.finditer(head):
        holder = match.group(1)
        if "apache software foundation" not in holder.lower():
            return True
    return bool(_ADAPTED.search(head))


def is_legal_file(path: str) -> bool:
    return bool(_LEGAL.search(path)) or path.startswith(("licenses/", "licences/"))


def third_party_licences(files: list[difflib.DiffFile]) -> list[dict[str, Any]]:
    licence_touched = any(re.match(r"^LICEN[CS]E(\.txt)?$", f.path, re.IGNORECASE) for f in files)
    found = []
    for f in files:
        if is_legal_file(f.path) or not f.added:
            continue
        head = "\n".join(f.head(25))
        licence = _licence_of(head)
        if licence is None or (licence.upper().startswith("APACHE-2.0") and not _third_party(head)):
            continue
        if not _third_party(head):
            continue  # contributor-authored with a wrong identifier: a licence-header finding
        category = licence_category(licence)
        short = licence.split("-")[0]
        if category == "X":
            found.append(
                {
                    "file": f.path,
                    "licence": licence,
                    "category": "X",
                    "severity": "blocking",
                    "reason": f"{short} is a Category X licence under the ASF resolved_licenses policy and "
                    "cannot be included in an ASF release in any form.",
                }
            )
        elif category == "B":
            found.append(
                {
                    "file": f.path,
                    "licence": licence,
                    "category": "B",
                    "severity": "blocking",
                    "reason": f"{short} is a Category B licence and cannot be included in source form in an "
                    "ASF release; binary-only inclusion requires explicit justification.",
                }
            )
        elif category == "A" and not licence_touched:
            licenses_dir = any(o.path.startswith(("licenses/", "licences/")) for o in files)
            reason = (
                f"{short} is a Category A licence; LICENSE / LICENSE.txt was not updated to add an attribution "
                "notice — a licenses/ directory entry alone is not sufficient."
                if licenses_dir
                else f"{short} is a Category A licence; attribution is required before shipping but LICENSE / "
                "LICENSE.txt was not updated in this PR."
            )
            found.append(
                {"file": f.path, "licence": licence, "category": "A", "severity": "major", "reason": reason}
            )
    for item in found:
        item["finding_category"] = "Third-party license compliance"
    return found


# --- Step 4: licence headers ------------------------------------------------------------

HEADER_TOOLS = (
    "rat",
    "apache-rat",
    "license-eye",
    "skywalking-eyes",
    "insert-license",
    "license-header",
    "licence-header",
    "license header",
    "licenserc",
)
_SOURCE_EXT = (
    ".py",
    ".java",
    ".scala",
    ".kt",
    ".kts",
    ".groovy",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
    ".rb",
    ".sh",
    ".bash",
    ".pl",
    ".php",
    ".swift",
    ".sql",
    ".lua",
    ".r",
)
_EXEMPT_EXT = (
    ".json",
    ".csv",
    ".tsv",
    ".md",
    ".rst",
    ".txt",
    ".lock",
    ".svg",
    ".png",
    ".jpg",
    ".gif",
    ".ico",
    ".ipynb",
)
_APACHE_HEADER = re.compile(
    r"Licensed to the Apache Software Foundation|SPDX-License-Identifier:\s*Apache-2\.0", re.IGNORECASE
)
_EXCLUSION_FILES = (
    ".rat-excludes",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    ".pre-commit-config.yaml",
    ".licenserc.yaml",
    "licenserc.yaml",
    ".licenserc.yml",
)
_EXCLUDE_LINE = (
    re.compile(r"<exclude>\s*([^<]+?)\s*</exclude>"),
    re.compile(r"^\s*exclude\s*[:=]\s*['\"]?([^'\"#]+)"),
    re.compile(r"^\s*-\s+['\"]?([^'\"#\s]+)"),
)


def header_tool_in_ci(context_names: list[str]) -> bool:
    lowered = [n.lower() for n in context_names]
    return any(tool in name for name in lowered for tool in HEADER_TOOLS)


def _exempt(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    lowered = path.lower()
    return (
        is_legal_file(path)
        or name.lower().startswith("readme")
        or lowered.endswith(_EXEMPT_EXT)
        or "/generated/" in "/" + lowered
        or "/fixtures/" in "/" + lowered
        or "test/resources/" in lowered
    )


def _added_exclusions(files: list[difflib.DiffFile]) -> list[tuple[str, str]]:
    found = []
    for f in files:
        name = f.path.rsplit("/", 1)[-1]
        if name not in _EXCLUSION_FILES:
            continue
        for line in f.added:
            text = line.text.strip()
            if not text or text.startswith("#"):
                continue
            pattern = None
            for regex in _EXCLUDE_LINE:
                match = regex.search(text)
                if match:
                    pattern = match.group(1).strip()
                    break
            if pattern is None and name == ".rat-excludes":
                pattern = text
            if pattern:
                found.append((f.path, pattern))
    return found


def _broad(pattern: str) -> bool:
    """A pattern exempting a whole subtree or file type rather than named files."""
    return "**" in pattern or pattern.endswith("/*") or pattern.startswith("*.") or pattern.endswith("/")


def licence_headers(files: list[difflib.DiffFile], context_names: list[str]) -> list[dict[str, Any]]:
    tooled = header_tool_in_ci(context_names)
    exclusions = _added_exclusions(files)
    found: list[dict[str, Any]] = []
    for config_file, pattern in exclusions:
        if _broad(pattern):
            found.append(
                {
                    "file": config_file,
                    "severity": "minor",
                    "reason": f"The new exclusion pattern '{pattern}' is broader than necessary — it exempts an "
                    "entire subtree of contributor-authored source from header checks; it should be "
                    "scoped to the specific file or files that legitimately require exclusion.",
                }
            )
    for f in files:
        if not f.is_new or not f.added or _exempt(f.path) or not f.path.lower().endswith(_SOURCE_EXT):
            continue
        head = "\n".join(f.head(20))
        has_apache = bool(_APACHE_HEADER.search(head))
        licence = _licence_of(head)
        excluded_by = [p for _, p in exclusions if fnmatch.fnmatch(f.path, p) or f.path == p]
        if excluded_by and not has_apache:
            found.append(
                {
                    "file": f.path,
                    "severity": "major",
                    "excluded_by": excluded_by[0],
                    "reason": f"This PR adds the header-tool exclusion '{excluded_by[0]}' and a file it masks, "
                    "which carries no Apache header — the check passes green by construction. Confirm "
                    "the exclusion is justified (generated, fixture or attributed third-party file); a "
                    "contributor-authored source file needs the header instead.",
                }
            )
            continue
        if licence and not licence.upper().startswith("APACHE") and not _third_party(head):
            found.append(
                {
                    "file": f.path,
                    "severity": "major",
                    "reason": f"This contributor-authored file carries a {licence} SPDX identifier instead of "
                    "Apache-2.0 — the header tooling passes because a header is present, but the "
                    "license identifier is wrong for an ASF project.",
                }
            )
            continue
        if not tooled and not has_apache and licence is None:
            found.append(
                {
                    "file": f.path,
                    "severity": "major",
                    "reason": "No header tooling in CI and this contributor-authored source file is missing the "
                    "required Apache license header.",
                }
            )
    for item in found:
        item["finding_category"] = "License headers"
    return found


# --- Step 2: AGENTS.md discovery ---------------------------------------------------------


def agents_files(paths: list[str], repo_root: Path) -> list[str]:
    """Every `AGENTS.md` between a touched file and the repository root, root included."""
    found: set[str] = set()
    for path in paths:
        parent = Path(path).parent
        while True:
            candidate = repo_root / parent / "AGENTS.md"
            if candidate.is_file():
                found.add((parent / "AGENTS.md").as_posix())
            if parent == Path(".") or str(parent) in ("", "/"):
                break
            parent = parent.parent
    return sorted(found)
