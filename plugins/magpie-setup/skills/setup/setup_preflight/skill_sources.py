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
"""Has an organization moved the pin of a source this project trusts?

An organization curates skill sources in `organizations/<org>/skill-sources.md`
and moves a curated pin when the source tags a newer version.  An adopter's
committed pin, in `<project-config>/skill-sources.md`, moves only when the
adopter bumps it.  `setup update` refreshes the snapshot, and with it the
organization's catalogue, so after that step both pins are on disk and the
comparison needs no network.

`pins` compares them, per id the trust list names:

- ``moved`` — same skill, the curated version is higher: propose the bump.
- ``same`` — same ref and commit.
- ``tag-moved`` — same ref, a different commit: a moved tag is suspicious,
  never a bump to make.
- ``adopter-ahead`` — the adopter pins a newer version than the curator.
- ``not-comparable`` — a ref with no ``<name>-<version>`` shape, or two
  different names.
- ``not-curated`` — a full descriptor of the adopter's own, or an id the
  catalogue does not carry.
- ``declined`` — ``moved``, but the adopter declined this curated ref
  before; asked again only once the curated ref moves past it.

`decline` records that answer under ``skill_source_pins`` in
`reconciled.json`, in this checkout's own layer (`layers.stamp_dir`).
Nothing here edits a trust list or a lock: the skill stages the bump after
the operator says yes.

Stdlib only, like the rest of the package.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from .layers import STAMP_NAME, merged_stamp, stamp_dir, write_stamp

BLOCK = "skill_source_pins"
_VERSIONED_REF = re.compile(r"^(?P<name>.+?)-v?(?P<version>\d+(?:\.\d+)*)$")
_FENCE = re.compile(r"^```(\w*)\s*$")


def _yaml_fence_lines(text: str) -> Iterator[str]:
    inside = False
    for line in text.splitlines():
        fence = _FENCE.match(line.strip())
        if fence:
            inside = not inside and fence.group(1) in ("yaml", "yml")
            continue
        if inside:
            yield line


def parse_descriptors(text: str) -> dict[str, dict[str, str]]:
    """The top-level scalar keys of each `- id:` entry in the yaml fences, by id.

    Commented lines declare nothing, so the template's examples are skipped;
    so is a placeholder id (`<source-id>`).  A later entry with the same id
    is ignored.  Nested blocks (`layout:`, `provides:`) are recorded as
    present keys with an empty value.
    """
    found: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in _yaml_fence_lines(text):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        entry = re.match(r"^-\s+id:\s*(\S+)\s*$", raw)
        if entry:
            source_id = entry.group(1).strip("'\"")
            current = None
            if "<" not in source_id and source_id not in found:
                current = found[source_id] = {"id": source_id}
            continue
        if current is None:
            continue
        pair = re.match(r"^  ([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if pair:
            current.setdefault(pair.group(1), pair.group(2).split(" #", 1)[0].strip().strip("'\""))
    return found


def _version(ref: str) -> tuple[str, tuple[int, ...]] | None:
    match = _VERSIONED_REF.match(ref)
    if match is None:
        return None
    return match.group("name"), tuple(int(part) for part in match.group("version").split("."))


def _full_descriptor(entry: dict[str, str]) -> bool:
    """An entry that declares its own source rather than referencing a curated one."""
    return "method" in entry or "url" in entry


def compare(adopter: dict[str, str], curated: dict[str, str] | None, declined: str | None) -> str:
    if curated is None or _full_descriptor(adopter):
        return "not-curated"
    ours, theirs = adopter.get("ref", ""), curated.get("ref", "")
    if ours == theirs:
        if adopter.get("commit") and curated.get("commit") and adopter["commit"] != curated["commit"]:
            return "tag-moved"
        return "same"
    mine, curators = _version(ours), _version(theirs)
    if mine is None or curators is None or mine[0] != curators[0]:
        return "not-comparable"
    if curators[1] <= mine[1]:
        return "adopter-ahead"
    if declined == theirs:
        return "declined"
    return "moved"


def _declined(root: Path) -> dict[str, str]:
    block = merged_stamp(root).get(BLOCK)
    if not isinstance(block, dict):
        return {}
    return {
        source_id: entry["declined"]
        for source_id, entry in block.items()
        if isinstance(entry, dict) and isinstance(entry.get("declined"), str)
    }


def pins(root: Path, trust_list: Path, catalogue: Path | None) -> list[dict[str, str | None]]:
    """One row per source the trust list names, in its order."""
    trusted = parse_descriptors(trust_list.read_text(encoding="utf-8"))
    curated = (
        parse_descriptors(catalogue.read_text(encoding="utf-8")) if catalogue and catalogue.is_file() else {}
    )
    declined = _declined(root)
    rows: list[dict[str, str | None]] = []
    for source_id, entry in trusted.items():
        theirs = curated.get(source_id)
        rows.append(
            {
                "id": source_id,
                "state": compare(entry, theirs, declined.get(source_id)),
                "ref": entry.get("ref"),
                "commit": entry.get("commit"),
                "curated_ref": theirs.get("ref") if theirs else None,
                "curated_commit": theirs.get("commit") if theirs else None,
            }
        )
    return rows


def decline(root: Path, source_id: str, curated_ref: str, today: date | None = None) -> dict[str, str]:
    """Record that the operator kept their pin over `curated_ref`; every other key is kept.

    A stamp that exists but cannot be parsed is left alone: `ValueError`.
    """
    directory = stamp_dir(root)
    path = directory / STAMP_NAME
    stamp: dict[str, object] = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} is not a JSON object; not overwriting it")
        stamp = loaded
    raw = stamp.get(BLOCK)
    block: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    entry = {"declined": curated_ref, "at": (today or date.today()).isoformat()}
    block[source_id] = entry
    stamp[BLOCK] = block
    write_stamp(directory, stamp)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.skill_sources", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    compare_cmd = sub.add_parser(
        "pins", help="compare the trust list's pins with the organization's catalogue"
    )
    compare_cmd.add_argument("--project-root", type=Path, default=Path("."))
    compare_cmd.add_argument("--trust-list", type=Path, required=True)
    compare_cmd.add_argument(
        "--catalogue", type=Path, help="organizations/<org>/skill-sources.md from the snapshot"
    )
    decline_cmd = sub.add_parser("decline", help="keep this project's pin over a curated ref")
    decline_cmd.add_argument("--project-root", type=Path, default=Path("."))
    decline_cmd.add_argument("--id", required=True)
    decline_cmd.add_argument("--curated-ref", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "pins":
            result: object = pins(args.project_root, args.trust_list, args.catalogue)
        else:
            result = decline(args.project_root, args.id, args.curated_ref)
    except (OSError, ValueError) as exc:
        print(f"skill_sources: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
