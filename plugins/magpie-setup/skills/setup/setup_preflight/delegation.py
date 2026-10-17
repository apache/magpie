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

"""Which skill actually does a Magpie skill's work: delegation to project skills.

An adopter that already has its own skill for something a Magpie skill does
(its own triage skill, its own create-PR skill) declares a `delegate:` block
in that Magpie skill's override file — the same `<override-name>.md` the
override chain already resolves (`layers.config_layers`):

    ---
    delegate:
      skill: triage-reports          # the project's own skill
      path: .claude/skills/triage-reports/SKILL.md   # optional
      mode: merge                    # replace | merge | before | after
      steps:                         # merge only: the confirmed order
        - magpie: Step 1 — Gather
        - project: Reproduce locally
        - magpie: Step 2 — Classify
        - skip: Step 3 — Label
      why: one line on why the project does it its own way
    ---

`resolve()` answers, for one Magpie skill, which skill does the work, in
which mode, with which steps, and from which file.  The first layer whose
file carries a `delegate:` key decides, personal before committed, exactly
as the rest of the chain resolves; `delegate: off` in the personal layer
opts one person out of a committed delegation.

The block is parsed strictly and refused whole rather than half-applied:
unknown keys, a malformed line, a delegate that names a Magpie skill, a
project skill that is not in the project, a merge that would skip a
baseline step (pre-flight, golden rules, confirmation, scrubs, privacy
gate).  A refused delegate means the framework default runs and the reason
is reported.  Nothing a delegate says can remove the wrapper the Magpie
skill keeps around it; the rules for that wrapper are `sections/step-13.md`.

Stdlib only, and never spawns anything: this runs inside the pre-flight.

    python3 -m setup_preflight.delegation resolve <override-name> [--project-root .]
    python3 -m setup_preflight.delegation list [--project-root .]
    python3 -m setup_preflight.delegation render --skill … --delegate … --mode … [--step kind:ref]…
    python3 -m setup_preflight.delegation write-names | check-names   # framework repo only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .core import Finding
from .layers import OVERRIDES_DIR, config_layers

MODES = ("replace", "merge", "before", "after")
#: `delegate: off` in a file: no delegation from this layer down.
OFF_VALUES = frozenset({"off", "none", "framework"})
KEYS = frozenset({"skill", "path", "mode", "steps", "why"})
STEP_KINDS = ("magpie", "project", "skip")
#: Where a project keeps its own skills.  `magpie-*` entries are Magpie's.
PROJECT_SKILL_DIRS = (".claude/skills", ".agents/skills", ".github/skills")
SNAPSHOT_DIR = ".apache-magpie"
#: A merge may skip an ordinary Magpie step, never one of these.  Matched
#: against the lowercased step reference, so `Step 0 — Pre-flight` and
#: `Golden rule 3` are both caught.
BASELINE_MARKERS = (
    "golden",
    "pre-flight",
    "preflight",
    "confirm",
    "scrub",
    "privacy",
    "redact",
    "external content",
    "external-content",
    "hitl",
    "human-in-the-loop",
    "guardrail",
)
#: The rules section a delegation finding names.
SECTION = "step-13"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
_STEP_RE = re.compile(r"^(magpie|project|skip)\s*:\s*(.+)$")


class MalformedDelegate(ValueError):
    """The block could not be read as the documented shape."""


@dataclass(frozen=True)
class Step:
    kind: str  # "magpie" | "project" | "skip"
    ref: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "ref": self.ref}


@dataclass(frozen=True)
class Resolution:
    """Who does one Magpie skill's work."""

    skill: str
    status: str  # "default" | "delegated" | "refused" | "opted-out"
    delegate: str | None = None
    path: str | None = None
    mode: str | None = None
    steps: tuple[Step, ...] = field(default_factory=tuple)
    source: str | None = None
    layer: str | None = None  # "personal" | "committed"
    reason: str | None = None
    why: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "skill": self.skill,
            "status": self.status,
            "delegate": self.delegate,
            "path": self.path,
            "mode": self.mode,
            "steps": [s.to_dict() for s in self.steps],
            "source": self.source,
            "layer": self.layer,
            "reason": self.reason,
            "why": self.why,
        }


# --- names ------------------------------------------------------------------------


def _names() -> dict[str, str]:
    try:
        from .skill_names import FRONTMATTER_TO_OVERRIDE
    except ImportError:  # pragma: no cover - a partial copy of the package
        return {}
    return dict(FRONTMATTER_TO_OVERRIDE)


def override_names() -> frozenset[str]:
    return frozenset(_names().values())


def override_name(name: str) -> str:
    """The override-file name for a skill named by frontmatter or override name.

    The frontmatter reading wins where a string is both (`issue-triage`):
    the pre-flight passes frontmatter names, and the hand-off CLI is
    documented to take override names, which never collide the other way.
    """
    names = _names()
    return names.get(name, name)


def delegatable(skill: str) -> bool:
    """Setup-family skills run no pre-flight, so no wrapper could hold a delegate."""
    return not (skill == "setup" or skill.startswith("setup-"))


# --- parsing ----------------------------------------------------------------------


def _strip_comment(text: str) -> str:
    quote: str | None = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    if value[:1] in ("{", "[", "&", "*", "|", ">", "!", "@", "`"):
        raise MalformedDelegate(f"unsupported value {value!r}: use a plain or quoted string")
    return value


def frontmatter(text: str) -> list[str] | None:
    """The lines between a leading `---` and the next `---`, or `None`."""
    lines = text.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines) or lines[start].strip() != "---":
        return None
    for end in range(start + 1, len(lines)):
        if lines[end].strip() == "---":
            return lines[start + 1 : end]
    return None


def _flow_mapping(text: str) -> dict[str, object]:
    inner = text.strip()
    if not (inner.startswith("{") and inner.endswith("}")):
        raise MalformedDelegate("a one-line delegate must be a `{ key: value, … }` mapping")
    data: dict[str, object] = {}
    body = inner[1:-1].strip()
    if not body:
        return data
    for part in body.split(","):
        m = _KEY_RE.match(part.strip())
        if not m:
            raise MalformedDelegate(f"cannot read {part.strip()!r} in the one-line delegate")
        key, value = m.group(1), m.group(2)
        if key in data:
            raise MalformedDelegate(f"duplicate key {key!r}")
        if key == "steps":
            raise MalformedDelegate("`steps` needs the block form, one `- kind: ref` per line")
        data[key] = _scalar(value)
    return data


def parse_block(lines: list[str]) -> dict[str, object] | str | None:
    """The `delegate:` value from frontmatter lines.

    `None` when the frontmatter has no `delegate:` key, `"off"` for an
    explicit opt-out, else the mapping.  Raises `MalformedDelegate`.
    """
    index = next((i for i, raw in enumerate(lines) if re.match(r"^delegate\s*:", raw)), None)
    if index is None:
        return None
    rest = _strip_comment(lines[index].split(":", 1)[1].strip())
    if rest:
        if rest.startswith("{"):
            return _flow_mapping(rest)
        if _scalar(rest).lower() in OFF_VALUES:
            return "off"
        raise MalformedDelegate(f"`delegate: {rest}` is neither `off` nor a mapping")

    data: dict[str, object] = {}
    base: int | None = None
    steps: list[Step] | None = None
    for raw in lines[index + 1 :]:
        if not raw.strip():
            continue
        if not raw[:1].isspace():
            break  # the next top-level key: the block has ended
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise MalformedDelegate("indent with spaces, not tabs")
        text = _strip_comment(raw.strip())
        if not text:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if base is None:
            base = indent
        if indent == base:
            km = _KEY_RE.match(text)
            if not km:
                raise MalformedDelegate(f"cannot read {text!r}")
            key, value = km.group(1), km.group(2)
            if key in data:
                raise MalformedDelegate(f"duplicate key {key!r}")
            if key == "steps":
                if value and value != "[]":
                    raise MalformedDelegate("`steps` needs the block form, one `- kind: ref` per line")
                steps = []
                data[key] = steps
            else:
                if not value:
                    raise MalformedDelegate(f"`{key}` has no value")
                data[key] = _scalar(value)
                steps = None
        elif indent > base and steps is not None and text.startswith("- "):
            sm = _STEP_RE.match(text[2:].strip())
            if not sm:
                raise MalformedDelegate(f"a step is `- magpie|project|skip: <ref>`, not {text!r}")
            steps.append(Step(sm.group(1), _scalar(sm.group(2))))
        else:
            raise MalformedDelegate(f"unexpected line {text!r}")
    return data


# --- validation -------------------------------------------------------------------


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def find_project_skill(root: Path, name: str, path: str | None) -> tuple[str | None, str | None]:
    """`(repo-relative SKILL.md path, None)` or `(None, why not)`."""
    real_root = Path(os.path.realpath(root))
    if path is not None:
        rel = Path(path)
        if rel.is_absolute() or ".." in rel.parts:
            return None, f"path {path!r} must be relative to the repository, without `..`"
        if rel.name != "SKILL.md":
            return None, f"path {path!r} must name a SKILL.md"
        candidates = [rel]
    else:
        candidates = [Path(d) / name / "SKILL.md" for d in PROJECT_SKILL_DIRS]
    for rel in candidates:
        full = root / rel
        if not full.is_file():
            continue
        real = Path(os.path.realpath(full))
        if not _inside(real, real_root):
            return None, f"{rel} resolves outside the repository; it is not the project's own skill"
        if _inside(real, real_root / SNAPSHOT_DIR):
            return None, f"{rel} is inside the Magpie snapshot, not a project skill"
        return rel.as_posix(), None
    where = path if path is not None else ", ".join(f"{d}/{name}/SKILL.md" for d in PROJECT_SKILL_DIRS)
    return None, f"project skill {name!r} not found ({where})"


def is_baseline(ref: str) -> bool:
    low = ref.lower()
    return any(marker in low for marker in BASELINE_MARKERS)


def validate(data: dict[str, object], root: Path, skill: str, source: str, layer: str) -> Resolution:
    """A parsed block → `delegated`, or `refused` with the first reason found."""

    def refuse(reason: str) -> Resolution:
        return Resolution(skill, "refused", source=source, layer=layer, reason=reason)

    unknown = sorted(set(data) - KEYS)
    if unknown:
        return refuse(f"unknown key(s) {', '.join(unknown)}; a delegate takes only {', '.join(sorted(KEYS))}")
    if not delegatable(skill):
        return refuse(f"{skill} is a setup-family skill: it runs no pre-flight, so it cannot be delegated")
    name = data.get("skill")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        return refuse("`skill` must name the project's skill (letters, digits, `.`, `_`, `-`)")
    if name.startswith("magpie-") or name in override_names():
        return refuse(f"`skill: {name}` names a Magpie skill; delegate only to the project's own skills")
    mode = data.get("mode")
    if mode not in MODES:
        return refuse(f"`mode` must be one of {', '.join(MODES)}")
    raw_steps = data.get("steps")
    steps: tuple[Step, ...] = ()
    if mode == "merge":
        if not isinstance(raw_steps, list) or not raw_steps:
            return refuse("a merge needs the confirmed `steps:` list")
        steps = tuple(s for s in raw_steps if isinstance(s, Step))
        kinds = {s.kind for s in steps}
        if "magpie" not in kinds or "project" not in kinds:
            return refuse("a merge interleaves Magpie and project steps; with only one side use replace")
        removed = [s.ref for s in steps if s.kind == "skip" and is_baseline(s.ref)]
        if removed:
            return refuse(
                f"the merge would skip a baseline step ({'; '.join(removed)}), which no delegate may remove"
            )
    elif raw_steps not in (None, []):
        return refuse(f"`steps` belongs to a merge only, not to mode {mode}")
    path = data.get("path")
    if path is not None and not isinstance(path, str):
        return refuse("`path` must be a string")
    found, why_not = find_project_skill(root, name, path)
    if found is None:
        return refuse(why_not or "project skill not found")
    why = data.get("why")
    return Resolution(
        skill,
        "delegated",
        delegate=name,
        path=found,
        mode=str(mode),
        steps=steps,
        source=source,
        layer=layer,
        why=why if isinstance(why, str) else None,
    )


# --- resolution -------------------------------------------------------------------


def _layer_kind(layer: Path) -> str:
    return "committed" if layer.name == OVERRIDES_DIR else "personal"


def resolve(root: Path, skill: str) -> Resolution:
    """The effective skill for `skill` (an override name), first declaring layer wins."""
    skill = override_name(skill)
    for layer in config_layers(root):
        candidate = layer / f"{skill}.md"
        if not candidate.is_file():
            continue
        source, kind = str(candidate), _layer_kind(layer)
        try:
            lines = frontmatter(candidate.read_text(encoding="utf-8"))
            block = parse_block(lines) if lines is not None else None
        except (OSError, UnicodeDecodeError) as exc:
            return Resolution(skill, "refused", source=source, layer=kind, reason=f"unreadable: {exc}")
        except MalformedDelegate as exc:
            return Resolution(skill, "refused", source=source, layer=kind, reason=f"malformed: {exc}")
        if block is None:
            continue  # this file overrides without delegating; look further down
        if block == "off":
            return Resolution(skill, "opted-out", source=source, layer=kind)
        assert isinstance(block, dict)
        return validate(block, root, skill, source, kind)
    return Resolution(skill, "default")


def declared(root: Path) -> list[Resolution]:
    """Every Magpie skill whose override chain carries a `delegate:` key."""
    known = override_names()
    names: set[str] = set()
    for layer in config_layers(root):
        if not layer.is_dir():
            continue
        names.update(p.stem for p in layer.glob("*.md") if p.stem in known)
    found = [resolve(root, name) for name in sorted(names)]
    return [r for r in found if r.status != "default"]


def findings(root: Path, skill: str) -> list[Finding]:
    """The pre-flight's delegation findings for the invoked skill (frontmatter name)."""
    own_name = override_name(skill)
    everything = declared(root)
    result: list[Finding] = []
    for entry in everything:
        if entry.skill != own_name:
            continue
        if entry.status == "delegated":
            result.append(Finding("skill", "delegated", SECTION, entry.to_dict()))
        elif entry.status == "refused":
            result.append(Finding("skill", "delegate-refused", SECTION, entry.to_dict()))
    others = {
        e.skill: {"delegate": e.delegate, "path": e.path, "mode": e.mode, "source": e.source}
        for e in everything
        if e.status == "delegated" and e.skill != own_name
    }
    if others:
        result.append(Finding("skill", "handoff-delegates", SECTION, {"delegates": others}))
    return result


# --- rendering --------------------------------------------------------------------


def _quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._/()\u2014\u2013-]*", value) and ": " not in value:
        return value
    return json.dumps(value, ensure_ascii=False)


def render(
    delegate: str, mode: str, path: str | None = None, steps: list[Step] | None = None, why: str | None = None
) -> str:
    """The frontmatter block for a confirmed delegation, ready to write."""
    lines = ["---", "delegate:", f"  skill: {_quote(delegate)}"]
    if path:
        lines.append(f"  path: {_quote(path)}")
    lines.append(f"  mode: {mode}")
    if steps:
        lines.append("  steps:")
        lines.extend(f"    - {s.kind}: {_quote(s.ref)}" for s in steps)
    if why:
        lines.append(f"  why: {_quote(why)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# --- the generated name table (framework repo only) ---------------------------------

NAMES_PATH = Path(__file__).with_name("skill_names.py")
_NAMES_TEMPLATE = '''# Licensed to the Apache Software Foundation (ASF) under one
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

"""Generated by `python3 -m setup_preflight.delegation write-names`. Do not edit.

Each framework skill's frontmatter `name:` (what the pre-flight passes as
`--skill`) mapped to the name its override file carries (`skills/<name>`
in the framework).  The two differ (`pr-triage` is `pr-management-triage`),
and one string can be a frontmatter name and another skill's override name
(`issue-triage`), so the mapping is shipped rather than guessed.
"""

FRONTMATTER_TO_OVERRIDE: dict[str, str] = {{
{rows}
}}
'''


def tree_names(framework_root: Path) -> dict[str, str]:
    """Frontmatter name → `skills/<entry>` name, read from a framework checkout."""
    mapping: dict[str, str] = {}
    for entry in sorted((framework_root / "skills").iterdir()):
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        lines = frontmatter(skill_md.read_text(encoding="utf-8")) or []
        for line in lines:
            m = re.match(r"^name:\s*(\S+)\s*$", line)
            if m:
                mapping[m.group(1)] = entry.name
                break
    return mapping


def names_source(framework_root: Path) -> str:
    rows = "\n".join(f'    "{k}": "{v}",' for k, v in sorted(tree_names(framework_root).items()))
    return _NAMES_TEMPLATE.format(rows=rows)


# --- CLI --------------------------------------------------------------------------


def _parse_step(text: str) -> Step:
    m = _STEP_RE.match(text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"a step is kind:ref with kind one of {', '.join(STEP_KINDS)}")
    return Step(m.group(1), m.group(2).strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.delegation", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    p_resolve = sub.add_parser("resolve", help="the effective skill for one Magpie skill")
    p_resolve.add_argument("skill", help="the Magpie skill's override name, e.g. security-issue-triage")
    p_list = sub.add_parser("list", help="every declared delegation")
    p_render = sub.add_parser("render", help="validate a confirmed delegation and print its block")
    p_render.add_argument("--skill", required=True, help="the Magpie skill's override name")
    p_render.add_argument("--delegate", required=True, help="the project skill's name")
    p_render.add_argument("--mode", required=True, choices=MODES)
    p_render.add_argument("--path", default=None)
    p_render.add_argument("--step", action="append", type=_parse_step, default=[], metavar="KIND:REF")
    p_render.add_argument("--why", default=None)
    for p in (p_resolve, p_list, p_render):
        p.add_argument("--project-root", default=".", type=Path)
    for name in ("write-names", "check-names"):
        p = sub.add_parser(name, help="framework repo only: the frontmatter → override name table")
        p.add_argument("--framework-root", default=".", type=Path)
    args = parser.parse_args(argv)

    if args.action == "resolve":
        print(json.dumps(resolve(args.project_root, args.skill).to_dict(), indent=2, sort_keys=True))
        return 0
    if args.action == "list":
        payload = [r.to_dict() for r in declared(args.project_root)]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.action == "render":
        skill = override_name(args.skill)
        data: dict[str, object] = {"skill": args.delegate, "mode": args.mode}
        if args.path:
            data["path"] = args.path
        if args.step:
            data["steps"] = list(args.step)
        checked = validate(data, args.project_root, skill, "<render>", "personal")
        if checked.status != "delegated":
            print(f"render: refused: {checked.reason}", file=sys.stderr)
            return 1
        print(render(args.delegate, args.mode, checked.path, list(args.step), args.why), end="")
        return 0

    wanted = names_source(args.framework_root)
    have = NAMES_PATH.read_text(encoding="utf-8") if NAMES_PATH.exists() else ""
    if have == wanted:
        return 0
    if args.action == "check-names":
        print(f"{NAMES_PATH.name} is stale; run write-names", file=sys.stderr)
        return 1
    NAMES_PATH.write_text(wanted, encoding="utf-8")
    print(f"{NAMES_PATH.name}: rewritten")
    return 1  # a fixer that changed a file fails, as prek expects


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
