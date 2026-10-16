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

"""First-run welcome guides: when to show one, and what was chosen.

Two kinds ship in `guides/`: `general.md`, for the first run of any Magpie
skill, and `<family>.md`, for the first run of a skill in that family.  When
one is due, the pre-flight reports a `welcome` finding carrying it.  At most
one guide per run, chosen by `due_guide`.  The agent shows it, offers three
choices, and records the answer here, in the personal layer's
`reconciled.json` under `welcome.<family>` (`welcome.general` for the
general guide):

* **`seen`** — shown again on the next run, up to `MAX_SEEN` recorded
  showings in all, then not again;
* **`dismiss`** — hidden until the framework version changes;
* **`never`** — hidden until `enable` clears it.

Which family a skill belongs to comes from its frontmatter `family:`, which
a marketplace install cannot read from here (the copy of this package in
the personal layer carries no skills), so it is generated into
`families.py` by `write-constant`, kept current by `check-family-plugins`.

Run as a module:

    python3 -m setup_preflight.welcome list
    python3 -m setup_preflight.welcome show   --family general [--color[=auto|always|never]]
    python3 -m setup_preflight.welcome record --family security --choice seen|dismiss|never
    python3 -m setup_preflight.welcome enable --family security
    python3 -m setup_preflight.welcome write-constant      # framework repo only (prek)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import TextIO

from .isolated import NoPersonalLayer, _load_stamp, _stamp_path
from .layers import personal_dir

HERE = Path(__file__).resolve().parent
GUIDES_DIR = HERE / "guides"
SECTIONS_DIR = HERE / "sections"
BLOCK = "welcome"
#: The guide for every Magpie skill, shown before any family's.
GENERAL = "general"
#: The one rules section every welcome finding names.
SECTION = "welcome"
#: Replaced in a guide by the list of family guides that ship.
_FAMILY_LIST_MARKER = "<!-- family guides: generated from guides/ -->"
#: Replaced in a guide by `guides/_footer.md`, filled in for that guide.
_FOOTER_MARKER = "<!-- welcome footer: generated from guides/_footer.md -->"
CHOICES = ("seen", "dismiss", "never")
#: How many recorded `seen` showings before the guide stops on its own.
MAX_SEEN = 3

_LICENCE_RE = re.compile(r"\A<!--\s*SPDX-License-Identifier.*?-->\s*", re.S)
_PLUGIN_JSON = Path("plugins") / "magpie-setup" / ".claude-plugin" / "plugin.json"
SNAPSHOT_DIR = ".apache-magpie"


# --- which family, which guide ------------------------------------------------------


def family_of(skill: str) -> str | None:
    """The family of `skill`: its frontmatter `name:`, or `magpie-<mirror name>`.

    Exact keys only.  A bare mirror name can collide with another family's
    frontmatter name (`skills/issue-triage` is the issue family's `triage`,
    while `issue-triage` is the security family's), so mirror names are
    keyed only with the `magpie-` prefix a pinned-snapshot install uses.
    """
    try:
        from .families import SKILL_FAMILIES
    except ImportError:
        return None
    return SKILL_FAMILIES.get(skill)


def guides() -> list[str]:
    """Every guide that ships: `general` and each family's (`_`-files are partials)."""
    return sorted(p.stem for p in GUIDES_DIR.glob("*.md") if not p.name.startswith("_"))


def family_guides() -> list[str]:
    return [name for name in guides() if name != GENERAL]


def _family_list() -> str:
    return "\n".join(f"- `{name}` — `/magpie-setup:welcome-guide {name}`" for name in family_guides())


def _read(path: Path) -> str:
    return _LICENCE_RE.sub("", path.read_text(encoding="utf-8")).strip() + "\n"


def _footer(family: str) -> str:
    """The shared footer, for `family`: one copy of the choices and the way back."""
    general = family == GENERAL
    return (
        _read(GUIDES_DIR / "_footer.md")
        .replace("{{label}}", "Magpie" if general else family)
        .replace("{{arg}}", " [<family>]" if general else f" {family}")
        .replace("{{guide}}", family)
        .strip()
    )


def guide(family: str) -> str | None:
    """The guide's Markdown without its licence header, or `None`.

    The family-guide marker becomes the list of family guides that ship, so
    the general guide never names one that does not exist, and the footer
    marker becomes the shared footer filled in for this guide.
    """
    if family not in guides():
        return None
    path = GUIDES_DIR / f"{family}.md"
    text = _read(path).replace(_FAMILY_LIST_MARKER, _family_list())
    return text.replace(_FOOTER_MARKER, _footer(family))


# --- the version a dismissal is tied to ---------------------------------------------


def _plugin_version(path: Path) -> str | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict) or loaded.get("name") != "magpie-setup":
        return None
    version = loaded.get("version")
    return version if isinstance(version, str) and version else None


def _package_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in sorted(HERE.rglob("*")):
        relative = path.relative_to(HERE)
        if not path.is_file() or "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "checker:" + digest.hexdigest()[:16]


def framework_stamp(root: Path) -> str:
    """The framework version this checker belongs to, as one comparable string.

    The `magpie-setup` plugin version when one can be read: beside this
    package (a plugin or framework tree), in the project's own framework
    tree, or in its pinned snapshot.  Otherwise — the copy in the personal
    layer of a marketplace install, which carries no manifest — the
    fingerprint of this package, which `/magpie-setup:setup upgrade`
    refreshes, so a dismissal lifts when an upgrade changes the checker.
    """
    for candidate in (
        HERE.parents[2] / ".claude-plugin" / "plugin.json",
        root / _PLUGIN_JSON,
        root / SNAPSHOT_DIR / _PLUGIN_JSON,
    ):
        version = _plugin_version(candidate)
        if version:
            return version
    return _package_fingerprint()


# --- the decision -------------------------------------------------------------------


def _state(root: Path, family: str) -> dict[str, object] | None:
    raw = _load_stamp(root).get(BLOCK)
    entry = raw.get(family) if isinstance(raw, dict) else None
    return entry if isinstance(entry, dict) else None


def _shown(state: dict[str, object] | None) -> int:
    value = state.get("shown") if state else None
    return value if isinstance(value, int) and value >= 0 else 0


def reason_to_show(state: dict[str, object] | None, stamp: str) -> str | None:
    """Why the guide is due (`first-run`, `again`, `upgraded`), or `None`."""
    choice = state.get("choice") if state else None
    if choice == "never":
        return None
    if choice == "dismiss":
        return "upgraded" if state and state.get("version") != stamp else None
    if choice == "seen":
        return "again" if _shown(state) < MAX_SEEN else None
    return "first-run"


def due_guide(root: Path, skill: str) -> tuple[str, str, dict[str, object] | None] | None:
    """`(guide, reason, state)` for the one guide this run shows, or `None`.

    The candidates are the general guide and the skill's family guide.  A
    first showing beats a repeat, and between equals the general guide goes
    first.  So the general guide opens the very first run, the family guide's
    first showing comes on the next run of a skill in that family, and the
    repeats take turns rather than one starving the other.
    """
    family = family_of(skill)
    if family is None:
        return None
    stamp = framework_stamp(root)
    due: list[tuple[str, str, dict[str, object] | None]] = []
    for name in (GENERAL, family):
        if guide(name) is None:
            continue
        state = _state(root, name)
        reason = reason_to_show(state, stamp)
        if reason is not None:
            due.append((name, reason, state))
    first = [entry for entry in due if entry[1] == "first-run"]
    chosen = first or due
    return chosen[0] if chosen else None


def welcome_facts(root: Path, skill: str) -> tuple[str, dict[str, object]] | None:
    """`(section, facts)` when a guide is due on this run, else `None`.

    Silent for a skill that is not a Magpie skill, when the rules section is
    missing, and when there is no personal layer to record a choice in (an
    unadopted project outside a git repository): a guide that could never
    be dismissed would repeat on every run.
    """
    if not (SECTIONS_DIR / f"{SECTION}.md").is_file() or personal_dir(root) is None:
        return None
    chosen = due_guide(root, skill)
    if chosen is None:
        return None
    name, reason, state = chosen
    return SECTION, {
        "family": name,
        "reason": reason,
        "shown": _shown(state),
        "max_shown": MAX_SEEN,
        "guide": guide(name),
    }


# --- recording ----------------------------------------------------------------------


def _write_stamp(root: Path, stamp: dict[str, object]) -> None:
    path = _stamp_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def record(root: Path, family: str, choice: str, today: date | None = None) -> dict[str, object]:
    """Merge the user's choice into `welcome.<family>`; every other key is kept.

    `seen` counts one more showing; `dismiss` and `never` leave the count
    alone, so a `seen` recorded on display and replaced by the user's later
    answer is still one showing.
    """
    if choice not in CHOICES:
        raise ValueError(f"unknown choice {choice!r}; expected one of {CHOICES}")
    stamp = _load_stamp(root)
    raw = stamp.get(BLOCK)
    block: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    previous = block.get(family)
    shown = _shown(previous if isinstance(previous, dict) else None)
    entry: dict[str, object] = {
        "choice": choice,
        "version": framework_stamp(root),
        "at": (today or date.today()).isoformat(),
        "shown": shown + 1 if choice == "seen" else shown,
    }
    block[family] = entry
    stamp[BLOCK] = block
    _write_stamp(root, stamp)
    return entry


def enable(root: Path, family: str) -> bool:
    """Forget the choice, so the guide shows on the next run.  `True` if one existed."""
    stamp = _load_stamp(root)
    raw = stamp.get(BLOCK)
    if not isinstance(raw, dict) or family not in raw:
        return False
    block = dict(raw)
    del block[family]
    if block:
        stamp[BLOCK] = block
    else:
        del stamp[BLOCK]
    _write_stamp(root, stamp)
    return True


# --- showing it in a terminal -------------------------------------------------------

_RESET = "\033[0m"
_STYLES = {
    "h1": "\033[1;35m",
    "h2": "\033[1;36m",
    "bold": "\033[1m",
    "italic": "\033[3m",
    "code": "\033[33m",
    "quote": "\033[2m",
    "block": "\033[32m",
}
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<![*\w])\*([^*\s][^*]*?)\*(?![*\w])")
_CODE_RE = re.compile(r"`([^`]+)`")


def use_color(mode: str, stream: TextIO, env: dict[str, str] | None = None) -> bool:
    """Colour or not: `never`, `always` (unless NO_COLOR), `auto` (a tty, unless NO_COLOR).

    NO_COLOR set to any non-empty value wins over everything (no-color.org).
    """
    environ = os.environ if env is None else env
    if environ.get("NO_COLOR", ""):
        return False
    if mode == "always":
        return True
    if mode == "auto":
        isatty = getattr(stream, "isatty", None)
        return bool(isatty and isatty())
    return False


def _paint(style: str, text: str, color: bool) -> str:
    return f"{_STYLES[style]}{text}{_RESET}" if color else text


def _inline(text: str, color: bool) -> str:
    text = _CODE_RE.sub(lambda m: _paint("code", m.group(1), color), text)
    text = _BOLD_RE.sub(lambda m: _paint("bold", m.group(1), color), text)
    return _ITALIC_RE.sub(lambda m: _paint("italic", m.group(1), color), text)


def render_terminal(markdown: str, color: bool) -> str:
    """The guide laid out for a terminal; escape codes only when `color`."""
    out: list[str] = []
    in_block = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            in_block = not in_block
            continue
        if in_block:
            out.append("    " + _paint("block", line, color))
        elif line.startswith("# "):
            out.append(_paint("h1", line[2:], color))
        elif line.startswith("## "):
            out.append(_paint("h2", line[3:], color))
        elif line.startswith("> "):
            out.append(_paint("quote", "│ " + _inline(line[2:], False), color))
        elif line.lstrip().startswith("- "):
            indent = len(line) - len(line.lstrip())
            out.append(" " * indent + "  • " + _inline(line.lstrip()[2:], color))
        else:
            out.append(_inline(line, color))
    return "\n".join(out).rstrip() + "\n"


# --- the generated family map -------------------------------------------------------

CONSTANT_PATH = HERE / "families.py"
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_KEY_RE = r"^{key}:\s*([A-Za-z0-9_.-]+)\s*$"
_CONSTANT_HEADER = '''\
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

"""Generated by `python -m setup_preflight.welcome write-constant`. Do not edit.

Each skill's frontmatter `family:`, keyed by its frontmatter `name:` and by
`magpie-<skills/ mirror name>`, for installs that carry no skills (see `welcome.py`).
"""

SKILL_FAMILIES: dict[str, str] = {
'''


def scan_families(base: Path) -> dict[str, str]:
    """`{skill name: family}` from every plugin skill's frontmatter under `base`."""
    found: dict[str, str] = {}
    by_dir: dict[Path, str] = {}
    for skill_md in sorted(base.glob("plugins/magpie-*/skills/*/SKILL.md")):
        match = _FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
        if not match:
            continue
        name = re.search(_KEY_RE.format(key="name"), match.group(1), re.M)
        family = re.search(_KEY_RE.format(key="family"), match.group(1), re.M)
        if name and family:
            found[name.group(1)] = family.group(1)
            by_dir[skill_md.parent.resolve()] = family.group(1)
    mirror = base / "skills"
    if mirror.is_dir():
        for link in sorted(mirror.iterdir()):
            target = link.resolve()
            if target in by_dir:
                found.setdefault(f"magpie-{link.name}", by_dir[target])
    return dict(sorted(found.items()))


def render_constant(mapping: dict[str, str]) -> str:
    body = "".join(f"    {json.dumps(k)}: {json.dumps(v)},\n" for k, v in mapping.items())
    return _CONSTANT_HEADER + body + "}\n"


# --- the command --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.welcome", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="print the guides that ship, one per line")
    show = sub.add_parser("show", help="print a family's welcome guide")
    show.add_argument("--family", required=True)
    show.add_argument(
        "--color",
        nargs="?",
        const="auto",
        choices=["auto", "always", "never"],
        help="terminal rendering; colour on a tty unless NO_COLOR (always: off a tty too)",
    )
    rec = sub.add_parser("record", help="record the user's answer to the guide")
    rec.add_argument("--family", required=True)
    rec.add_argument("--choice", required=True, choices=CHOICES)
    rec.add_argument("--project-root", default=".", type=Path)
    ena = sub.add_parser("enable", help="show the guide again on the next run")
    ena.add_argument("--family", required=True)
    ena.add_argument("--project-root", default=".", type=Path)
    for name in ("write-constant", "check-constant"):
        gen = sub.add_parser(name, help="framework repo only: the generated family map")
        gen.add_argument("--project-root", default=".", type=Path)
    args = parser.parse_args(argv)

    if args.action in ("write-constant", "check-constant"):
        mapping = scan_families(args.project_root)
        if not mapping:
            print(f"{args.action}: no plugin skills under {args.project_root}", file=sys.stderr)
            return 2
        wanted = render_constant(mapping)
        have = CONSTANT_PATH.read_text(encoding="utf-8") if CONSTANT_PATH.exists() else ""
        if have == wanted:
            return 0
        if args.action == "check-constant":
            print(f"{CONSTANT_PATH.name} is stale; run write-constant", file=sys.stderr)
            return 1
        CONSTANT_PATH.write_text(wanted, encoding="utf-8")
        print(f"{CONSTANT_PATH.name}: {len(mapping)} skills")
        return 1  # a fixer that changed a file fails the hook, as prek expects

    if args.action == "list":
        print("\n".join(guides()))
        return 0

    if guide(args.family) is None:
        print(f"{args.action}: no welcome guide for {args.family!r}; have {guides()}", file=sys.stderr)
        return 2

    if args.action == "show":
        text = guide(args.family) or ""
        if args.color:
            text = render_terminal(text, use_color(args.color, sys.stdout))
        sys.stdout.write(text)
        return 0

    try:
        if args.action == "record":
            entry = record(args.project_root, args.family, args.choice)
            print(json.dumps({BLOCK: {args.family: entry}}, indent=2, sort_keys=True))
            return 0
        cleared = enable(args.project_root, args.family)
    except NoPersonalLayer as exc:
        print(f"{args.action}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"family": args.family, "enabled": True, "cleared": cleared}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
