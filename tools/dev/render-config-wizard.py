#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Generate one animated SVG per family: `/magpie-setup config`, playing through.

The family screenshots show a skill's *output*. They cannot show the thing a
first-time reader most needs to see, which is the shape of a conversation —
the command being typed, the values the wizard works out on its own, the one
question it asks, and the files that appear. A still frame of a wizard is a
wizard with the interesting part removed.

So this animates it. Every frame is derived, not written: the files a family's
wizard would create come from that family's skills' `requires_config:`
frontmatter, and the one-line description of each comes from the adopter
scaffold's index — the same two sources `check-skill-config.py` reads. A
family that gains a required file gets a new frame in its animation on the
next `--fix`, with nobody editing a transcript.

**Illustrative, not a recording.** The real run derives more, asks better
questions, and looks like whatever the harness renders. What this shows
truthfully is the shape: auto-detect first, one batched question, gitignored
files out, nothing staged. `assets/quickstart/README.md` says so where a
reader will meet it.

Why SMIL rather than a capture: the same reason the static screenshots are
authored. A capture needs a terminal, a human and asciinema, and needs all
three again whenever the wizard's wording moves. SMIL `<animate>` is plain
XML, deterministic, and needs no Node — `record-svg.sh` is the one place
svg-term-cli is a dependency, and this is not it. GitHub animates inline SVG;
a renderer that does not falls back to the first frame, which is the command
about to be typed.

Determinism is the same contract the static renderer signs: same frontmatter,
same bytes, on any machine. No timestamps, no ids that vary, integer geometry
only.

Run from the repo root:

    python3 tools/dev/render-config-wizard.py           # write them
    python3 tools/dev/render-config-wizard.py --check   # fail on drift
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from xml.sax.saxutils import escape

OUT_DIR = Path("assets/quickstart/wizard")

# The recorder's palette, so this reads as the same terminal as everything else.
BG, BAR, DOT = "#1d1f21", "#2b2e31", "#3f4448"
FG, MUTED, CMD = "#c5c8c6", "#8a8f94", "#8abeb7"
OK, WARN = "#7f9f7f", "#d8a657"

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
FONT_SIZE = 17
ADVANCE_TENTHS = 102  # 0.6em at 17px, in tenths, so the geometry stays integer
LINE_H = 24
PAD_X, PAD_TOP, BAR_H = 26, 28, 34

STEP_MS = 700  # one revealed line
HOLD_MS = 2600  # the pause on the finished frame before it loops

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

  Derived from the skills' requires_config: frontmatter by
  tools/dev/render-config-wizard.py. Illustrative of the shape of a
  /magpie-setup config run, not a recording of one.
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


def render(family: str, frames: list[tuple[str, str]]) -> str:
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
        '     data-magpie-generated="render-config-wizard"',
        f'     aria-label="An animated /magpie-setup config run for the {family} family:'
        f" the check failing, values derived from the repository, one question, and"
        f' gitignored files written">',
        f"  <title>/magpie-setup config — {family}</title>",
        f"  <desc>Illustrative animation of a configuration run for the {family}"
        f" family. Derived from the skills' declared required configuration.</desc>",
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


def build() -> dict[Path, str]:
    cfg = _load("check_skill_config", Path("tools/dev/check-skill-config.py"))
    desc = cfg.descriptions()
    out: dict[Path, str] = {}
    for family, skills in sorted(cfg.families().items()):
        required = sorted({name for need, _ in skills.values() for name in need})
        if not required:
            continue  # nothing to configure, so nothing to animate
        out[OUT_DIR / f"{family}.svg"] = render(family, script(family, required, desc))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if any file is stale")
    parser.add_argument("files", nargs="*", help="(ignored; present for pre-commit)")
    args = parser.parse_args([] if argv is None else argv)

    if not Path("plugins").is_dir():
        print("render-config-wizard: run from the repository root", file=sys.stderr)
        return 2

    wanted = build()
    if args.check:
        stale = [p for p, body in wanted.items() if not p.is_file() or p.read_text("utf-8") != body]
        extra = [p for p in sorted(OUT_DIR.glob("*.svg")) if p not in wanted] if OUT_DIR.is_dir() else []
        for path in stale:
            print(f"{path}: stale — run python3 tools/dev/render-config-wizard.py", file=sys.stderr)
        for path in extra:
            print(f"{path}: no family requires configuration — delete it", file=sys.stderr)
        return 1 if (stale or extra) else 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, body in wanted.items():
        path.write_text(body, encoding="utf-8")
    for path in sorted(OUT_DIR.glob("*.svg")):
        if path not in wanted:
            path.unlink()
    print(f"render-config-wizard: wrote {len(wanted)} animated wizard runs to {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
