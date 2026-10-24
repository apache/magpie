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
"""Quoting for values spliced into the commands the renderers print.

A copy of `release_management.shell` (tools/release-management), kept
byte-for-byte in behaviour: the two packages are separate `uv run --project`
entry points and neither may import the other. Change both together;
`tests/test_shell.py` pins the same cases.

The agent pastes these values into a shell command, so a configured value
(a reporter name in a rollup label, a subject line) must never be able to
expand there: `dq` keeps the recipes' familiar double quotes but escapes
everything a shell would interpret inside them (or single-quotes a value
holding `!`, which double quotes cannot protect from history expansion).
"""

from __future__ import annotations

import re
import shlex

_SAFE = re.compile(r"[A-Za-z0-9_./:=@%+,-]+")
_PLACEHOLDER = re.compile(r"<[A-Za-z0-9_ -]+>")


def dq(value: object) -> str:
    """`value` as one double-quoted shell word: `\\`, `"`, `$` and backquote escaped.

    A `!` cannot be escaped inside double quotes (interactive bash and zsh run
    history expansion on it), so a value containing one is single-quoted instead.
    """
    text = str(value)
    if "!" in text:
        return shlex.quote(text)
    for char in ("\\", '"', "$", "`"):
        text = text.replace(char, "\\" + char)
    return f'"{text}"'


def w(value: object) -> str:
    """`value` as one bare shell word: unchanged when plainly safe or a `<placeholder>`, else shell-quoted."""
    text = str(value)
    if _SAFE.fullmatch(text) or _PLACEHOLDER.fullmatch(text):
        return text
    return shlex.quote(text)
