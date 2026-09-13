#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Validate the one recording and the authored screenshots the docs embed.

`docs/quick-start.md` used to carry one install screenshot per *harness* and
each `docs/<family>/README.md` one per *family* — fourteen stills, with a
design on file to grow them to twenty-five. Every one of them showed the same
thing, a plugin list with a plugin in it: proof that an install succeeded, and
nothing about the framework doing anything.

They were replaced by recordings. That fixed the wrong half. The quick start's
`/magpie-setup` recording earned its place, but the nine per-family recordings
all showed *setup's* arc — a pre-flight stopping on an unadopted repo — which
is the quick start's subject, not the family's. Nine copies of it, filed under
ten families, taught a reader nothing about what the families do. They are
gone.

What each family shows now is that family working, and those are **authored**:
a committed `.txt` transcript rendered to a static `.svg` by
`render-screenshot.sh`. A capture needs a terminal, a scratch project and a
human, and needs all three again whenever any output moves — which is exactly
why nine placeholders sat in the tree for months. A transcript is a text file:
it reviews as a diff and a contributor can fix a line without a recording
session.

What authoring gives up is the guarantee that the picture matches the program,
and this file buys back the half it can. Rendering is deterministic, so every
committed `.svg` can be proven to still match its `.txt`. The other half —
that the `.txt` matches what the skill prints today — is a human's judgement,
and `assets/quickstart/README.md` says so rather than letting a reader assume
this check is stronger than it is.

Checks:

- every family in the live `family:` frontmatter has a screenshot directory
  with at least one transcript in it, and every directory on disk belongs to a
  family;
- every screenshot names a skill that family actually ships, so a renamed
  skill cannot leave a picture of a command nobody can run;
- every `.txt` has an `.svg` beside it, every `.svg` has a `.txt`, and every
  `.svg` still regenerates byte-identically from its source;
- every screenshot is embedded by its family README, and every family README
  embeds at least one;
- `magpie-setup.svg` — the whole first run, including the secure-agent setup
  that follows it — regenerates from `render-wizard.py`, is embedded by the
  quick start, and the setup family's README embeds it rather than a copy.
  It used to be the repository's one *recording*, and it was wrong: it opened
  with the marketplace install, which became a prerequisite with its own page,
  and re-cutting it needed a terminal, a scratch project and a human. Nothing
  here is captured any more;
- the per-family wizard animations regenerate from the frontmatter they are
  derived from, and each is embedded by its family README. These have no
  transcript to pair with -- their source is `requires_config:` -- so the
  pairing rule does not apply to them and the staleness rule does;
- the first-run walkthrough's screenshots are paired and embedded by the
  chapter they exist for, in the order its steps run. A walkthrough whose
  pictures are a step out of order teaches the wrong sequence, and no link
  check can see it;
- every SVG parses as XML with an `<svg>` root, carries the Apache licence
  header, and is under the size cap. These are *text*: one that fails to parse
  still "exists", a hand-edited file loses the licence header its generator
  writes, and one that grows unnoticed ships in every source release. None of it shows up in review, because the diff of a generated SVG
  is unreadable by design;
- nothing still points at anything retired — the fourteen PNG stills, the nine
  `*-first-run.svg` recordings, or the `assets/examples/` set the authored
  screenshots replaced.

There is no placeholder machinery left. It existed because ten recordings
needed ten capture sessions and blocking commits until someone sat down with
asciinema would simply have got the hook disabled. One recording is a thing a
person does once; a screenshot is a file you write. Neither needs an interim
state, so a missing file is now an error rather than a note.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

QUICKSTART = Path("assets/quickstart")
FAMILY_DIR = QUICKSTART / "families"
WALKTHROUGH_DIR = QUICKSTART / "walkthrough"
WIZARD_DIR = QUICKSTART / "wizard"
WIZARD_SCRIPT = Path("tools/dev/render-wizard.py")
FIRST_RUN_DOC = Path("docs/quick-start/first-run.md")
PLUGINS = Path("plugins")
SETUP_RECORDING = QUICKSTART / "magpie-setup.svg"
QUICK_START_DOC = Path("docs/quick-start.md")
RENDER_SCRIPT = Path("tools/dev/render-screenshot.sh")
SKILLS = Path("skills")

# Generous next to a terminal GIF and still small enough to not be felt in a
# source release. Nothing generated here comes close; the cap is the guard
# against a transcript that grew without anyone noticing.
MAX_BYTES = 1536 * 1024

LICENCE_MARKER = "Licensed to the Apache Software Foundation"
SVG_ROOT = "{http://www.w3.org/2000/svg}svg"

# One family's docs directory is not named after the family.
DOCS_DIR_OVERRIDES = {"issue": "issue-management"}

# Everything this set replaced. A live reference to any of it renders a broken
# image, and the offline link check does not cover every path that could
# reintroduce one.
RETIRED = re.compile(
    r"assets/quickstart/(?:families/)?[A-Za-z0-9._-]+\.png"
    r"|assets/quickstart/families/[A-Za-z0-9._-]+-first-run\.svg"
    r"|assets/examples/[A-Za-z0-9._-]+\.svg"
)


def families() -> list[str]:
    """The live family list, from the frontmatter the plugins are built from."""
    found = set()
    for skill in SKILLS.glob("*/SKILL.md"):
        for line in skill.read_text().splitlines():
            if line.startswith("family:"):
                found.add(line.split("family:", 1)[1].strip())
                break
    return sorted(found)


def docs_readme(family: str) -> Path:
    return Path("docs") / DOCS_DIR_OVERRIDES.get(family, family) / "README.md"


def family_skills(family: str) -> set[str]:
    """The skills a family plugin ships, under the aliases it advertises them by."""
    skills_dir = PLUGINS / f"magpie-{family}" / "skills"
    if not skills_dir.is_dir():
        return set()
    return {p.name for p in skills_dir.iterdir()}


def check_svg(path: Path) -> list[str]:
    """Parse, licence header and size cap — the checks that apply to any SVG
    the docs embed, authored or recorded."""
    if not path.is_file():
        return [f"{path}: missing"]

    errors: list[str] = []
    raw = path.read_bytes()

    if (n := len(raw)) > MAX_BYTES:
        errors.append(
            f"{path}: {n // 1024} KB exceeds the {MAX_BYTES // 1024} KB cap — "
            f"shorten the transcript it renders from"
        )

    text = raw.decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        errors.append(f"{path}: not parsable as XML ({exc}) — it will render as nothing")
        return errors

    if root.tag != SVG_ROOT:
        errors.append(
            f"{path}: root element is {root.tag!r}, expected an SVG root — the page embeds this as an image"
        )

    if LICENCE_MARKER not in text:
        errors.append(f"{path}: no Apache licence header. Regenerate it — every generator here prepends one")

    return errors


def check_screenshots(known: list[str]) -> list[str]:
    """The authored set: coverage, pairing, naming, and that the docs show it."""
    errors: list[str] = []

    if not FAMILY_DIR.is_dir():
        return [f"{FAMILY_DIR}: missing — every family's screenshots live here"]

    on_disk = {d.name for d in FAMILY_DIR.iterdir() if d.is_dir()}
    for stray in sorted(on_disk - set(known)):
        errors.append(
            f"{FAMILY_DIR / stray}: no family declares {stray!r} in its "
            f"frontmatter — drop the directory, or add the family"
        )

    # A loose file directly under families/ is the shape the retired recordings
    # had. Name it, rather than letting it pass as "not a directory".
    for loose in sorted(p for p in FAMILY_DIR.iterdir() if p.is_file()):
        errors.append(
            f"{loose}: screenshots live in a per-family directory — "
            f"{FAMILY_DIR}/<family>/<skill>.txt and its rendered .svg"
        )

    for family in known:
        fdir = FAMILY_DIR / family
        readme = docs_readme(family)
        transcripts = sorted(fdir.glob("*.txt")) if fdir.is_dir() else []

        if not transcripts:
            errors.append(
                f"{fdir}: no screenshots for the {family!r} family — write at "
                f"least one transcript and render it with {RENDER_SCRIPT}"
            )
            continue

        body = readme.read_text() if readme.is_file() else ""
        if not readme.is_file():
            errors.append(f"{readme}: missing")

        ships = family_skills(family)
        for txt in transcripts:
            svg = txt.with_suffix(".svg")
            if not svg.is_file():
                errors.append(f"{svg}: missing — render it with {RENDER_SCRIPT} {txt}")
                continue
            errors += check_svg(svg)
            if ships and txt.stem not in ships:
                errors.append(
                    f"{txt}: magpie-{family} ships no skill {txt.stem!r}, so this "
                    f"pictures a command nobody can run"
                )
            if body and svg.as_posix() not in body:
                errors.append(f"{readme}: does not embed {svg}")

        for svg in sorted(fdir.glob("*.svg")):
            if not svg.with_suffix(".txt").is_file():
                errors.append(
                    f"{svg}: no transcript beside it — an SVG here is generated, never hand-written"
                )

    return errors


def check_walkthrough() -> list[str]:
    """The first-run chapter: every step pictured, and pictured in order.

    Separate from the family screenshots because the constraint is different.
    A family screenshot has to name a skill that family ships; a walkthrough
    screenshot has to be step N of a sequence the reader follows top to
    bottom, so the check that matters is that the chapter embeds them all, in
    the order their filenames number them.
    """
    if not WALKTHROUGH_DIR.is_dir():
        return [f"{WALKTHROUGH_DIR}: missing — the first-run chapter has no screenshots"]

    errors: list[str] = []
    steps = sorted(WALKTHROUGH_DIR.glob("*.txt"))
    if not steps:
        return [f"{WALKTHROUGH_DIR}: no transcripts"]

    if not FIRST_RUN_DOC.is_file():
        return [f"{FIRST_RUN_DOC}: missing — the walkthrough screenshots are shown by nothing"]
    body = FIRST_RUN_DOC.read_text(encoding="utf-8")

    seen_at: list[tuple[int, str]] = []
    for txt in steps:
        svg = txt.with_suffix(".svg")
        if not svg.is_file():
            errors.append(f"{svg}: missing — render it with {RENDER_SCRIPT} {txt}")
            continue
        errors += check_svg(svg)
        at = body.find(svg.as_posix())
        if at == -1:
            errors.append(f"{FIRST_RUN_DOC}: does not embed {svg}")
        else:
            seen_at.append((at, txt.stem))

    for svg in sorted(WALKTHROUGH_DIR.glob("*.svg")):
        if not svg.with_suffix(".txt").is_file():
            errors.append(f"{svg}: no transcript beside it — generated, never hand-written")

    if [name for _, name in sorted(seen_at)] != [name for _, name in seen_at]:
        errors.append(
            f"{FIRST_RUN_DOC}: embeds the walkthrough screenshots out of order — "
            f"they are numbered steps and the page is read top to bottom"
        )
    return errors


def check_wizards() -> list[str]:
    """The animated per-family config runs: regenerate, and are shown.

    Derived from `requires_config:` rather than from a transcript, so the
    check is the same in spirit and different in mechanism: re-derive and
    compare, then confirm the family page embeds the result.
    """
    if not WIZARD_SCRIPT.is_file():
        return [f"{WIZARD_SCRIPT}: missing — nothing can verify the wizard animations"]

    errors: list[str] = []
    proc = subprocess.run(["python3", str(WIZARD_SCRIPT), "--check"], capture_output=True, text=True)
    if proc.returncode != 0:
        errors += [line for line in proc.stderr.splitlines() if line.strip()]

    if not WIZARD_DIR.is_dir():
        return errors

    for svg in sorted(WIZARD_DIR.glob("*.svg")):
        errors += check_svg(svg)
        readme = docs_readme(svg.stem)
        if not readme.is_file():
            errors.append(f"{readme}: missing — {svg} is shown by nothing")
        elif svg.as_posix() not in readme.read_text(encoding="utf-8"):
            errors.append(f"{readme}: does not embed {svg}")
    return errors


def check_regenerates() -> list[str]:
    """Every committed .svg still matches its .txt.

    This is the guard a hand-authored image cannot have, and the whole reason
    the renderer is byte-deterministic. Delegated to the renderer so the
    comparison lives in one place.
    """
    if not RENDER_SCRIPT.is_file():
        return [f"{RENDER_SCRIPT}: missing — nothing can verify the screenshots"]
    proc = subprocess.run(
        ["bash", str(RENDER_SCRIPT), "--check"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return []
    return [line for line in proc.stderr.splitlines() if line.strip()]


def check_embedded(doc: Path, recording: Path) -> list[str]:
    """A recording and the page that exists to show it must not drift apart."""
    if not doc.is_file():
        return [f"{doc}: missing"]
    if recording.name in doc.read_text():
        return []
    return [f"{doc}: does not embed {recording} — the page this recording exists for"]


def check_no_retired_references() -> list[str]:
    """Three sets were retired. Nothing may point at any of them again."""
    errors: list[str] = []

    for png in sorted(QUICKSTART.rglob("*.png")):
        errors.append(
            f"{png}: the quick-start screenshot set was retired in favour of the "
            f"recording and the authored screenshots — a new still here is shown by nothing"
        )

    for stale in sorted(FAMILY_DIR.glob("*-first-run.svg")) if FAMILY_DIR.is_dir() else []:
        errors.append(
            f"{stale}: the per-family first-run recordings were retired — they "
            f"showed setup's arc, which the quick start already shows"
        )

    if Path("assets/examples").is_dir():
        errors.append(
            "assets/examples/: retired — the authored screenshots under "
            f"{FAMILY_DIR} do this job for every family, not one"
        )

    for doc in [*sorted(Path("docs").rglob("*.md")), Path("README.md")]:
        if not doc.is_file():
            continue
        # A design records what was replaced, in prose that explains the
        # replacement. Only live references matter here.
        if doc.parts[:2] == ("docs", "designs"):
            continue
        for match in sorted(set(RETIRED.findall(doc.read_text()))):
            errors.append(f"{doc}: references retired asset {match}")

    return errors


def main() -> int:
    known = families()
    errors: list[str] = []

    # The first-run animation. The setup family's first run *is* that run, so
    # its README embeds it rather than a copy.
    errors += check_svg(SETUP_RECORDING)
    errors += check_embedded(QUICK_START_DOC, SETUP_RECORDING)
    if "setup" in known:
        errors += check_embedded(docs_readme("setup"), SETUP_RECORDING)

    errors += check_screenshots(known)
    errors += check_walkthrough()
    errors += check_wizards()
    errors += check_regenerates()
    errors += check_no_retired_references()

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    shots = len(list(FAMILY_DIR.rglob("*.svg"))) if FAMILY_DIR.is_dir() else 0
    steps = len(list(WALKTHROUGH_DIR.glob("*.svg"))) if WALKTHROUGH_DIR.is_dir() else 0
    wizards = len(list(WIZARD_DIR.glob("*.svg"))) if WIZARD_DIR.is_dir() else 0
    print(
        f"Screenshots OK ({shots} family screenshots, {steps} walkthrough steps, "
        f"{wizards + 1} generated animations). Nothing is captured."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
