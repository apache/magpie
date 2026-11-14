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
"""Save names built from repository paths."""

from __future__ import annotations

import re

import pytest

from pr_management.code_review import cli, data

# The rule vetted-ops applies to every `--save` name (`_SAVE_NAME` in vetted_ops/ops.py).
SAVE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

LONG = "plugins/magpie-security-tools/tools/security-management/src/security_management/issue_sync/state.py"


def test_a_short_path_keeps_its_readable_slug() -> None:
    assert data.slug("tools/foo/bar.py") == "tools_foo_bar.py"


@pytest.mark.parametrize("path", ["tools/foo/bar.py", LONG, "x/" * 200 + "y.py"])
def test_the_path_commits_save_name_is_one_vetted_ops_accepts(path: str) -> None:
    assert SAVE_NAME.match(f"path-commits-{data.slug(path)}.json")


def test_long_paths_that_share_a_stem_get_different_names() -> None:
    assert data.slug(LONG) != data.slug(LONG.replace("state.py", "other.py"))


def test_from_node_accepts_rollup_when_commit_oid_matches_head_ref_oid() -> None:
    node = {
        "number": 1,
        "headRefOid": "3ac12395",
        "latest": {
            "nodes": [
                {
                    "commit": {
                        "oid": "3ac12395",
                        "statusCheckRollup": {
                            "state": "SUCCESS",
                            "contexts": {
                                "nodes": [
                                    {
                                        "__typename": "CheckRun",
                                        "name": "build",
                                        "conclusion": "SUCCESS",
                                        "status": "COMPLETED",
                                    }
                                ]
                            },
                        },
                    }
                }
            ]
        },
    }
    pr = data.from_node(node)
    assert pr.head_sha == "3ac12395"
    assert pr.rollup_state == "SUCCESS"
    assert len(pr.contexts) == 1
    assert pr.contexts[0].name == "build"
    assert pr.contexts[0].conclusion == "SUCCESS"


def test_from_node_discards_rollup_when_commit_oid_mismatches_head_ref_oid() -> None:
    # Guards against a lagging commit edge where latest: commits(last: 1)
    # has not advanced to headRefOid (Direction 1 of #2034).
    node = {
        "number": 272,
        "headRefOid": "3ac12395",
        "latest": {
            "nodes": [
                {
                    "commit": {
                        "oid": "4eb3567c",
                        "statusCheckRollup": {
                            "state": "SUCCESS",
                            "contexts": {
                                "nodes": [
                                    {
                                        "__typename": "CheckRun",
                                        "name": "build",
                                        "conclusion": "SUCCESS",
                                        "status": "COMPLETED",
                                    }
                                ]
                            },
                        },
                    }
                }
            ]
        },
    }
    pr = data.from_node(node)
    assert pr.head_sha == "3ac12395"
    assert pr.rollup_state is None
    assert pr.contexts == ()
    assert pr.pending_not_required == ()
    assert pr.ci_outdated_query is False


def test_from_node_discards_rollup_and_flags_outdated_query_when_commit_oid_missing() -> None:
    # Simulates query skew: an older vetted-ops installation that did not request `oid`
    # under latest: commits(last: 1). Rollup is discarded for safety, but flagged as outdated.
    node = {
        "number": 1,
        "headRefOid": "3ac12395",
        "latest": {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": {
                            "state": "SUCCESS",
                            "contexts": {"nodes": []},
                        },
                    }
                }
            ]
        },
    }
    pr = data.from_node(node)
    assert pr.rollup_state is None
    assert pr.contexts == ()
    assert pr.ci_outdated_query is True
    # The headline names the cause, rather than reading as "none reported".
    assert "out of date" in cli._ci_line(pr, real=False)


def test_from_node_discards_rollup_when_head_ref_oid_missing() -> None:
    node = {
        "number": 1,
        "latest": {
            "nodes": [
                {
                    "commit": {
                        "oid": "3ac12395",
                        "statusCheckRollup": {
                            "state": "SUCCESS",
                            "contexts": {"nodes": []},
                        },
                    }
                }
            ]
        },
    }
    pr = data.from_node(node)
    assert pr.rollup_state is None
    assert pr.contexts == ()


def test_from_node_accepts_rollup_case_insensitively() -> None:
    node = {
        "number": 1,
        "headRefOid": "3AC12395",
        "latest": {
            "nodes": [
                {
                    "commit": {
                        "oid": "  3ac12395  ",
                        "statusCheckRollup": {
                            "state": "SUCCESS",
                            "contexts": {"nodes": []},
                        },
                    }
                }
            ]
        },
    }
    pr = data.from_node(node)
    assert pr.head_sha == "3AC12395"
    assert pr.rollup_state == "SUCCESS"
