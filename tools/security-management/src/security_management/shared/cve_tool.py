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
that tool's adapter. Arguments after the operation are the adapter's own
and are passed through, already shell-quoted by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.shell import w

PROJECT = "<framework>/tools/cve-tool"


def command(data: Mapping[str, Any], operation: str, *args: str) -> str:
    """`uv run --project <cve-tool> cve-tool <operation> <args>`; `data["cve_tool_project"]` overrides the path."""
    project = str(data.get("cve_tool_project") or PROJECT)
    return " ".join(("uv run --project", w(project), "cve-tool", operation, *args))
