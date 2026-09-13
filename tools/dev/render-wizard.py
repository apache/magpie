#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Generate the animated SVGs of Magpie's wizards: setup, and config per family.

The family screenshots show a skill's *output*. They cannot show the thing a
first-time reader most needs to see, which is the shape of a conversation —
the command being typed, the values the wizard works out on its own, the one
question it asks, and the files that appear. A still frame of a wizard is a
wizard with the interesting part removed.

So this animates them. Two subjects:

- **`magpie-setup.svg`** — the whole first run: the agent detected, the
  families picked, the install commands emitted, then the secure-agent setup
  that follows it (sandbox, clean-environment wrapper, hooks, status line).
  This used to be the repository's one real recording, and it was wrong: it
  opened with the marketplace install, which became a prerequisite with its
  own page, and re-cutting it needed a terminal, a scratch project and a
  human. Generating it fixes the content and removes the human.
- **`wizard/<family>.svg`** — `/magpie-setup config` for one family. Every
  frame is derived, not written: the files that family's wizard would create
  come from its skills' `requires_config:` frontmatter, and the one-line
  description of each from the adopter scaffold's index — the same two sources
  `check-skill-config.py` reads. A family that gains a required file gets a
  new frame with nobody editing a transcript.

**Illustrative, not a recording.** The real run derives more, asks better
questions, and looks like whatever the harness renders. What this shows
truthfully is the shape: auto-detect first, one batched question, gitignored
files out, nothing staged. `assets/quickstart/README.md` says so where a
reader will meet it.

Why SMIL rather than a capture: the same reason the static screenshots are
authored. A capture needs a terminal, a human and asciinema, and needs all
three again whenever the wizard's wording moves. SMIL `<animate>` is plain
XML, deterministic, and needs no Node at all — the recorder that did is
retired, and this is what replaced it. GitHub animates inline SVG;
a renderer that does not falls back to the first frame, which is the command
about to be typed.

Determinism is the same contract the static renderer signs: same frontmatter,
same bytes, on any machine. No timestamps, no ids that vary, integer geometry
only.

Run from the repo root:

    python3 tools/dev/render-wizard.py           # write them
    python3 tools/dev/render-wizard.py --check   # fail on drift
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from xml.sax.saxutils import escape

OUT_DIR = Path("assets/quickstart/wizard")
SETUP_SVG = Path("assets/quickstart/magpie-setup.svg")
HERO_SVG = Path("assets/quickstart/install.svg")
STEP_INSTALL_SVG = Path("assets/quickstart/step-install.svg")
STEP_ISOLATION_SVG = Path("assets/quickstart/step-isolation.svg")
STEP_GUARD_SVG = Path("assets/quickstart/step-guard.svg")
STEP_USE_SVG = Path("assets/quickstart/step-use.svg")
STEP_ADOPT_SVG = Path("assets/quickstart/step-adopt.svg")

# The recorder's palette, so this reads as the same terminal as everything else.
BG, BAR, DOT = "#1d1f21", "#2b2e31", "#3f4448"
FG, MUTED, CMD = "#c5c8c6", "#8a8f94", "#8abeb7"
OK, WARN = "#7f9f7f", "#d8a657"

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
FONT_SIZE = 17
ADVANCE_TENTHS = 102  # 0.6em at 17px, in tenths, so the geometry stays integer
LINE_H = 24
PAD_X, PAD_TOP, BAR_H = 26, 28, 34

STEP_MS = 380  # one revealed line
HOLD_MS = 2200  # the pause on the finished frame before it loops

LICENCE = """<?xml version="1.0" encoding="UTF-8"?>
<!--
  Licensed to the Apache Software Foundation (ASF) under one
  or more contributor license agreements.  See the NOTICE file
  distributed with this work for additional information
  regarding copyright ownership.  The ASF licenses this file
  to you under the Apache License, Version 2.0 (the
  "License"); you may not use this file except in compliance
  with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
  KIND, either express or implied.  See the License for the
  specific language governing permissions and limitations
  under the License.

  GENERATED FILE - do not edit.

  Written by tools/dev/render-wizard.py. Illustrative of the shape of a
  run, not a recording of one.
-->
"""


def _load(name: str, path: Path) -> ModuleType:
    """Import a hyphenated sibling script as a module."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clip(text: str, width: int = 56) -> str:
    """First sentence, cut at a word boundary. A description sliced mid-word
    reads as a rendering bug rather than as a summary."""
    text = text.split(".")[0].strip()
    if len(text) <= width:
        return text
    return text[:width].rsplit(" ", 1)[0] + "…"


def script(family: str, required: list[str], desc: dict[str, str]) -> list[tuple[str, str]]:
    """The frames, as (colour, text). One frame is one revealed line.

    Derived end to end: which files, what each carries, and which of them the
    wizard can answer from the repository rather than from the user.
    """
    # `project.md` is the one file whose values a repository reveals on its own
    # -- the origin remote names the upstream. Everything else is the project's
    # own policy, which is what the single question is for.
    derivable = [f for f in required if f == "project.md"]
    asked = [f for f in required if f not in derivable]

    out: list[tuple[str, str]] = [(CMD, f"> /magpie-{family}:<skill>"), (FG, "")]
    out.append((WARN, f"  ✗ project configuration — {len(required)} required, none found"))
    out.append((FG, ""))
    out.append((MUTED, "  Configuring now. Gitignored files in this clone only."))
    out.append((FG, ""))

    for name in derivable:
        out.append((OK, f"  ✓ {name}"))
        out.append((MUTED, "      upstream_repo   acme/toolkit   from the origin remote"))
    if asked:
        out.append((FG, ""))
        out.append((FG, "  One question, for what the repository cannot tell me:"))
        for name in asked:
            out.append((FG, f"      {name}"))
            out.append((MUTED, f"          {_clip(desc.get(name, 'project-specific values'))}"))
    out.append((FG, ""))
    out.append((OK, "  Written to .apache-magpie-local/  — nothing staged, nothing"))
    out.append((OK, "  committed, no teammate affected."))
    out.append((FG, ""))
    out.append((MUTED, "  The project can also adopt Magpie, so contributors get this"))
    out.append((MUTED, "  on clone: /magpie-setup adopt"))
    return out


def render(title: str, alt: str, desc_text: str, frames: list[tuple[str, str]]) -> str:
    cols = max((len(text) for _, text in frames), default=0)
    width = 2 * PAD_X + (cols * ADVANCE_TENTHS + 9) // 10
    width = max(width, 620)
    height = BAR_H + PAD_TOP + len(frames) * LINE_H + PAD_X

    beats = sum(1 for _, text in frames if text.strip())
    total_ms = beats * STEP_MS + HOLD_MS
    dur = f"{total_ms / 1000:.1f}s"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"',
        f'     width="{width}" height="{height}" role="img"',
        '     data-magpie-generated="render-wizard"',
        f'     aria-label="{escape(alt)}">',
        f"  <title>{escape(title)}</title>",
        f"  <desc>{escape(desc_text)}</desc>",
        f'  <rect width="{width}" height="{height}" rx="10" fill="{BG}"/>',
        f'  <rect x="0" y="0" width="{width}" height="{BAR_H}" rx="10" fill="{BAR}"/>',
        f'  <rect x="0" y="{BAR_H - 10}" width="{width}" height="10" fill="{BAR}"/>',
    ]
    for cx in (22, 44, 66):
        lines.append(f'  <circle cx="{cx}" cy="17" r="6" fill="{DOT}"/>')
    lines.append(f'  <g font-family="{FONT}" font-size="{FONT_SIZE}" xml:space="preserve">')

    beat = 0
    for i, (colour, text) in enumerate(frames):
        y = BAR_H + PAD_TOP + (i + 1) * LINE_H - 6
        if not text.strip():
            continue
        appear = beat * STEP_MS
        beat += 1
        # values/keyTimes rather than begin=: one animate element per line, all
        # sharing one duration, so the whole sequence loops as a unit and no
        # line can drift out of step with the others.
        k = appear / total_ms
        lines.append(
            f'    <text x="{PAD_X}" y="{y}" fill="{colour}" opacity="0">{escape(text)}'
            f'<animate attributeName="opacity" values="0;0;1;1" '
            f'keyTimes="0;{k:.4f};{min(k + 0.001, 1.0):.4f};1" '
            f'dur="{dur}" repeatCount="indefinite"/></text>'
        )

    # The cursor sits at the end of the last revealed line, blinking throughout.
    last_y = BAR_H + PAD_TOP + len(frames) * LINE_H - 6
    lines.append(
        f'    <rect x="{PAD_X}" y="{last_y - 13}" width="10" height="17" fill="{FG}">'
        f'<animate attributeName="opacity" values="1;1;0;0;1" dur="1.2s" '
        f'repeatCount="indefinite"/></rect>'
    )
    lines += ["  </g>", "</svg>", ""]
    return LICENCE + "\n".join(lines)


def hero_script() -> list[tuple[str, str]]:
    """The shortest true story: install it, run something, get an answer.

    This is the first thing on the quick start, so it answers the only
    question a reader has before they have decided anything -- what does
    using this look like. No agent detection, no family picker, no secure
    setup: those are the page, and `magpie-setup.svg` further down shows
    them. A hero that tries to show everything shows nothing.
    """
    return [
        (CMD, "> /plugin marketplace add apache/magpie"),
        (CMD, "> /plugin install magpie-setup@apache-magpie"),
        (CMD, "> /plugin install magpie-agent-guard@apache-magpie"),
        (CMD, "> /plugin install magpie-utilities@apache-magpie"),
        (CMD, "> /plugin install magpie-pr-management@apache-magpie"),
        (FG, ""),
        (OK, "  ✓ baseline + one family - nothing written to the repository"),
        (FG, ""),
        (CMD, "> /magpie-pr-management:triage"),
        (FG, ""),
        (FG, "  38 open PRs, 12 untriaged"),
        (FG, ""),
        (FG, "  #1421  first contribution, CI green, no reviewer"),
        (MUTED, "         -> mark ready for maintainer review"),
        (FG, "  #1388  draft 3 weeks, no commits since"),
        (MUTED, "         -> ask the author if it is still active"),
        (FG, ""),
        (MUTED, "  Each action needs your confirmation. [Y/n]"),
    ]


def step_install_script() -> list[tuple[str, str]]:
    """Walkthrough step 1: the marketplace install, on one agent.

    Deliberately narrower than the hero, which runs a skill afterwards. This
    one answers what step 1 alone does and where it stops -- no numbers a
    release would move, because nothing regenerates this from the tree.
    """
    return [
        (CMD, "> /plugin marketplace add apache/magpie"),
        (FG, ""),
        (OK, "  ✓ apache-magpie added"),
        (FG, ""),
        (CMD, "> /plugin install magpie-setup@apache-magpie"),
        (OK, "  ✓ magpie-setup          install this one first - nothing"),
        (MUTED, "                          else installs or upgrades without it"),
        (FG, ""),
        (CMD, "> /plugin install magpie-agent-guard@apache-magpie"),
        (OK, "  ✓ magpie-agent-guard    denies dangerous shell shapes before"),
        (MUTED, "                          they run"),
        (FG, ""),
        (CMD, "> /plugin install magpie-utilities@apache-magpie"),
        (OK, "  ✓ magpie-utilities      list-skills, and the small tools"),
        (FG, ""),
        (CMD, "> /plugin install magpie-pr-management@apache-magpie"),
        (OK, "  ✓ magpie-pr-management  the family you picked"),
        (FG, ""),
        (MUTED, "  The first three are the baseline - the same set a project"),
        (MUTED, "  commits when it adopts. Nothing was written to this"),
        (MUTED, "  repository, and your teammates are unaffected."),
    ]


def step_isolation_script() -> list[tuple[str, str]]:
    """Walkthrough step 3: the secure-agent setup, on Claude Code.

    The step other harnesses reach differently, which the page says in a
    table above this. What the animation shows is the shape every one of
    them shares: propose, confirm, then three things that are true after.
    """
    return [
        (CMD, "> /magpie-setup:isolated-setup-install"),
        (FG, ""),
        (FG, "  Proposed - nothing applied yet:"),
        (FG, "    1  .claude/settings.json   sandbox on, credential denies"),
        (FG, "    2  ~/.claude/scripts/      hooks and the status line"),
        (FG, "    3  ~/.zshrc                source agent-iso.sh"),
        (FG, ""),
        (FG, "  Apply 1-3? [y/N] y"),
        (FG, ""),
        (OK, "  ✓ sandbox      bash sees only the paths you allow"),
        (OK, "  ✓ clean env    credentials stripped before the agent starts"),
        (OK, "  ✓ status line  [sandbox] in the footer, green when it is on"),
        (FG, ""),
        (MUTED, "  Your ~/.ssh, ~/.aws and tokens are out of reach. Every sudo,"),
        (MUTED, "  shell-rc and settings change was shown before it ran."),
    ]


def step_guard_script() -> list[tuple[str, str]]:
    """Walkthrough step 4: the deterministic action guard.

    The isolation step sandboxes the process; this one guards the command.
    What it has to show is the distinction, so it ends on a real denial
    rather than on a list of things that were installed: a guard nobody
    has watched say no reads as one more checkbox.
    """
    return [
        (CMD, "> /magpie-setup:isolated-setup-install"),
        (FG, ""),
        (FG, "  Registering the deterministic guard:"),
        (FG, "    ~/.claude/scripts/agent-guard.py     the dispatcher"),
        (FG, "    ~/.claude/scripts/guards.d/          5 rules, bundled + skill-owned"),
        (FG, "    .claude/settings.json                PreToolUse hook on Bash"),
        (FG, ""),
        (OK, "  ✓ every shell command is inspected before it runs"),
        (FG, ""),
        (MUTED, "  Later that session -"),
        (FG, ""),
        (CMD, "> gh pr comment 1421 --body \"@alice @bob please take a look\""),
        (FG, ""),
        (WARN, "  ⚠ agent-guard[mention] denied this before it ran"),
        (FG, ""),
        (FG, "    A review ping to two maintainers who did not ask for it."),
        (FG, "    The author is @carol - anyone else is noise."),
        (MUTED, "    Fix: write `alice` in backticks, or MAGPIE_ALLOW_MENTIONS=1."),
        (FG, ""),
        (MUTED, "  Nothing was posted. The rule is code, not a line in a SKILL.md"),
        (MUTED, "  the model has to remember - so it holds on the turn it matters."),
    ]


def step_use_script() -> list[tuple[str, str]]:
    """Walkthrough step 4: invoking a skill, and what comes back.

    The first three steps are preparation. This is the one that shows why
    any of it was worth doing, so it ends on the thing every skill in the
    framework has in common: a proposal, not an action.
    """
    return [
        (CMD, "> /magpie-utilities:list-skills"),
        (FG, ""),
        (FG, "  magpie-setup           install, upgrade, adopt, sandbox"),
        (FG, "  magpie-utilities       author and index your own skills"),
        (FG, "  magpie-pr-management   triage, review, stats, quick-merge"),
        (FG, ""),
        (CMD, "> /magpie-pr-management:triage"),
        (FG, ""),
        (FG, "  38 open PRs, 12 untriaged"),
        (FG, ""),
        (FG, "  #1421  first contribution, CI green, no reviewer"),
        (MUTED, "         -> mark ready for maintainer review"),
        (FG, "  #1402  branch 200 commits behind, conflicts"),
        (MUTED, "         -> ask the author to rebase"),
        (FG, ""),
        (OK, "  Nothing has been posted. Every action waits for you."),
    ]


def step_adopt_script() -> list[tuple[str, str]]:
    """Walkthrough step 5: adoption, which most readers will never run.

    So the animation leads with who it is for and ends on what it does not
    do, rather than selling it.
    """
    return [
        (WARN, "  Only if you are a maintainer, deciding with the others."),
        (FG, ""),
        (CMD, "> /magpie-setup adopt"),
        (FG, ""),
        (FG, "  Staged, not committed:"),
        (FG, "    .apache-magpie.lock       the floor - a minimum, not a pin"),
        (FG, "    .claude/settings.json     derived from it"),
        (FG, "    .apache-magpie-overrides/ the project's configuration"),
        (FG, ""),
        (OK, "  ✓ a contributor who clones this arrives with the floor"),
        (OK, "  ✓ review it and commit it like any other change"),
        (FG, ""),
        (MUTED, "  It limits nobody: anyone may install more, run a newer"),
        (MUTED, "  Magpie, or ignore the recommendation entirely."),
    ]


def setup_script() -> list[tuple[str, str]]:
    """The first run, end to end: install, then the secure-agent setup.

    Fixed rather than derived, because it is one arc rather than a per-family
    projection — but it tracks what install.md and isolated-setup-install.md
    actually do, and the eval suites for both are what keep those honest.
    """
    return [
        (CMD, "> /magpie-setup"),
        (FG, ""),
        (MUTED, "  Agent      Claude Code"),
        (MUTED, "  Installed  nothing yet"),
        (MUTED, "  Repo       github.com/acme/toolkit, not adopted"),
        (FG, ""),
        (FG, "  Which families? The baseline three are ticked already."),
        (OK, "    [x] setup            install, upgrade, adopt, sandbox"),
        (OK, "    [x] agent-guard      denies dangerous commands before they run"),
        (OK, "    [x] utilities        author and index your own skills"),
        (OK, '    [x] pr-management    you said "triage"'),
        (MUTED, "    [ ] security  [ ] issue  [ ] release-management  [ ] …"),
        (FG, ""),
        (FG, "  Installing 4 plugins for you - user scope:"),
        (OK, "    ✓ apache-magpie marketplace added"),
        (OK, "    ✓ magpie-setup   ✓ magpie-agent-guard"),
        (OK, "    ✓ magpie-utilities   ✓ magpie-pr-management"),
        (FG, ""),
        (MUTED, "  Live in your next session. Nothing was written to the"),
        (MUTED, "  repository - that is the finished state."),
        (FG, ""),
        (WARN, "  One follow-up that is not optional - these skills read"),
        (WARN, "  pre-disclosure security content, so sandbox the agent:"),
        (FG, ""),
        (CMD, "> /magpie-setup:isolated-setup-install"),
        (FG, ""),
        (FG, "  Proposed - nothing applied yet:"),
        (FG, "    1  .claude/settings.json   sandbox on, 14 deny rules"),
        (FG, "    2  ~/.claude/scripts/      3 hooks and the status line"),
        (FG, "    3  ~/.zshrc                source agent-iso.sh"),
        (FG, ""),
        (FG, "  Apply 1-3? [y/N] y"),
        (FG, ""),
        (OK, "  ✓ sandbox        filesystem and network confined to this repo"),
        (OK, "  ✓ clean env      credentials stripped before the agent starts"),
        (OK, "  ✓ status line    shows the sandbox state and the Magpie version"),
        (FG, ""),
        (MUTED, "  Run a skill when you are ready. The first one that needs project"),
        (MUTED, "  configuration writes it itself, into gitignored files."),
    ]


def build() -> dict[Path, str]:
    cfg = _load("check_skill_config", Path("tools/dev/check-skill-config.py"))
    desc = cfg.descriptions()
    out: dict[Path, str] = {
        HERO_SVG: render(
            "Install Magpie, and use it",
            "An animated first look: three install commands, then a triage run "
            "returning 38 open PRs with a proposed action for each and a confirmation "
            "prompt",
            "Illustrative animation of installing Magpie and running one skill. Not a recording.",
            hero_script(),
        ),
        STEP_INSTALL_SVG: render(
            "Step 1 — install from the marketplace",
            "An animated marketplace install: adding apache-magpie, then installing "
            "magpie-setup and one family, with nothing written to the repository",
            "Illustrative animation of the marketplace install step. Not a recording.",
            step_install_script(),
        ),
        STEP_ISOLATION_SVG: render(
            "Step 3 — lock the agent down",
            "An animated secure-agent setup: three proposed changes, a confirmation, "
            "then the sandbox, the clean environment and the status line in place",
            "Illustrative animation of the secure-agent setup step. Not a recording.",
            step_isolation_script(),
        ),
        STEP_GUARD_SVG: render(
            "Step 4 — put the guard in front of every command",
            "An animated agent-guard setup: the dispatcher, the rules and the "
            "PreToolUse hook registered, then a real denial of an unwanted "
            "review ping before it was posted",
            "Illustrative animation of the deterministic action guard. Not a recording.",
            step_guard_script(),
        ),
        STEP_USE_SVG: render(
            "Step 5 — use it",
            "An animated skill run: listing what is installed, then a triage pass "
            "returning 38 open PRs with a proposed action each and nothing posted",
            "Illustrative animation of running a skill. Not a recording.",
            step_use_script(),
        ),
        STEP_ADOPT_SVG: render(
            "Step 6 — adopt it for the project",
            "An animated adopt run: three paths staged and not committed, what a "
            "contributor gets on clone, and what it does not restrict",
            "Illustrative animation of adopting Magpie for a project. Not a recording.",
            step_adopt_script(),
        ),
        SETUP_SVG: render(
            "/magpie-setup — the first run",
            "An animated first run of /magpie-setup: the agent detected, the skill families "
            "picked, the install commands emitted, then the secure-agent setup applying the "
            "sandbox, the clean-environment wrapper, the hooks and the status line",
            "Illustrative animation of a first /magpie-setup run and the secure-agent setup "
            "that follows it. Not a recording.",
            setup_script(),
        ),
    }
    for family, skills in sorted(cfg.families().items()):
        required = sorted({name for need, _ in skills.values() for name in need})
        if not required:
            continue  # nothing to configure, so nothing to animate
        out[OUT_DIR / f"{family}.svg"] = render(
            f"/magpie-setup config — {family}",
            f"An animated /magpie-setup config run for the {family} family: the check failing, "
            f"values derived from the repository, one question, and gitignored files written",
            f"Illustrative animation of a configuration run for the {family} family. Derived "
            f"from the skills' declared required configuration.",
            script(family, required, desc),
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if any file is stale")
    parser.add_argument("files", nargs="*", help="(ignored; present for pre-commit)")
    args = parser.parse_args([] if argv is None else argv)

    if not Path("plugins").is_dir():
        print("render-wizard: run from the repository root", file=sys.stderr)
        return 2

    wanted = build()
    if args.check:
        stale = [p for p, body in wanted.items() if not p.is_file() or p.read_text("utf-8") != body]
        extra = [p for p in sorted(OUT_DIR.glob("*.svg")) if p not in wanted] if OUT_DIR.is_dir() else []
        for path in stale:
            print(f"{path}: stale — run python3 tools/dev/render-wizard.py", file=sys.stderr)
        for path in extra:
            print(f"{path}: no family requires configuration — delete it", file=sys.stderr)
        return 1 if (stale or extra) else 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, body in wanted.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    for path in sorted(OUT_DIR.glob("*.svg")):
        if path not in wanted:
            path.unlink()
    fams = sum(1 for path in wanted if path.parent == OUT_DIR)
    print(
        f"render-wizard: wrote {len(wanted)} animated runs "
        f"({len(wanted) - fams} top-level, {fams} per-family)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
