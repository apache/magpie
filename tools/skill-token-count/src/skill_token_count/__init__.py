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

"""Reproducible full-file skill token measurements, independent of Git history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote

import tiktoken
from tiktoken.load import read_file_cached

START = "<!-- BEGIN GENERATED SKILL TOKEN COUNTS -->"
END = "<!-- END GENERATED SKILL TOKEN COUNTS -->"
ENCODING = "cl100k_base"
VOCAB_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
VOCAB_SHA256 = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


def vocabulary_path() -> Path:
    """Use a persistent, sandbox-readable cache outside the checkout."""
    cache = os.environ.get("TIKTOKEN_CACHE_DIR")
    if cache is None:
        cache = str(Path.home() / ".cache/apache-magpie/tiktoken")
        os.environ["TIKTOKEN_CACHE_DIR"] = cache
    if not cache:
        raise ValueError("TIKTOKEN_CACHE_DIR must not disable caching")
    return Path(cache) / hashlib.sha1(VOCAB_URL.encode()).hexdigest()


def prepare_tokenizer() -> None:
    """Explicit installation step; this is the only operation that downloads."""
    vocabulary_path()
    read_file_cached(VOCAB_URL, expected_hash=VOCAB_SHA256)


def offline_encoding() -> tiktoken.Encoding:
    path = vocabulary_path()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != VOCAB_SHA256:
        raise ValueError(
            "Tokenizer cache missing or corrupt. Outside the isolated agent, run: "
            "uv run --project tools/skill-token-count skill-token-count --prepare-tokenizer"
        )
    return tiktoken.get_encoding(ENCODING)


def render(root: Path, measured_on: str = "unrecorded") -> str:
    """Measure canonical files; exclude harness symlinks and external redirects."""
    skills = root / "skills"
    paths = sorted(skills.rglob("SKILL.md"))
    if not paths:
        raise ValueError("No skills/**/SKILL.md files found")
    encoder = offline_encoding()
    rows: list[tuple[str, int, str]] = []
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(skills.resolve()):
            raise ValueError(f"Skill must be a regular in-tree file: {path}")
        # Normalize CRLF/CR exactly as text-mode reading does, across platforms.
        source = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        rows.append((path.relative_to(root).as_posix(), len(encoder.encode_ordinary(source)), digest))
    tokenizer = version("tiktoken")
    manifest = json.dumps(
        {"schema": 1, "tokenizer": tokenizer, "encoding": ENCODING, "files": rows},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    lines = [
        START,
        "",
        f"Measured on (UTC): {measured_on}.",
        "",
        f"Tokenizer: **tiktoken {tokenizer}, `{ENCODING}`**. Method: full UTF-8 file,",
        "including frontmatter and comments; line endings normalized to LF;",
        "special-token spellings counted as ordinary text.",
        f"Coverage: **{len(rows)} of {len(paths)} local `skills/**/SKILL.md` files**.",
        "External `source.md` redirects and harness symlinks are excluded.",
        "",
        f"Measurement manifest SHA-256: `{fingerprint}`.",
        "",
        "| Skill file | Measured tokens | Source SHA-256 (first 16 characters) |",
        "|---|---:|---|",
    ]
    for name, count, digest in rows:
        label = name.removeprefix("skills/").removesuffix("/SKILL.md").replace("|", "&#124;")
        lines.append(f"| [{label}](../{quote(name, safe='/')}) | {count:,} | `{digest[:16]}` |")
    lines.extend(["", END])
    return "\n".join(lines)


def replace_block(document: str, block: str) -> str:
    """Refuse ambiguous markers instead of overwriting unrelated documentation."""
    if document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("Expected exactly one pair of generated token-count markers")
    start = document.index(START)
    end = document.index(END)
    if end < start:
        raise ValueError("Token-count markers are reversed")
    return document[:start] + block + document[end + len(END) :]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root (default: cwd)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail on drift without writing (default)")
    mode.add_argument("--write", action="store_true", help="Regenerate the marked documentation block")
    mode.add_argument(
        "--prepare-tokenizer", action="store_true", help="Download and verify the vocabulary cache"
    )
    args = parser.parse_args(argv)
    try:
        if args.prepare_tokenizer:
            prepare_tokenizer()
            print(f"Verified tokenizer cache: {vocabulary_path()}")
            return 0
        target = args.root / "docs/mode-economics.md"
        original = target.read_text(encoding="utf-8")
        stamp = re.search(r"^Measured on \(UTC\): (\d{4}-\d{2}-\d{2})\.$", original, re.MULTILINE)
        measured_on = "unrecorded"
        if stamp:
            measured_on = date.fromisoformat(stamp[1]).isoformat()
        block = render(args.root, measured_on)
        updated = replace_block(original, block)
        if original == updated and stamp:
            return 0
        if args.write:
            # Stamp only regeneration, never a check or an unchanged write.
            # UTC rather than local time keeps the date's meaning explicit.
            block = block.replace(
                f"Measured on (UTC): {measured_on}.",
                f"Measured on (UTC): {datetime.now(UTC).date().isoformat()}.",
            )
            updated = replace_block(original, block)
            target.write_text(updated, encoding="utf-8", newline="\n")
            print(f"Updated {target}")
            return 0
        print(
            "Skill token measurements are stale. Run: "
            "uv run --project tools/skill-token-count skill-token-count --write",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as exc:
        print(f"skill-token-count: {exc}", file=sys.stderr)
        return 2
