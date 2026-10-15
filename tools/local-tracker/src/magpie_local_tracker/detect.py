# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Infer a descriptor from the reports a team already keeps.

Every choice is made from evidence — the names, folders, metadata keys and
headings actually present — and the evidence is returned with the result, so
the person running setup can see why the tool decided what it did and correct
it before anything is written. With no reports present the default
descriptor applies.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import metadata as md
from .descriptor import DESCRIPTOR_NAME, Descriptor, IdFormat, StateFormat

OPEN_WORDS = [
    "open", "new", "triage", "needs-triage", "needs triage", "in-progress", "in progress",
    "active", "accepted", "valid", "confirmed", "pending", "draft", "embargoed",
]  # fmt: skip
CLOSED_WORDS = [
    "closed", "fixed", "resolved", "done", "published", "rejected", "invalid", "wontfix",
    "won't fix", "duplicate", "archive", "archived", "disclosed", "not-planned", "not planned",
]  # fmt: skip
NOT_PLANNED_WORDS = ["rejected", "invalid", "wontfix", "won't fix", "not-planned", "not planned"]

ROLE_SYNONYMS: dict[str, list[str]] = {
    "title": ["title", "summary", "subject"],
    "state": ["state", "status"],
    "labels": ["labels", "tags", "keywords"],
    "assignees": ["assignees", "assignee", "owner", "owners", "handler", "assigned to"],
    "milestone": ["milestone", "target", "fix version", "fix-version", "fix_version", "release"],
    "author": ["reporter", "author", "reported by", "reported-by", "reported_by", "finder"],
    "created": ["created", "date", "reported", "opened", "created_at", "reported on"],
    "updated": ["updated", "last updated", "last-updated", "modified", "updated_at"],
}
# Roles the security skills need even when a team's reports never had them.
REQUIRED_ROLES = ("title", "state", "labels", "assignees", "milestone")

COMMENT_HEADINGS = ["Comments", "Discussion", "Notes", "Timeline", "History", "Log"]
COMMENT_FILES = ["comments.md", "discussion.md", "notes.md", "timeline.md", "history.md"]

_ID_RE = re.compile(r"^(?P<prefix>.*?[-_])?(?P<num>\d+)(?:[-_](?P<slug>[A-Za-z].*))?$")


def _candidates(base: Path) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    folders: list[Path] = []
    if not base.is_dir():
        return files, folders
    for child in sorted(base.iterdir()):
        if child.name.startswith(".") or child.name.lower() in {"readme.md", "index.md", "template.md"}:
            continue
        if child.is_file() and child.suffix == ".md" and _ID_RE.match(child.stem):
            files.append(child)
        elif child.is_dir() and _ID_RE.match(child.name) and any(child.glob("*.md")):
            folders.append(child)
    return files, folders


def _is_word(name: str, words: list[str]) -> bool:
    return name.lower().replace("_", "-") in {w.replace(" ", "-") for w in words} or name.lower() in words


def detect(root: Path) -> tuple[Descriptor, dict[str, object]]:
    desc = Descriptor()
    evidence: dict[str, object] = {"root": str(root), "reports_found": 0, "decisions": []}
    decisions: list[str] = evidence["decisions"]  # type: ignore[assignment]

    if not root.is_dir() or not [p for p in root.iterdir() if p.name != DESCRIPTOR_NAME]:
        decisions.append("no existing reports — using the default format (folder per report, front matter)")
        evidence["confidence"] = "default"
        return desc, evidence

    # 1. State folders.
    state_dirs = [
        d
        for d in sorted(root.iterdir())
        if d.is_dir() and (_is_word(d.name, OPEN_WORDS) or _is_word(d.name, CLOSED_WORDS))
    ]
    bases: list[Path] = state_dirs or [root]
    if state_dirs:
        opens = [d.name for d in state_dirs if _is_word(d.name, OPEN_WORDS)]
        closeds = [d.name for d in state_dirs if _is_word(d.name, CLOSED_WORDS)]
        desc.state = StateFormat(
            mode="directory",
            open_dir=opens[0] if opens else "open",
            closed_dir=closeds[0] if closeds else "closed",
            open_values=opens or ["open"],
            closed_values=closeds or ["closed"],
        )
        decisions.append(f"state is the folder a report sits in: open={opens}, closed={closeds}")

    # 2. Layout.
    files: list[Path] = []
    folders: list[Path] = []
    for base in bases:
        f, d = _candidates(base)
        files += f
        folders += d
    if not files and not folders:
        decisions.append("no file or folder named like a report ID — using the default format")
        evidence["confidence"] = "default"
        evidence["unrecognized"] = sorted(p.name for p in root.iterdir())[:20]
        return Descriptor(), evidence

    issue_paths: list[Path]
    if len(folders) > len(files):
        desc.layout = "folder-per-issue"
        names: Counter[str] = Counter()
        same_as_dir = 0
        for folder in folders:
            mds = [p.name for p in folder.glob("*.md") if p.name.lower() not in COMMENT_FILES]
            if f"{folder.name}.md" in mds:
                same_as_dir += 1
            names.update(mds)
        if same_as_dir > len(folders) / 2:
            desc.issue_file = "{id}.md"
        elif names:
            desc.issue_file = names.most_common(1)[0][0]
        issue_paths = [f / desc.issue_file.replace("{id}", f.name) for f in folders]
        issue_paths = [p for p in issue_paths if p.is_file()]
        decisions.append(f"one folder per report ({len(folders)} found), report file {desc.issue_file!r}")
        stems = [f.name for f in folders]
    else:
        desc.layout = "file-per-issue"
        issue_paths = files
        decisions.append(f"one markdown file per report ({len(files)} found)")
        stems = [f.stem for f in files]
        desc.comments_mode = "section"
        desc.rollup_mode = "section"
    evidence["reports_found"] = len(stems)

    # 3. Identifier format.
    matches = [m for m in (_ID_RE.match(s) for s in stems) if m]
    prefixes = Counter(m.group("prefix") or "" for m in matches)
    prefix = prefixes.most_common(1)[0][0]
    nums = [m.group("num") for m in matches if (m.group("prefix") or "") == prefix]
    padded = any(n.startswith("0") for n in nums)
    desc.id = IdFormat(
        prefix=prefix,
        width=max(len(n) for n in nums) if padded else 1,
        slug=any(m.group("slug") for m in matches),
    )
    decisions.append(
        f"IDs look like {desc.id.render(7, 'example')!r} (prefix {prefix!r}, width {desc.id.width}"
        + (", with a title slug" if desc.id.slug else "")
        + ")"
    )
    if len(prefixes) > 1:
        desc.notes.append(f"several ID prefixes in use {dict(prefixes)}; new reports use {prefix!r}")

    # 4. Metadata, keys, state values, headings.
    sample = issue_paths[:60]
    styles: Counter[str] = Counter()
    list_styles: Counter[str] = Counter()
    keys_seen: Counter[str] = Counter()
    state_values: Counter[str] = Counter()
    heading_levels: Counter[int] = Counter()
    h1_titles = 0
    comment_headings: Counter[str] = Counter()
    for path in sample:
        meta, body = md.split(path.read_text(encoding="utf-8", errors="replace"))
        styles[meta.style] += 1
        if meta.style == "front-matter":
            list_styles[meta.list_style] += 1
        keys_seen.update(meta.values.keys())
        skey = meta.find_key(ROLE_SYNONYMS["state"])
        sval = meta.values.get(skey) if skey else None
        if isinstance(sval, str):
            state_values[sval] += 1
        if re.search(r"^# .+$", body, re.MULTILINE):
            h1_titles += 1
        for line in body.split("\n"):
            m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
            if not m:
                continue
            text = m.group(2)
            if text in COMMENT_HEADINGS and len(m.group(1)) == 2:
                comment_headings[text] += 1
            else:
                heading_levels[len(m.group(1))] += 1

    style = styles.most_common(1)[0][0]
    desc.metadata = style if style != "none" else "bold-fields"
    if style == "none":
        desc.notes.append("existing reports carry no metadata block; new reports get **Key:** value lines")
    desc.list_style = list_styles.most_common(1)[0][0] if list_styles else "inline"
    decisions.append(f"metadata style {style!r} ({dict(styles)})")

    capitalised = sum(1 for k in keys_seen if k[:1].isupper()) > len(keys_seen) / 2
    keys: dict[str, str] = {}
    for role, synonyms in ROLE_SYNONYMS.items():
        lowered = {k.lower(): k for k in keys_seen}
        found = next((lowered[s] for s in synonyms if s in lowered), "")
        if not found and role in REQUIRED_ROLES:
            found = role.capitalize() if capitalised else role
            if not (role == "state" and desc.state.mode == "directory"):
                desc.notes.append(
                    f"no {role!r} key in existing reports; new and edited reports add {found!r}"
                )
        if role == "state" and desc.state.mode == "directory" and found not in keys_seen:
            found = ""
        keys[role] = found
    if "title" not in {r for r, k in keys.items() if k in keys_seen} and h1_titles > len(sample) / 2:
        desc.title_source = "h1"
        keys["title"] = ""
        decisions.append("title is the report's first '# ' heading")
    desc.keys = keys
    decisions.append(f"metadata keys: { {r: k for r, k in keys.items() if k} }")

    if state_values:
        opens = [v for v in state_values if _is_word(v, OPEN_WORDS)]
        closeds = [v for v in state_values if _is_word(v, CLOSED_WORDS)]
        unknown = [v for v in state_values if v not in opens and v not in closeds]
        top_open = max(opens, key=lambda v: state_values[v]) if opens else "open"
        top_closed = max(closeds, key=lambda v: state_values[v]) if closeds else "closed"
        not_planned = [v for v in closeds if _is_word(v, NOT_PLANNED_WORDS)]
        st = desc.state
        st.open_value = next((v for v in opens if _is_word(v, ["open", "new"])), top_open)
        st.closed_value = next(
            (v for v in closeds if _is_word(v, ["fixed", "closed", "resolved"])), top_closed
        )
        st.not_planned_value = not_planned[0] if not_planned else st.closed_value
        if st.mode == "directory":
            # The folder decides; the values only keep the key in step with it.
            st.open_values = [*st.open_values, *opens, *unknown]
            st.closed_values = [*st.closed_values, *closeds]
        else:
            st.open_values = opens + unknown or ["open"]
            st.closed_values = closeds or ["closed"]
        decisions.append(f"state values: open={opens}, closed={closeds}")
        if unknown and st.mode == "field":
            desc.notes.append(
                f"state values {unknown} were not recognised and are treated as open — check them"
            )

    if heading_levels:
        desc.field_heading_level = heading_levels.most_common(1)[0][0]
        decisions.append(f"report sections use level-{desc.field_heading_level} headings")

    # 5. Comments.
    if desc.layout == "folder-per-issue":
        files_seen: Counter[str] = Counter(
            p.name for f in folders for p in f.iterdir() if p.name.lower() in COMMENT_FILES
        )
        if files_seen:
            desc.comments_mode = "file"
            desc.comments_file = files_seen.most_common(1)[0][0]
            decisions.append(f"comments live in {desc.comments_file!r} next to the report")
        elif comment_headings:
            desc.comments_mode = "section"
            desc.comments_heading = comment_headings.most_common(1)[0][0]
            decisions.append(f"comments live under '## {desc.comments_heading}' in the report")
    elif comment_headings:
        desc.comments_heading = comment_headings.most_common(1)[0][0]
        decisions.append(f"comments live under '## {desc.comments_heading}' in the report")

    evidence["confidence"] = "high" if not desc.notes else "review"
    evidence["sample_size"] = len(sample)
    return desc, evidence


def describe(desc: Descriptor) -> str:
    """A short human description of the format, for setup's confirmation."""
    where = (
        f"<root>/{desc.id.render(1)}/{desc.issue_file.replace('{id}', desc.id.render(1))}"
        if desc.layout == "folder-per-issue"
        else f"<root>/{desc.id.render(1)}.md"
    )
    if desc.state.mode == "directory":
        where = where.replace("<root>/", f"<root>/{{{desc.state.open_dir}|{desc.state.closed_dir}}}/")
    level = "#" * desc.field_heading_level
    return (
        f"{where}; metadata as {desc.metadata}; fields as '{level} <Field>' sections; "
        f"comments in {'section ' + desc.comments_heading if desc.comments_mode == 'section' else desc.comments_file}"
    )
