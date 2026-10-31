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

from pr_management.code_review import data

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
