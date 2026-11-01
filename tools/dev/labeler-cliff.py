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
"""Tell whether a pull request is over the labeler's changed-files label limit.

`actions/labeler` applies no changed-files label at all when more new labels
match than `changed-files-labels-limit`, so a cross-cutting sweep would stay
unlabelled. This script reads the pull request's changed files on stdin, one
per line, computes the labels `.github/labeler.yml` would apply from the same
rules `generate-labeler-config.py` renders it from, and prints
`family:cross-family` when the new ones (those not in `--labels`) are more than
the limit. It prints nothing otherwise, and never touches the network.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

CROSS_FAMILY = "family:cross-family"
_GENERATOR = Path(__file__).resolve().parent / "generate-labeler-config.py"


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_labeler_config", _GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_cache: dict[str, re.Pattern[str]] = {}


def glob_match(glob: str, path: str) -> bool:
    """Match `path` against a labeler glob the way minimatch does (`dot: true`)."""
    if glob not in _cache:
        out, i = "", 0
        while i < len(glob):
            if glob.startswith("**/", i):
                out += "(?:.*/)?"
                i += 3
            elif glob.startswith("**", i):
                out += ".*"
                i += 2
            elif glob[i] == "*":
                out += "[^/]*"
                i += 1
            elif glob[i] == "?":
                out += "[^/]"
                i += 1
            else:
                out += re.escape(glob[i])
                i += 1
        _cache[glob] = re.compile(out + r"\Z")
    return bool(_cache[glob].match(path))


def matched_labels(
    path_rules: dict[str, list[str]],
    capabilities: dict[str, list[str]],
    excludes: dict[str, tuple[str, ...]],
    files: list[str],
) -> set[str]:
    """The labels `.github/labeler.yml` applies to `files`, before its limit."""
    labels: set[str] = set()
    for label, globs in path_rules.items():
        plain = [g for g in globs if not g.startswith("!")]
        negations = [g[1:] for g in globs if g.startswith("!")]
        if negations:
            # render(): the tools/** tree with its exclusions, OR-ed with the rest.
            tree = "tools/**"
            rest = [g for g in plain if g != tree]
            hit = any(glob_match(g, f) for g in rest for f in files) or any(
                glob_match(tree, f) and not any(glob_match(n, f) for n in negations) for f in files
            )
        else:
            hit = any(glob_match(g, f) for g in plain for f in files)
        if hit:
            labels.add(label)
    for label, tools in capabilities.items():
        for tool in tools:
            root = f"tools/{tool}/**"
            skip = [f"tools/{tool}/{pattern}" for pattern in excludes.get(tool, ())]
            if any(glob_match(root, f) and not any(glob_match(s, f) for s in skip) for f in files):
                labels.add(label)
                break
    return labels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", default="", help="comma-separated labels the pull request already has")
    parser.add_argument("--root", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--count", action="store_true", help="print the new-label count instead")
    args = parser.parse_args(argv)

    gen = _generator()
    root = args.root or gen.REPO_ROOT
    files = [line.strip() for line in sys.stdin if line.strip()]
    existing = {label.strip() for label in args.labels.split(",") if label.strip()}
    labels = matched_labels(gen.load_path_rules(root), gen.load_capabilities(root), gen.EXCLUDES, files)
    new = labels - existing
    if args.count:
        print(len(new))
    elif len(new) > gen.LABELS_LIMIT and CROSS_FAMILY not in existing:
        print(CROSS_FAMILY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
