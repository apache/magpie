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
"""GraphQL query construction + `gh` invocation.

Kept separate from the classifier so tests can replay canned
responses without shelling out to `gh`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

_ISSUE_BLOCK = """\
    i{n}: issue(number: {n}) {{
      number state closedAt updatedAt
      labels(first: 30) {{ nodes {{ name }} }}
      comments(last: 1) {{
        nodes {{ author {{ login }} createdAt body }}
      }}
    }}"""


def build_query(owner: str, name: str, numbers: Sequence[int]) -> str:
    """Build the aliased multi-field GraphQL query.

    The aliased-field form (``i<N>: issue(number: <N>)``) lets one
    round-trip fetch state for an arbitrary number of issues. For
    a 30-issue sweep the request is ~3 KB and the response is
    ~50-130 KB depending on rollup-comment body length.
    """
    if not numbers:
        raise ValueError("numbers must be non-empty")
    blocks = "\n".join(_ISSUE_BLOCK.format(n=n) for n in numbers)
    return f'query {{\n  repository(owner: "{owner}", name: "{name}") {{\n{blocks}\n  }}\n}}\n'


def fetch_state(
    owner: str,
    name: str,
    numbers: Sequence[int],
    gh_path: str = "gh",
) -> dict[str, Any]:
    """Invoke `gh api graphql` and return the parsed JSON response.

    Raises :class:`SystemExit` if `gh` exits non-zero — the
    underlying stderr is forwarded so the caller sees the real
    error (auth, rate limit, etc.).
    """
    query = build_query(owner, name, numbers)
    cmd = [gh_path, "api", "graphql", "--raw-field", f"query={query}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return json.loads(result.stdout)
