#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Validate the quick-start screenshot set against the harnesses and families
the repository actually ships.

`docs/quick-start.md` shows one install screenshot per *harness*, and each
`docs/<family>/README.md` shows one per *family*. Three separate lists therefore
have to agree — the harnesses `capture-screenshot.sh` will capture, the
ecosystem manifests that make a harness real, and the files on disk — and
nothing was checking that they did. A harness added to the docs without a
manifest, a family added to the frontmatter without a screenshot, or a capture
taken at a different window size than the rest of its set are all invisible at
review time: the page still renders and the link check still passes, because a
placeholder and a real capture are both valid PNG files.

Checks:

- every harness `capture-screenshot.sh` offers has the ecosystem manifest that
  makes it a real target, and vice versa — a harness with no manifest is a
  screenshot of something the framework does not ship;
- every harness and every `family:` in the frontmatter has its screenshot at
  the exact path the docs reference;
- no orphan screenshots — a file no harness or family claims is one the docs
  cannot be showing;
- every file is a real PNG, and each one is either a *real capture* at the
  canonical width or an untouched *placeholder* at the placeholder geometry.
  Any third size is a capture taken at the wrong window size;
- real family captures all share one geometry. They are one `/plugin` list
  photographed ten times, so differing sizes mean the window was resized
  mid-run and the set will read as ragged on the page;
- nothing exceeds the published size cap.

Placeholders are *allowed*: they are the documented interim state
(`assets/quickstart/README.md`) that keeps the pages rendering until a real
capture replaces them. They are reported so the remaining work stays visible,
but they do not fail the check — a hook that blocked commits until all
fourteen were captured would simply be disabled.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

CAPTURE_SCRIPT = Path("tools/dev/capture-screenshot.sh")
SKILLS = Path("skills")
QUICKSTART = Path("assets/quickstart")
FAMILY_DIR = QUICKSTART / "families"

# The canonical capture width, matching `assets/session-*.png` and the
# `WIDTH=` the capture script resizes to. A capture narrower than this was
# taken on a display that could not supply the pixels (the script only ever
# shrinks), and is what makes one shot look soft beside the others.
CAPTURE_WIDTH = 1700
# The generated-placeholder geometry from `assets/quickstart/README.md`.
PLACEHOLDER_SIZE = (1200, 300)
MAX_BYTES = 500 * 1024

# A harness earns a screenshot by shipping the manifest its client reads. This
# is the join that keeps the three lists honest: drop a manifest and the
# harness must leave the capture script and the docs with it.
HARNESS_MANIFESTS = {
    "claude-code": Path(".claude-plugin/marketplace.json"),
    "codex": Path(".agents/plugins/marketplace.json"),
    "vscode": Path("marketplace.json"),  # GitHub Copilot / VS Code catalogue
    "gemini": Path("gemini-extension.json"),
}

# Shots the docs describe but do not require. The auto-install shot has to be
# staged (drop your own `enabledPlugins`, re-trust the repo) rather than merely
# captured, so it is not part of the set a contributor is expected to produce —
# but it is a documented path, so when it does exist it must meet the same
# conventions instead of counting as an orphan.
OPTIONAL_SHOTS = (QUICKSTART / "claude-code-default-install.png",)


def harnesses_from_capture_script() -> tuple[list[str], list[str]]:
    """Read the harness list the capture script offers as targets."""
    if not CAPTURE_SCRIPT.is_file():
        return [], [f"{CAPTURE_SCRIPT}: missing (source of the harness list)"]
    match = re.search(r"^HARNESSES=\(([^)]*)\)", CAPTURE_SCRIPT.read_text(), re.M)
    if not match:
        return [], [f"{CAPTURE_SCRIPT}: no HARNESSES=(...) array found"]
    return re.findall(r'"([^"]+)"', match.group(1)), []


def families_from_frontmatter() -> list[str]:
    """Families come from live `family:` frontmatter, as everywhere else."""
    found = set()
    for skill in sorted(SKILLS.glob("*/SKILL.md")):
        for line in skill.read_text().splitlines():
            if line.startswith("family:"):
                found.add(line.split(":", 1)[1].strip())
                break
    return sorted(found)


def png_size(path: Path) -> tuple[tuple[int, int] | None, str | None]:
    """Width/height straight from the IHDR chunk — no image library needed."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, f"{path}: not a PNG"
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None, f"{path}: corrupt or truncated PNG header"
    return struct.unpack(">II", data[16:24]), None


def check_image(path: Path) -> tuple[bool | None, list[str]]:
    """Return (is_real_capture, errors). None means the geometry was unusable."""
    if not path.is_file():
        return None, [f"{path}: missing"]
    size, err = png_size(path)
    if size is None:
        return None, [err or f"{path}: unreadable PNG header"]
    errors: list[str] = []
    if (n := path.stat().st_size) > MAX_BYTES:
        errors.append(f"{path}: {n // 1024} KB exceeds the {MAX_BYTES // 1024} KB cap")
    width, height = size
    if size == PLACEHOLDER_SIZE:
        return False, errors
    if width == CAPTURE_WIDTH:
        return True, errors
    errors.append(
        f"{path}: {width}x{height} is neither a {CAPTURE_WIDTH}px-wide capture nor "
        f"the {PLACEHOLDER_SIZE[0]}x{PLACEHOLDER_SIZE[1]} placeholder — capture it "
        f"from a window at least {CAPTURE_WIDTH}px wide (see assets/quickstart/README.md)"
    )
    return None, errors


def main() -> int:
    errors: list[str] = []
    placeholders: list[Path] = []

    harnesses, errs = harnesses_from_capture_script()
    errors.extend(errs)

    # The capture script and the shipped manifests must name the same harnesses.
    for harness in harnesses:
        if harness not in HARNESS_MANIFESTS:
            errors.append(
                f"{CAPTURE_SCRIPT}: harness {harness!r} has no known manifest — add it "
                f"to HARNESS_MANIFESTS here, or drop the target"
            )
        elif not HARNESS_MANIFESTS[harness].is_file():
            errors.append(
                f"{harness}: capture target exists but its manifest {HARNESS_MANIFESTS[harness]} does not"
            )
    for harness, manifest in HARNESS_MANIFESTS.items():
        if manifest.is_file() and harness not in harnesses:
            errors.append(
                f"{harness}: ships {manifest} but {CAPTURE_SCRIPT} offers no capture "
                f"target, so the quick-start page cannot show it"
            )

    expected = {QUICKSTART / f"{h}-install.png" for h in harnesses}
    family_shots = {FAMILY_DIR / f"{f}-install.png" for f in families_from_frontmatter()}
    expected |= family_shots

    real_family_sizes: dict[Path, tuple[int, int]] = {}
    for path in sorted(expected):
        is_real, errs = check_image(path)
        errors.extend(errs)
        if is_real is False:
            placeholders.append(path)
        elif is_real and path in family_shots:
            size, _ = png_size(path)
            if size:
                real_family_sizes[path] = size

    # One /plugin list photographed ten times: the geometry must not wander.
    if len(set(real_family_sizes.values())) > 1:
        by_size: dict[tuple[int, int], list[str]] = {}
        for path, size in sorted(real_family_sizes.items()):
            by_size.setdefault(size, []).append(path.name)
        detail = "; ".join(f"{w}x{h}: {', '.join(names)}" for (w, h), names in sorted(by_size.items()))
        errors.append(
            f"family captures have inconsistent geometry ({detail}) — capture the whole "
            f"family set without resizing the window between shots"
        )

    for optional in OPTIONAL_SHOTS:
        if optional.is_file():
            _, errs = check_image(optional)
            errors.extend(errs)

    known = expected | set(OPTIONAL_SHOTS)
    for stray in sorted(set(QUICKSTART.glob("*.png")) | set(FAMILY_DIR.glob("*.png"))):
        if stray not in known:
            errors.append(f"{stray}: orphan screenshot — no harness or skill family claims it")

    if placeholders:
        print(
            f"note: {len(placeholders)} of {len(expected)} screenshots are still "
            f"placeholders: {', '.join(p.name for p in placeholders)}"
        )
    if errors:
        print("Quick-start screenshot set is inconsistent:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"Quick-start screenshots OK ({len(expected)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
