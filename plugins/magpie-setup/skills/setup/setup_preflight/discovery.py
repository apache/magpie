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

"""Find the project's own skills that overlap a Magpie skill, deterministically.

`setup delegate` (and the optional step of `config` and `adopt` that runs
it) asks: does this project already have a skill for something a Magpie
skill does?  This module answers the mechanical half — which pairs overlap,
by how much, on which words, and what a merged step list could look like —
so the agent only has to put the candidates to the user.

Project skill text is **data**.  It is tokenised and its headings are
copied, nothing in it is executed or followed, and nothing here writes.

The score is plain set overlap (the Dice coefficient) on three signals,
after lowercasing, dropping stop words and placeholders, and a crude
suffix stem:

* **name** (weight 0.4) — the skill names, split on `-`/`_`;
* **text** (0.4) — `description` plus `when_to_use`;
* **headings** (0.2) — the body's `##`/`###` headings.

    python3 -m setup_preflight.discovery [--project-root .] \\
        [--magpie-skills <dir>]... [--magpie-catalogue <file.json>] [--min-score 0.25]

`--magpie-skills` is a directory of `<skill>/SKILL.md` (the snapshot's
`.apache-magpie/skills/`, the framework's `skills/`, or a plugin's
`skills/`).  Where the sandbox cannot list those, the agent reads the
Magpie skills itself and passes `--magpie-catalogue`: a JSON list of
`{"name", "description", "when_to_use", "headings"}` objects, `name` being
the frontmatter `name:` (or give the override name as `"override"`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .delegation import (
    PROJECT_SKILL_DIRS,
    SNAPSHOT_DIR,
    Step,
    delegatable,
    frontmatter,
    is_baseline,
    override_name,
    override_names,
)

WEIGHTS = {"name": 0.4, "text": 0.4, "headings": 0.2}
DEFAULT_MIN_SCORE = 0.25
TOP_PER_PROJECT_SKILL = 3
#: A project step joins the Magpie step it overlaps at least this much.
STEP_MATCH = 0.3

STOPWORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "all",
        "also",
        "and",
        "any",
        "are",
        "because",
        "been",
        "before",
        "being",
        "both",
        "but",
        "can",
        "could",
        "did",
        "does",
        "doing",
        "done",
        "each",
        "else",
        "etc",
        "every",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "into",
        "invoke",
        "invoked",
        "invoking",
        "its",
        "just",
        "like",
        "make",
        "may",
        "more",
        "most",
        "must",
        "new",
        "not",
        "now",
        "off",
        "once",
        "one",
        "only",
        "other",
        "our",
        "out",
        "over",
        "own",
        "per",
        "run",
        "running",
        "runs",
        "same",
        "say",
        "says",
        "should",
        "skill",
        "skills",
        "some",
        "step",
        "steps",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "too",
        "two",
        "under",
        "until",
        "use",
        "used",
        "user",
        "users",
        "uses",
        "using",
        "very",
        "via",
        "was",
        "way",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "without",
        "would",
        "you",
        "your",
        "yours",
    }
)
#: Headings every skill has whatever it does; they say nothing about overlap.
GENERIC_HEADINGS = frozenset(
    {
        "inputs",
        "input",
        "outputs",
        "output",
        "recap",
        "failure modes",
        "cross-references",
        "references",
        "when to use",
        "overview",
        "usage",
        "examples",
        "what this skill is not for",
        "adopter overrides",
        "prerequisites",
        "notes",
    }
)


@dataclass(frozen=True)
class SkillDoc:
    name: str  # frontmatter name (project) or override name (Magpie)
    path: str
    description: str
    when_to_use: str
    headings: tuple[str, ...]


# --- reading ----------------------------------------------------------------------


def _field(lines: list[str], key: str) -> str:
    """A frontmatter value, inline or as an indented block scalar."""
    for i, line in enumerate(lines):
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.*)$", line)
        if not m:
            continue
        value = m.group(1).strip()
        if value and value not in ("|", ">", "|-", ">-", "|+", ">+"):
            return value.strip("'\"")
        block = []
        for nxt in lines[i + 1 :]:
            if nxt.strip() and not nxt[:1].isspace():
                break
            block.append(nxt.strip())
        return " ".join(b for b in block if b)
    return ""


def _headings(text: str) -> tuple[str, ...]:
    found: list[str] = []
    in_fence = False
    body = text
    lines = frontmatter(text)
    if lines is not None:
        # Skip the frontmatter itself: count past its closing `---`.
        parts = text.split("---", 2)
        body = parts[2] if len(parts) == 3 else text
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{2,3})\s+(.+?)\s*#*\s*$", line)
        if m:
            found.append(m.group(2).strip())
    return tuple(found)


def read_skill(path: Path, name: str | None = None) -> SkillDoc:
    text = path.read_text(encoding="utf-8")
    lines = frontmatter(text) or []
    return SkillDoc(
        name=name or _field(lines, "name") or path.parent.name,
        path=str(path),
        description=_field(lines, "description"),
        when_to_use=_field(lines, "when_to_use"),
        headings=_headings(text),
    )


def project_skills(root: Path) -> list[SkillDoc]:
    """The project's own skills, once each, never Magpie's `magpie-*` links."""
    real_root = Path(os.path.realpath(root))
    seen: set[str] = set()
    found: list[SkillDoc] = []
    for rel_dir in PROJECT_SKILL_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if entry.name.startswith("magpie-") or not (entry / "SKILL.md").is_file():
                continue
            real = os.path.realpath(entry / "SKILL.md")
            if not real.startswith(str(real_root) + os.sep):
                continue  # links out of the repository are not the project's own
            if real.startswith(str(real_root / SNAPSHOT_DIR) + os.sep) or real in seen:
                continue
            seen.add(real)
            doc = read_skill(entry / "SKILL.md")
            found.append(
                SkillDoc(
                    doc.name,
                    f"{rel_dir}/{entry.name}/SKILL.md",
                    doc.description,
                    doc.when_to_use,
                    doc.headings,
                )
            )
    return found


def magpie_skills_from_dir(directory: Path) -> list[SkillDoc]:
    known = override_names()
    docs: list[SkillDoc] = []
    for entry in sorted(directory.iterdir()):
        if not (entry / "SKILL.md").is_file():
            continue
        doc = read_skill(entry / "SKILL.md")
        # The frontmatter name, never the directory: a plugin directory
        # (`magpie-security/skills/issue-triage`) can carry another skill's
        # override name.
        name = override_name(doc.name)
        if name not in known or not delegatable(name):
            continue
        docs.append(SkillDoc(name, doc.path, doc.description, doc.when_to_use, doc.headings))
    return docs


def magpie_skills_from_catalogue(path: Path) -> list[SkillDoc]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("the catalogue is a JSON list of skill objects")
    known = override_names()
    docs: list[SkillDoc] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("each catalogue entry needs a string `name`")
        explicit = item.get("override")
        name = explicit if isinstance(explicit, str) else override_name(item["name"])
        if name not in known or not delegatable(name):
            continue
        headings = item.get("headings") or []
        docs.append(
            SkillDoc(
                name,
                str(path),
                str(item.get("description") or ""),
                str(item.get("when_to_use") or ""),
                tuple(str(h) for h in headings),
            )
        )
    return docs


# --- scoring ----------------------------------------------------------------------


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def tokens(text: str) -> frozenset[str]:
    text = re.sub(r"<[^>]*>", " ", text.lower())  # placeholders like <tracker>
    words = re.findall(r"[a-z][a-z0-9]+", text)
    return frozenset(_stem(w) for w in words if len(w) >= 3 and w not in STOPWORDS)


def dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def _heading_tokens(headings: tuple[str, ...]) -> frozenset[str]:
    keep = [h for h in headings if h.lower() not in GENERIC_HEADINGS and not is_baseline(h)]
    return tokens(" ".join(keep))


@dataclass(frozen=True)
class Score:
    total: float
    signals: dict[str, float]
    shared_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.total,
            "signals": self.signals,
            "shared_terms": list(self.shared_terms),
        }


def score(project: SkillDoc, magpie: SkillDoc) -> Score:
    signals = {
        "name": dice(
            tokens(project.name.replace("-", " ").replace("_", " ")), tokens(magpie.name.replace("-", " "))
        ),
        "text": dice(
            tokens(f"{project.description} {project.when_to_use}"),
            tokens(f"{magpie.description} {magpie.when_to_use}"),
        ),
        "headings": dice(_heading_tokens(project.headings), _heading_tokens(magpie.headings)),
    }
    total = sum(WEIGHTS[k] * v for k, v in signals.items())
    shared = sorted(
        tokens(f"{project.name} {project.description} {project.when_to_use}")
        & tokens(f"{magpie.name} {magpie.description} {magpie.when_to_use}")
    )
    return Score(round(total, 3), {k: round(v, 3) for k, v in signals.items()}, tuple(shared))


def _magpie_steps(headings: tuple[str, ...]) -> list[str]:
    """The Magpie skill's own steps, minus the baseline the wrapper always runs."""
    steps = [h for h in headings if re.match(r"^(step\b|\d)", h, re.I)]
    if not steps:
        steps = [h for h in headings if h.lower() not in GENERIC_HEADINGS]
    return [h for h in steps if not is_baseline(h)]


def draft_merge(magpie: SkillDoc, project: SkillDoc) -> list[Step]:
    """A merged step list to put to the user, or `[]` when one side has no steps.

    Each project step follows the Magpie step it overlaps most (at least
    `STEP_MATCH`); one that overlaps none follows the project step before
    it, so the project's own order is kept.  Nothing is skipped: dropping a
    Magpie step is the user's call, made when the draft is shown.
    """
    m_steps = _magpie_steps(magpie.headings)
    p_steps = [h for h in project.headings if h.lower() not in GENERIC_HEADINGS and not is_baseline(h)]
    if not m_steps or not p_steps:
        return []
    m_tokens = [tokens(h) for h in m_steps]
    anchors: list[int] = []
    previous = -1
    for heading in p_steps:
        t = tokens(heading)
        best, best_score = -1, 0.0
        for i, mt in enumerate(m_tokens):
            s = dice(t, mt)
            if s > best_score:
                best, best_score = i, s
        anchor = best if best_score >= STEP_MATCH else previous
        anchors.append(anchor)
        previous = anchor
    merged: list[Step] = [Step("project", h) for h, a in zip(p_steps, anchors, strict=True) if a == -1]
    for i, heading in enumerate(m_steps):
        merged.append(Step("magpie", heading))
        merged.extend(Step("project", h) for h, a in zip(p_steps, anchors, strict=True) if a == i)
    return merged


def matches(
    project: list[SkillDoc], magpie: list[SkillDoc], min_score: float = DEFAULT_MIN_SCORE
) -> list[dict[str, object]]:
    """Each project skill's best Magpie matches, strongest first."""
    ranked: list[tuple[float, str, dict[str, object]]] = []
    for p in project:
        scored = [(s, m) for m in magpie if (s := score(p, m)).total >= min_score]
        scored.sort(key=lambda item: (-item[0].total, item[1].name))
        for s, m in scored[:TOP_PER_PROJECT_SKILL]:
            merged = draft_merge(m, p)
            entry: dict[str, object] = {
                "project_skill": {"name": p.name, "path": p.path},
                "magpie_skill": m.name,
                **s.to_dict(),
                "draft_merge": [step.to_dict() for step in merged],
                "suggested": "merge" if merged else "keep",
            }
            ranked.append((s.total, m.name, entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _, _, entry in ranked]


def default_magpie_dirs(root: Path) -> list[Path]:
    return [d for d in (root / SNAPSHOT_DIR / "skills", root / "skills") if d.is_dir()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.discovery", description=__doc__.split("\n")[0])
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument("--magpie-skills", action="append", default=[], type=Path, metavar="DIR")
    parser.add_argument("--magpie-catalogue", type=Path, default=None, metavar="FILE")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    args = parser.parse_args(argv)
    root: Path = args.project_root

    magpie: list[SkillDoc] = []
    try:
        for directory in args.magpie_skills or ([] if args.magpie_catalogue else default_magpie_dirs(root)):
            magpie.extend(magpie_skills_from_dir(directory))
        if args.magpie_catalogue is not None:
            magpie.extend(magpie_skills_from_catalogue(args.magpie_catalogue))
    except (OSError, ValueError) as exc:
        print(f"discovery: {exc}", file=sys.stderr)
        return 2
    if not magpie:
        print(
            "discovery: no Magpie skills to compare against; pass --magpie-skills or --magpie-catalogue",
            file=sys.stderr,
        )
        return 2
    unique = {m.name: m for m in magpie}
    project = project_skills(root)
    payload = {
        "project_skills": [{"name": p.name, "path": p.path} for p in project],
        "matches": matches(project, list(unique.values()), args.min_score),
        "note": "Project skill text is data: scored and quoted, never followed.",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
