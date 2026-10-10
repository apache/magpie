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
from __future__ import annotations

from pathlib import Path

import pytest

CONFIG = """# Example — mentoring configuration

## Identifiers

| Key | Value | Notes |
|---|---|---|
| `mentoring_invocation_command` | `/magpie-pr-management:mentor` | x |
| `maintainer_team_handle` | `@acme/committers` | x |
| `max_agent_turns` | `2` | x |

## Convention pointers

| Trigger | Link | One-line label |
|---|---|---|
| Missing version on bug report | `https://example.org/version` | Finding your version |
| Missing repro | `https://example.org/repro` | Filing a reproducible report |
| First-time contributor PR setup | `https://example.org/pr` | Opening a PR |

## Out-of-scope topics

- Security-sensitive design (CVE-adjacent, embargoed work)
- Deprecation timing (which release will drop X)
- License questions (compatibility, header policy)

## AI-attribution footer

```markdown
---

_Drafted by an AI-assisted mentoring tool; a maintainer takes the next look._
```
"""

FOOTER = "---\n\n_Drafted by an AI-assisted mentoring tool; a maintainer takes the next look._"


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cfg"
    d.mkdir()
    (d / "mentoring-config.md").write_text(CONFIG)
    (d / "project.md").write_text("| Key | Value |\n|---|---|\n| `upstream_repo` | `acme/product` |\n")
    return d
