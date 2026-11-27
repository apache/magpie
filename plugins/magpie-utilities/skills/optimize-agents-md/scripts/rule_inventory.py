#!/usr/bin/env python3
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
#
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check that no rule was lost when an agent-instruction file was optimized.

An AGENTS.md has no eval suite, so this is the proof that a pass preserved
behaviour. It collects every *rule sentence* of the file before the pass. A
rule sentence is one that either:

- carries a normative word (MUST, never, always, required, do not, ...); or
- opens with a command verb (*"Run the link check."*, *"Verify the hook
  before every commit."*), the way most plain instructions are worded.

Each list item counts as its own unit, so the command opening a bullet is
seen. Every rule sentence is looked for, with whitespace normalised and link
targets ignored (a move into a nested file rewrites them), in:

- the file after the pass, where the rule stayed always-on;
- a file the after-file links to by a relative Markdown link, where it moved
  behind a pointer (reported as ``moved``, with the target, so the maintainer
  can check the pointer names its trigger);
- any ``--also`` file, for text that moved somewhere the file does not link.

A sentence found nowhere is ``missing`` and the exit code is 1. A rewrite pass
changes wording on purpose, so after one, ``missing`` is the list of approved
paragraph edits to review, not an automatic failure.

``--before`` and ``--after`` take a path, or ``REV:PATH`` to read a file at a
git revision (for example ``main:AGENTS.md``).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

NORMATIVE = re.compile(r"\b(must|shall|never|always|required|do not|don't)\b", re.IGNORECASE)
FENCE = re.compile(r"^\s*(```|~~~)")
TOC = re.compile(r"<!--\s*(START|END) doctoc", re.IGNORECASE)
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SENTENCE_END = re.compile(r"(?<=[.!?:])\s+(?=[A-Z*`_(\"'\[])")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
LEADING_MARKUP = re.compile(r"^[\s>*_`\"'(\[]+")
FIRST_WORD = re.compile(r"[A-Za-z][A-Za-z-]*")

# Verbs that open an instruction in the imperative. A sentence starting with
# one ("Run ...", "Keep ...", "Re-read ...") is a rule even with no "must" in it.
_IMPERATIVE_WORDS = """
    add apply ask avoid bump check choose cite clean commit compare confirm
    copy create cut delete describe document draft drop edit enable ensure
    escape exclude fetch file fill find fix flag follow format generate give
    grep hand include install keep label land leave limit link list load
    look make mark measure mention merge move name note open pass paste pick
    pin place point post prefer prepare probe propose prove push put quote
    read rebase record redact refer regenerate remove rename render replace
    report request require reset resolve restamp restore return review
    rewrite run say scope scrub search send set show skip sign split stage
    start state stop strip submit substitute summarise summarize surface
    suggest switch tag tell test treat trim update use validate verify wait
    warn wrap write
"""
IMPERATIVE = frozenset(_IMPERATIVE_WORDS.split())


def read(spec: str) -> tuple[str, Path | None]:
    """Return the text of ``spec`` and, for a working-tree path, its location."""
    path = Path(spec)
    if path.is_file():
        return path.read_text(encoding="utf-8"), path
    if ":" in spec:
        result = subprocess.run(["git", "show", spec], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout, None
    raise SystemExit(f"error: cannot read {spec!r} as a file or REV:PATH")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def match_key(text: str) -> str:
    """Normalised text with link targets dropped, so a rewritten link still matches."""
    return normalise(re.sub(r"\]\([^)\s]*\)", "]()", text))


def paragraphs(text: str) -> list[str]:
    """Prose paragraphs, with code fences and the generated TOC left out."""
    out: list[str] = []
    current: list[str] = []
    in_fence = in_toc = False
    for line in text.splitlines():
        if TOC.search(line):
            in_toc = not in_toc if "START" in line.upper() else False
            continue
        if in_toc:
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.lstrip().startswith("#"):
            # A heading is a label, not a rule; it ends the paragraph above.
            if current:
                out.append(" ".join(current))
                current = []
            continue
        if LIST_ITEM.match(line):
            # Each list item is its own unit, so the verb opening it is seen.
            if current:
                out.append(" ".join(current))
            current = [LIST_ITEM.sub("", line, count=1)]
            continue
        if line.strip():
            current.append(line)
        elif current:
            out.append(" ".join(current))
            current = []
    if current:
        out.append(" ".join(current))
    return out


def is_imperative(sentence: str) -> bool:
    word = FIRST_WORD.match(LEADING_MARKUP.sub("", sentence))
    if not word:
        return False
    verb = word.group(0).lower()
    if verb.startswith("re-"):
        verb = verb[3:]
    return verb in IMPERATIVE


def is_rule(sentence: str) -> bool:
    return bool(NORMATIVE.search(sentence)) or is_imperative(sentence)


def rules(text: str) -> list[str]:
    found: list[str] = []
    for paragraph in paragraphs(text):
        for sentence in SENTENCE_END.split(normalise(paragraph)):
            sentence = sentence.strip()
            if is_rule(sentence) and sentence not in found:
                found.append(sentence)
    return found


def linked_files(text: str, base: Path) -> list[Path]:
    seen: list[Path] = []
    for target in LINK.findall(text):
        if "://" in target or target.startswith("mailto:"):
            continue
        path = (base / target).resolve()
        if path.is_file() and path.suffix == ".md" and path not in seen:
            seen.append(path)
    return seen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--before", required=True, help="path or REV:PATH")
    parser.add_argument("--after", required=True, help="path (working tree)")
    parser.add_argument(
        "--also",
        action="append",
        default=[],
        type=Path,
        help="another file where moved text may live (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    before_text, _ = read(args.before)
    after_text, after_path = read(args.after)
    if after_path is None:
        raise SystemExit("error: --after must be a working-tree path")

    homes: list[tuple[str, str]] = [("", match_key(after_text))]
    for path in [*linked_files(after_text, after_path.parent), *args.also]:
        homes.append((str(path), match_key(Path(path).read_text(encoding="utf-8"))))

    kept: list[str] = []
    moved: list[dict] = []
    missing: list[str] = []
    for rule in rules(before_text):
        home = next((name for name, text in homes if match_key(rule) in text), None)
        if home is None:
            missing.append(rule)
        elif home == "":
            kept.append(rule)
        else:
            moved.append({"rule": rule, "to": home})

    result = {
        "rules_before": len(kept) + len(moved) + len(missing),
        "kept": len(kept),
        "moved": moved,
        "missing": missing,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"{result['rules_before']} rule sentences: {len(kept)} kept, "
            f"{len(moved)} moved, {len(missing)} missing"
        )
        by_target: dict[str, int] = {}
        for item in moved:
            by_target[item["to"]] = by_target.get(item["to"], 0) + 1
        for target, count in by_target.items():
            print(f"  moved {count} to {target}")
        for rule in missing:
            print(f"  MISSING: {rule}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
