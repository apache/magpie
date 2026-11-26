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
- `length_check` — whether a title is too long for the published record or the
  announcement subject, and the length a shorter one must fit.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from generate_cve_json.cve_json import configured_title_product_prefix

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


# The published record's hard limit on its title (the record schema's
# `maxLength: 256`), and the length above which the title, reused in the
# announcement mail subject, is worth shortening. Counted in characters
# (Unicode code points, Python `len`), never bytes; the record generator
# applies the same two limits.
TITLE_MAX_CHARS = 256
TITLE_WARN_CHARS = 100
# JavaScript's `\b` is ASCII only, hence re.ASCII, to read titles as Vulnogram does.
_APACHE_WORD = re.compile(r"\bApache\b", re.ASCII)


def posted_title(title: str, products: Sequence[str] = (), product_prefix: bool = False) -> str:
    """The title as the CVE tool posts it, which the registry validates.

    Without ``product_prefix`` that is the bare title. With it, the ASF
    Vulnogram rule: a title with the whole word ``Apache`` (case-sensitive,
    ASCII word boundaries) is posted as is; any other as ``<products>: <title>``,
    the distinct product names in first-seen order joined with ``", "``.
    """
    names = list(dict.fromkeys(p for p in products if p))
    if not product_prefix or not names or _APACHE_WORD.search(title):
        return title
    return f"{', '.join(names)}: {title}"


def title_product_prefix(data: Mapping[str, Any], report: Mapping[str, Any] | None = None) -> bool:
    """Whether the CVE tool prefixes the title: the caller's explicit value, else
    the record generator's report, else the configuration chain the generator
    resolves (its config's `[cna].title_product_prefix`, then project.md, then
    the organization manifest, then `False`), read from the working directory.
    """
    if data.get("title_product_prefix") is not None:
        return bool(data["title_product_prefix"])
    if report is not None and isinstance(report.get("title_product_prefix"), bool):
        return bool(report["title_product_prefix"])
    return configured_title_product_prefix()[0]


def length_check(
    title: str, products: Sequence[str] = (), product_prefix: bool = False
) -> dict[str, int | bool | None]:
    """The length verdict on a record title; proposing the shorter title stays the model's job.

    The schema limit applies to :func:`posted_title`.
    ``max_title_chars`` is the budget left after the product prefix, capped at
    :data:`TITLE_WARN_CHARS`; the prefix counts even when the title holds the
    word ``Apache``, since a shorter title must not rely on it. ``shorten`` is
    true exactly when the title is over that budget. ``products_too_long`` is
    true when the prefix alone leaves no room (``max_title_chars`` is then
    ``None``): a products problem, not a title one.
    """
    length = len(title)
    posted = len(posted_title(title, products, product_prefix))
    names = list(dict.fromkeys(p for p in products if p))
    prefix_chars = len(f"{', '.join(names)}: ") if product_prefix and names else 0
    room = TITLE_MAX_CHARS - prefix_chars
    budget = min(room, TITLE_WARN_CHARS) if room > 0 else None
    return {
        "title_chars": length,
        "posted_chars": posted,
        "prefix_chars": prefix_chars,
        "max_title_chars": budget,
        "products_too_long": budget is None,
        "over_limit": max(length, posted) > TITLE_MAX_CHARS,
        "shorten": budget is not None and length > budget,
    }
