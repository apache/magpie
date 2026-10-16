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
"""Search keywords safe to single-quote into a plain `gh search` call.

Report-derived keywords are attacker-controlled. The agent writes them to a
file with its Write tool (no shell tokenisation), and this module keeps only
an allowlist of characters — the equivalent of `tr -cd 'A-Za-z0-9._ -'`, or
`tr -cd 'A-Za-z0-9._+-'` for an email local-part. On top of `tr` it collapses
runs of spaces and drops the whole leading run of spaces and `-` (`-- --help` is `help`), so the cleaned string can never be read
as a `gh` flag. It reads only from a file: the raw keyword never travels in argv.
"""

from __future__ import annotations

import re
from pathlib import Path

ALLOWLISTS: dict[str, re.Pattern[str]] = {
    "keywords": re.compile(r"[^A-Za-z0-9._ -]"),
    "email-local": re.compile(r"[^A-Za-z0-9._+-]"),
}


def clean(raw: str, kind: str = "keywords") -> str:
    if kind not in ALLOWLISTS:
        raise ValueError(f"unknown keyword kind {kind!r}")
    text = re.sub(r" +", " ", ALLOWLISTS[kind].sub("", raw))
    text = text.lstrip(" -").rstrip(" ")
    assert not text.startswith("-")
    return text


def clean_file(path: str | Path, kind: str = "keywords") -> str:
    return clean(Path(path).read_text(encoding="utf-8"), kind)
