#!/usr/bin/env python3
#
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

"""Refresh generated knowledge-base material in AI tutor prompts.

Each tutor prompt in ``ai-tutors/`` maps to the same-named lesson in
``docs/education/training/``. This script reads that lesson, follows its
``**Source page:**`` link, and injects both files into the tutor's
``## KNOWLEDGE BASE`` section.

Hand-written answer keys below ``### Exercise answer keys``,
``### Self-check answer keys``, or ``### Summary`` are preserved.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AI_TUTORS_DIR = ROOT / "ai-tutors"
TRAINING_DIR = ROOT / "docs" / "education" / "training"
LESSON_GLOB = "lesson-*.md"

KB_HEADING_RE = re.compile(
    r"^## KNOWLEDGE BASE \(teaching content and answer keys\)\s*$",
    re.MULTILINE,
)
PRESERVED_TAIL_RE = re.compile(
    r"^### (?:Exercise answer keys|Self-check answer keys|Summary \(use at close\))\s*$",
    re.MULTILINE,
)
SOURCE_PAGE_RE = re.compile(
    r"^\*\*Source page:\*\*\s+\[[^\]]+\]\((?P<path>[^)]+)\)",
    re.MULTILINE,
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
DOCTOC_RE = re.compile(
    r"<!-- START doctoc generated TOC.*?<!-- END doctoc generated TOC.*?-->\n*",
    re.DOTALL,
)
SPDX_RE = re.compile(r"<!-- SPDX-License-Identifier:.*?-->\n*", re.DOTALL)


@dataclass(frozen=True)
class TutorUpdate:
    tutor: Path
    training_lesson: Path
    source_page: Path
    updated_text: str


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject source lesson knowledge into ai-tutors lesson prompts."
    )
    parser.add_argument(
        "lessons",
        nargs="*",
        help=(
            "Optional tutor filenames to refresh, for example "
            "lesson-01-what-agents-are.md. Defaults to every ai-tutors/lesson-*.md."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any tutor prompt is not up to date; do not write files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would change; do not write files.",
    )
    return parser.parse_args(argv)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def tutor_paths(names: list[str]) -> list[Path]:
    if names:
        return [AI_TUTORS_DIR / name for name in names]
    return sorted(AI_TUTORS_DIR.glob(LESSON_GLOB))


def source_page_for(training_lesson: Path) -> Path:
    lesson_text = read_text(training_lesson)
    match = SOURCE_PAGE_RE.search(lesson_text)
    if not match:
        raise ValueError(f"{training_lesson} has no '**Source page:**' link")

    source_ref = match.group("path").split("#", 1)[0]
    return (training_lesson.parent / source_ref).resolve()


def clean_markdown_for_embedding(text: str) -> str:
    text = SPDX_RE.sub("", text)
    text = DOCTOC_RE.sub("", text)
    text = MARKDOWN_LINK_RE.sub(r"\1 (\2)", text)
    return text.strip()


def blockquote(text: str) -> str:
    return "\n".join(">" if line == "" else f"> {line}" for line in text.splitlines())


def render_generated_kb(training_lesson: Path, source_page: Path) -> str:
    source_label = source_page.relative_to(ROOT).as_posix()
    lesson_label = training_lesson.relative_to(ROOT).as_posix()
    source_body = blockquote(clean_markdown_for_embedding(read_text(source_page)))
    lesson_body = blockquote(clean_markdown_for_embedding(read_text(training_lesson)))

    return "\n".join(
        [
            "### Source page (teaching text)",
            "",
            f"This is the full `{source_label}` page. Teach from it and regenerate from it.",
            "Apache-2.0 licensed.",
            "",
            source_body,
            "",
            "### Lesson wrapper (exercises and self-check)",
            "",
            f"This is the full `{lesson_label}` lesson wrapper. Use it for exercise wording,",
            "learning objectives, learner-facing self-check questions, and embedded",
            "self-check answers.",
            "",
            lesson_body,
            "",
        ]
    )


def refresh_tutor(tutor: Path) -> TutorUpdate:
    if not tutor.is_file():
        raise FileNotFoundError(f"tutor prompt does not exist: {tutor}")

    training_lesson = TRAINING_DIR / tutor.name
    if not training_lesson.is_file():
        raise FileNotFoundError(
            f"matching training lesson does not exist: {training_lesson}"
        )

    source_page = source_page_for(training_lesson)
    if not source_page.is_file():
        raise FileNotFoundError(f"source page does not exist: {source_page}")

    text = read_text(tutor)
    kb_match = KB_HEADING_RE.search(text)
    if not kb_match:
        raise ValueError(f"{tutor} has no '## KNOWLEDGE BASE' section")

    generated_kb = render_generated_kb(training_lesson, source_page)
    tail_match = PRESERVED_TAIL_RE.search(text, kb_match.end())
    tail = text[tail_match.start() :].strip() if tail_match else ""
    prefix = text[: kb_match.end()].rstrip()

    updated_parts = [prefix, "", generated_kb.rstrip()]
    if tail:
        updated_parts.extend(["", tail])

    return TutorUpdate(
        tutor=tutor,
        training_lesson=training_lesson,
        source_page=source_page,
        updated_text="\n".join(updated_parts).rstrip() + "\n",
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    changed: list[Path] = []

    try:
        updates = [refresh_tutor(path) for path in tutor_paths(args.lessons)]
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    for update in updates:
        original = read_text(update.tutor)
        if original == update.updated_text:
            continue

        changed.append(update.tutor)
        if not args.check and not args.dry_run:
            write_text(update.tutor, update.updated_text)

    for path in changed:
        print(path.relative_to(ROOT).as_posix())

    if args.check and changed:
        print(
            f"{len(changed)} AI tutor prompt(s) need knowledge-base refresh.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
