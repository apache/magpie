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
"""Insert an Apache-2.0 licence header into Markdown and `.gitignore` files.

Apache RAT (see `.github/workflows/rat.yml`) requires every scanned file
to carry an approved licence header. Markdown carries no comment header by
convention, so this script stamps an SPDX identifier and the licence URL
that RAT recognises as an approved licence. `.gitignore` files are
hash-comment config, so they get the full ASF header (the same block
`.gitattributes` and `.pre-commit-config.yaml` carry) — matching the
project convention that source/config files carry the full header while
Markdown carries the SPDX identifier.

Placements, chosen per file so the stamp never breaks downstream
parsers:

* **`.gitignore`** — the full ASF licence header as `#` comment lines,
  prepended before the ignore patterns (a leading comment block is inert
  to git's ignore parser)::

      # Licensed to the Apache Software Foundation (ASF) under one
      # ... (full ASF header) ...
      # under the License.


* **Plain Markdown** — a two-line HTML comment on the first line::

      <!-- SPDX-License-Identifier: Apache-2.0
           https://www.apache.org/licenses/LICENSE-2.0 -->

* **Files with YAML front matter** (first line is exactly ``---``, e.g.
  `SKILL.md` and spec files) — the same two lines as YAML comments,
  inserted *inside* the front matter, so line 1 stays ``---`` and no new
  key is introduced that a front-matter validator might reject::

      ---
      # SPDX-License-Identifier: Apache-2.0
      # https://www.apache.org/licenses/LICENSE-2.0
      name: ...

The operation is idempotent: a file that already carries any
``SPDX-License-Identifier:`` declaration — or the full ASF header's first
line — in its leading lines is left untouched, so a hand-written header in
a different comment style is never double-stamped.

Usage::

    # Stamp specific files (the pre-commit / prek entry point; prek passes
    # the staged Markdown / .gitignore files as arguments). Exits non-zero
    # if any file was modified, so the commit fails and the contributor
    # re-stages the now-stamped file — the same convention as
    # end-of-file-fixer.
    tools/dev/add-license-headers.py path/to/file.md ...

    # Stamp every tracked Markdown and .gitignore file in the repository.
    tools/dev/add-license-headers.py --all
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_LICENSE_URL = "https://www.apache.org/licenses/LICENSE-2.0"

# Plain Markdown: a two-line HTML comment carrying the SPDX identifier and
# the licence URL.
SPDX_HTML = f"<!-- SPDX-License-Identifier: Apache-2.0\n     {_LICENSE_URL} -->"

# YAML front matter: the same two lines as YAML comments, inserted after
# the opening `---` so line 1 stays `---` and no key is introduced.
SPDX_YAML = f"# SPDX-License-Identifier: Apache-2.0\n# {_LICENSE_URL}"

# Full ASF licence header as `#` comments, for hash-comment config files
# that carry no SPDX convention (`.gitignore`) — the same block
# `.gitattributes` and `.pre-commit-config.yaml` carry.
ASF_HEADER_HASH = """\
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
# under the License."""

# How many leading lines to scan for an existing SPDX declaration.
_SCAN_LINES = 12

# Paths never stamped, mirroring the Markdown entries in `.rat-excludes`.
# The third-party-licence detection fixtures deliberately carry non-Apache
# (GPL / EPL / …) licence text as eval input; an Apache-2.0 stamp would be
# semantically wrong and corrupt the eval. RAT excludes them too, so they
# need no header. Kept in the script (not just the prek `exclude:`) so a
# direct or `--all` invocation cannot stamp them either.
EXCLUDE_PREFIXES = (
    "tools/skill-evals/evals/pr-management-code-review/"
    "step-4-third-party-license/fixtures/",
)


def _already_stamped(lines: list[str]) -> bool:
    """True if the file already carries an SPDX licence declaration.

    Matches any existing ``SPDX-License-Identifier:`` line in the leading
    lines — not just the exact stamp this script writes — so a file that
    already has a header (in any comment style, e.g. a hand-written
    multi-line HTML comment) is left untouched rather than double-stamped.
    A bare mention of the token without a ``:`` value (prose describing
    SPDX) is not treated as a declaration, so such a file still gets a real
    header. The full ASF header (`.gitignore`) carries no SPDX token, so its
    first line is recognised too.
    """
    for line in lines[:_SCAN_LINES]:
        if "SPDX-License-Identifier:" in line:
            return True
        if "Licensed to the Apache Software Foundation" in line:
            return True
    return False


def stamp(path: Path) -> bool:
    """Stamp *path* in place. Return True if the file was modified."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if _already_stamped(lines):
        return False
    if not text:
        # An empty file has no content to license; leave it be.
        return False
    if path.name == ".gitignore":
        # Hash-comment config: full ASF header, then a blank line before the
        # existing patterns (a leading comment block is inert to git).
        new_text = ASF_HEADER_HASH + "\n\n" + text
    elif lines[0].rstrip("\n") == "---":
        new_text = lines[0] + SPDX_YAML + "\n" + "".join(lines[1:])
    else:
        new_text = SPDX_HTML + "\n\n" + text
    path.write_text(new_text, encoding="utf-8")
    return True


def _is_target(name: str) -> bool:
    """Files this script stamps: Markdown and `.gitignore`."""
    return name.endswith(".md") or name == ".gitignore"


def _tracked_targets() -> list[Path]:
    out = subprocess.check_output(
        ["git", "ls-files", "*.md", ".gitignore", "**/.gitignore"], text=True
    )
    return [Path(p) for p in out.splitlines()]


def main(argv: list[str]) -> int:
    args = argv[1:]
    if "--all" in args:
        targets = _tracked_targets()
    else:
        targets = [Path(a) for a in args if _is_target(Path(a).name)]

    modified: list[Path] = []
    for path in targets:
        if path.is_symlink() or not path.is_file():
            continue
        if path.as_posix().startswith(EXCLUDE_PREFIXES):
            continue
        if stamp(path):
            modified.append(path)

    for path in modified:
        print(f"stamped licence header: {path}")
    if modified:
        print(f"\n{len(modified)} file(s) stamped. Re-stage them and commit again.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
