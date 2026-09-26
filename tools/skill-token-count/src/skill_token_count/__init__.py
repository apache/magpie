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

"""Reproducible full-file skill token measurements, stamped into each skill.

Each ``SKILL.md`` carries its own count in a generated ``measured_tokens:``
frontmatter line, the same way it carries ``surface_hash:``. A committed
table of every skill in one document made any two skill PRs conflict on its
shared header lines and on adjacent rows; a per-file stamp only conflicts when
two PRs edit the same skill, which they would anyway. The table is rendered on
demand (``--table``) and by the website build, never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote

import tiktoken
from tiktoken.load import read_file_cached

FIELD = "measured_tokens"
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


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
FIELD_LINE_RE = re.compile(rf"^{FIELD}:[ \t]*(\S*)[ \t]*$")


def skill_paths(root: Path) -> list[Path]:
    """Canonical skill files; exclude harness symlinks and external redirects."""
    skills = root / "skills"
    # One level only, and through `skills/<name>/` rather than under it: each
    # entry is a symlink into the family plugin that owns the skill, and
    # `rglob` does not descend a symlinked directory -- it would find nothing.
    # `is_dir()` follows the link, so this reads the same whether the entry is
    # the mirror or (in a fixture, or an adopter's snapshot) a real directory.
    entries = sorted(skills.iterdir()) if skills.is_dir() else []
    paths = [e / "SKILL.md" for e in entries if e.is_dir() and (e / "SKILL.md").is_file()]
    if not paths:
        raise ValueError("No skills/*/SKILL.md files found")
    for path in paths:
        # The file itself is never a link: a harness relay or an external
        # `source.md` redirect is not a skill this measures. The *directory*
        # may be, which is how the mirror reaches the plugin that owns it.
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Skill must be a regular in-tree file: {path}")
    return paths


def split_stamp(source: str) -> tuple[str, str | None]:
    """Return (source without its own stamp line, the stamped value or None).

    The stamp is excluded from what it measures, so writing it never changes
    the count it records. Only the frontmatter is searched.
    """
    match = FRONTMATTER_RE.match(source)
    if not match:
        return source, None
    kept, value = [], None
    for line in match.group(1).split("\n"):
        field = FIELD_LINE_RE.match(line)
        if field:
            value = field.group(1)
        else:
            kept.append(line)
    return "---\n" + "\n".join(kept) + "\n---\n" + source[match.end() :], value


def measure(source: str, encoder: tiktoken.Encoding) -> int:
    """Full UTF-8 file, frontmatter and comments included, minus its own stamp."""
    return len(encoder.encode_ordinary(split_stamp(source)[0]))


def stamp(source: str, count: int) -> str:
    """Place the stamp immediately after `license:`.

    `surface_hash:` sits immediately *before* `license:`; anchoring on the other
    side keeps the two stampers from reordering each other's line, so each tool
    is idempotent whichever runs last.
    """
    stripped, _ = split_stamp(source)
    match = FRONTMATTER_RE.match(stripped)
    if not match:
        raise ValueError("no YAML frontmatter to stamp")
    lines = match.group(1).split("\n")
    try:
        index = next(i for i, line in enumerate(lines) if line.startswith("license:")) + 1
    except StopIteration:
        raise ValueError(f"no 'license:' line to anchor {FIELD} to") from None
    lines.insert(index, f"{FIELD}: {count}")
    return "---\n" + "\n".join(lines) + "\n---\n" + stripped[match.end() :]


def measure_all(root: Path) -> list[tuple[Path, str, int, str | None]]:
    """(path, normalized source, measured count, stamped value) per skill."""
    encoder = offline_encoding()
    rows = []
    for path in skill_paths(root):
        # Normalize CRLF/CR exactly as text-mode reading does, across platforms.
        source = path.read_text(encoding="utf-8")
        rows.append((path, source, measure(source, encoder), split_stamp(source)[1]))
    return rows


def table(root: Path) -> str:
    """The markdown table the website renders; never committed."""
    lines = [
        f"Tokenizer: **tiktoken {version('tiktoken')}, `{ENCODING}`**. Method: full UTF-8 file,",
        f"including frontmatter and comments, excluding the `{FIELD}:` line itself;",
        "line endings normalized to LF; special-token spellings counted as ordinary text.",
        "",
        "| Skill file | Measured tokens |",
        "|---|---:|",
    ]
    for path, _, count, _ in measure_all(root):
        name = path.relative_to(root).as_posix()
        label = name.removeprefix("skills/").removesuffix("/SKILL.md").replace("|", "&#124;")
        lines.append(f"| [{label}](../{quote(name, safe='/')}) | {count:,} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root (default: cwd)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail on a missing or stale stamp (default)")
    mode.add_argument("--write", action="store_true", help=f"Stamp `{FIELD}:` into every SKILL.md")
    mode.add_argument("--table", action="store_true", help="Print the per-skill table to stdout")
    mode.add_argument(
        "--prepare-tokenizer", action="store_true", help="Download and verify the vocabulary cache"
    )
    args = parser.parse_args(argv)
    try:
        if args.prepare_tokenizer:
            prepare_tokenizer()
            print(f"Verified tokenizer cache: {vocabulary_path()}")
            return 0
        if args.table:
            print(table(args.root))
            return 0
        stale = []
        for path, source, count, stamped in measure_all(args.root):
            if stamped == str(count):
                continue
            if args.write:
                path.write_text(stamp(source, count), encoding="utf-8", newline="\n")
                print(f"Stamped {FIELD}: {count} in {path.relative_to(args.root)}")
            else:
                stale.append(
                    f"{path.relative_to(args.root)}: {FIELD} {stamped or 'missing'}, measured {count}"
                )
        if stale:
            print("Skill token stamps are stale:", *stale, sep="\n  ", file=sys.stderr)
            print(
                "Run: uv run --project tools/skill-token-count skill-token-count --write",
                file=sys.stderr,
            )
            return 1
        return 0
    except (OSError, ValueError) as exc:
        print(f"skill-token-count: {exc}", file=sys.stderr)
        return 2
