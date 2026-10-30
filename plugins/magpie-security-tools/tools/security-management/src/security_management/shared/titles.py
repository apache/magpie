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
"""Title clean-ups the import skills share. Paraphrasing a title stays the model's job.

- `strip_mail_prefixes` — a mail subject without its `Re:` / `Fwd:` / `FW:` /
  `[SECURITY]` / `[Security Report]` prefixes (any order, any repetition).
- `strip_pr_title` — a PR title without its conventional-commit prefix and
  scope, `[skip ci]`-style markers and trailing `(#N)` / `[#N]`.
- `md_title` — a markdown finding's title with the `[ Security Report ] ` prefix.
"""

from __future__ import annotations

import re

_MAIL_PREFIX = re.compile(r"^\s*(?:(?:re|fwd?)\s*:|\[\s*security(?:\s+report)?\s*\])\s*", re.IGNORECASE)
_CONVENTIONAL = re.compile(
    r"^\s*(?:feat|fix|chore|docs|refactor|perf|test|tests|build|ci|style|revert|security|sec|deps)"
    r"(?:\([^)\n]*\))?!?\s*:\s*",
    re.IGNORECASE,
)
_SKIP_CI = re.compile(r"\[\s*(?:skip[ -]ci|ci[ -]skip|no[ -]ci|skip[ -]actions)\s*\]\s*", re.IGNORECASE)
_TRAILING_PR = re.compile(r"\s*(?:\(#\d+\)|\[#\d+\])\s*$")

MD_TITLE_PREFIX = "[ Security Report ] "


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_mail_prefixes(subject: str) -> str:
    text = subject
    while True:
        stripped = _MAIL_PREFIX.sub("", text, count=1)
        if stripped == text:
            return _tidy(text)
        text = stripped


def strip_pr_title(title: str) -> str:
    text = _SKIP_CI.sub(" ", title)
    while True:
        stripped = _TRAILING_PR.sub("", text)
        if stripped == text:
            break
        text = stripped
    return _tidy(_CONVENTIONAL.sub("", text, count=1))


def md_title(title: str) -> str:
    text = _tidy(title)
    if text.startswith(MD_TITLE_PREFIX.strip()):
        text = _tidy(text[len(MD_TITLE_PREFIX.strip()) :])
    return MD_TITLE_PREFIX + text
