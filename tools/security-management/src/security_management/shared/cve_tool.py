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
"""The CVE-record commands the renderers print, through the CVE-tool interface.

The skills never name a CVE tool's own commands: they run `cve-tool
<operation>` (tools/cve-tool), which resolves `cve_authority.tool` and runs
that tool's adapter. Arguments after the operation are the adapter's own;
`command` shell-quotes each one, so callers pass raw values.

The default command runs `cve-tool` from `STABLE`, the fixed link the
magpie-security-tools SessionStart hook keeps on the plugin's tools/: the one
spelling the secure setup lets out of the sandbox (with a prompt on every
call), since `cve-tool` needs the CVE tool's session the sandbox denies.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from typing import Any

from security_management.shell import w

STABLE = "~/.claude/magpie/security-tools/cve-tool"
#: Where a framework checkout or snapshot install keeps the tool, run sandboxed.
PROJECT = "<framework>/tools/cve-tool"


def stable_installed() -> bool:
    """Whether the plugin's link exists here; snapshot installs have no plugin."""
    return os.path.isdir(os.path.expanduser(STABLE))


def command(data: Mapping[str, Any], operation: str, *args: object) -> str:
    """`uvx --from <STABLE> cve-tool <operation> <args>`.

    `data["cve_tool_project"]` names another checkout instead, run as
    `uv run --project <path> cve-tool …`; without the plugin's link (a
    framework checkout or snapshot install) that is `<framework>/tools/cve-tool`.
    That form stays inside the sandbox.

    Each argument is shell-quoted here, so pass raw values and never quote them first:
    quoting twice breaks a value. `shlex.quote`, not `w`, because an argument can come
    from the tracker (an allocation title), and `w` leaves a `<placeholder>`-shaped value bare.
    """
    quoted = (shlex.quote(str(arg)) for arg in args)
    project = data.get("cve_tool_project") or (None if stable_installed() else PROJECT)
    if project:
        return " ".join(("uv run --project", w(str(project)), "cve-tool", operation, *quoted))
    # The literal `~`, unquoted: the sandbox exclusion and the `ask` rule match this spelling.
    return " ".join(("uvx --from", STABLE, "cve-tool", operation, *quoted))
