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
"""A configured value can never expand in the shell the release manager pastes into."""

from __future__ import annotations

import shlex
import subprocess

import pytest

from release_management.shell import dq, w

HOSTILE = [
    "$(touch pwned)",
    "`touch pwned`",
    'a" ; touch pwned ; "',
    "a'b",
    "x\\$HOME",
    "a b",
    "hi!",
    "!!",
    "a!$HOME",
]


@pytest.mark.parametrize("value", HOSTILE)
def test_dq_and_w_round_trip_through_a_real_shell(value: str, tmp_path) -> None:
    for quoted in (dq(value), w(value)):
        out = subprocess.run(
            ["sh", "-c", f"printf %s {quoted}"], capture_output=True, text=True, cwd=tmp_path
        )
        assert out.stdout == value
        assert not (tmp_path / "pwned").exists()


def test_w_leaves_ordinary_words_and_placeholders_alone() -> None:
    assert w("apache-foo-1.0.0-source.tar.gz") == "apache-foo-1.0.0-source.tar.gz"
    assert (
        w("https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/")
        == "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/"
    )
    assert w("<asf-id>") == "<asf-id>"
    assert w("a b") == shlex.quote("a b")


def test_dq_keeps_the_recipes_double_quotes() -> None:
    assert dq("apache-foo-1.0.0") == '"apache-foo-1.0.0"'
    assert dq("$HOME") == '"\\$HOME"'


def test_dq_single_quotes_a_value_with_a_bang() -> None:
    assert dq("hi!") == "'hi!'"
    assert dq("it's!") == shlex.quote("it's!")
    assert dq("Release 1.0.0 RC1") == '"Release 1.0.0 RC1"'
