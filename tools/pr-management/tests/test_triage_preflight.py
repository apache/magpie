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

import json
from pathlib import Path

from pr_management import config
from pr_management.triage import preflight


def _save(tmp_path: Path, permission: str | None, *pages: list[str]) -> Path:
    path = tmp_path / "preflight.json"
    path.write_text(
        json.dumps(
            [
                {
                    "data": {
                        "viewer": {"login": "me"},
                        "repository": {
                            "viewerPermission": permission,
                            "labels": {"nodes": [{"name": n} for n in names]},
                        },
                    }
                }
                for names in pages
            ]
        )
    )
    return path


ALL = [
    "ready for maintainer review",
    "closed because of multiple quality violations",
    "suspicious changes detected",
]


def test_write_access_with_every_label_passes(tmp_path: Path) -> None:
    r = preflight.check(_save(tmp_path, "WRITE", ALL[:1], ALL[1:]), config.Config())
    assert r["ok"] and r["viewer"] == "me" and r["missing_labels"] == {} and r["warnings"] == []


def test_read_access_blocks(tmp_path: Path) -> None:
    r = preflight.check(_save(tmp_path, "READ", ALL), config.Config())
    assert not r["ok"] and "READ" in r["blocking"]


def test_triage_access_warns_about_workflow_approval(tmp_path: Path) -> None:
    r = preflight.check(_save(tmp_path, "TRIAGE", ALL), config.Config())
    assert r["ok"] and any("WRITE-level" in w for w in r["warnings"])


def test_a_missing_label_degrades_with_a_warning(tmp_path: Path) -> None:
    r = preflight.check(_save(tmp_path, "ADMIN", ALL[:2]), config.Config())
    assert r["ok"] and r["missing_labels"] == {"suspicious_changes": "suspicious changes detected"}
