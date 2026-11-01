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
"""pr-management-triage pre-flight checks 2 and 3: viewer permission and the triage labels.

Reads `preflight.json`, the `gql-pr-triage-preflight` save (slurped pages).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import Config

MUTATING = frozenset({"WRITE", "MAINTAIN", "ADMIN"})


def check(path: Path, cfg: Config) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    pages = document if isinstance(document, list) else [document]
    viewer = None
    permission = None
    labels: set[str] = set()
    for page in pages:
        data = (page or {}).get("data") or {}
        viewer = viewer or (data.get("viewer") or {}).get("login")
        repo = data.get("repository") or {}
        permission = permission or repo.get("viewerPermission")
        labels.update(str(n.get("name")) for n in (repo.get("labels") or {}).get("nodes") or [] if n)
    wanted = {
        "ready_for_maintainer_review": cfg.ready_label,
        "quality_violations_close": cfg.quality_close_label,
        "suspicious_changes": cfg.suspicious_label,
    }
    missing = {key: name for key, name in wanted.items() if name and name not in labels}
    warnings = [
        f"label {name!r} ({key}) does not exist on the repo; that action skips the label"
        for key, name in missing.items()
    ]
    blocking = None
    if permission not in MUTATING and permission != "TRIAGE":
        blocking = (
            f"the viewer has {permission or 'no'} access to the upstream repo — ask to be added as a collaborator, "
            "or check you are logged in as the right account"
        )
    elif permission == "TRIAGE":
        warnings.append("TRIAGE permission: workflow approvals will need a WRITE-level maintainer")
    if "ready_for_maintainer_review" in missing:
        warnings.append(
            "without the ready label, mark-ready cannot run at all: it is that action's only purpose"
        )
    return {
        "ok": blocking is None,
        "viewer": viewer,
        "permission": permission,
        "blocking": blocking,
        "missing_labels": missing,
        "warnings": warnings,
    }
