#
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
"""Magpie's own committed policy loads, and every grant in it names a real operation.

Two pull requests can each add a valid `[callers]` entry and still merge into an
invalid file (the same key declared twice); git merges the lines cleanly, so only
loading the merged policy catches it.
"""

from __future__ import annotations

from pathlib import Path

from vetted_ops import cli, config, git_ops
from vetted_ops import ops as ops_mod

COMMITTED = (
    Path(__file__).resolve().parents[3] / ".apache-magpie-overrides" / "tools" / "vetted-ops" / "config.toml"
)


def test_the_committed_policy_loads() -> None:
    assert cli  # importing the CLI registers every operation module
    policy = config.load(COMMITTED)
    assert policy.upstream_repo == "apache/magpie"


def test_every_granted_operation_exists() -> None:
    known = set(ops_mod.OPS) | set(git_ops.OPS)
    policy = config.load(COMMITTED)
    unknown = {caller: sorted(ops - known) for caller, ops in policy.callers.items() if ops - known}
    assert unknown == {}
