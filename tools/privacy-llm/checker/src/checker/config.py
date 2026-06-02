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
"""Parse ``<project-config>/privacy-llm.md`` into structured records.

The parser is deliberately permissive about whitespace and comment
placement — adopters customise the file by hand and the framework
should not reject minor formatting variations. It IS strict about
the structural anchors (`## Currently configured LLM stack`,
`## Approved third-party endpoints (opt-in)`) — those are the
contract surfaces the gate-check relies on, and a typo there is
worth surfacing.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import re
import urllib.parse

# Section-heading anchors the parser keys off. Matching is
# case-insensitive on the heading text but the leading `## ` is
# required.
_HEADING_LLM_STACK = "currently configured llm stack"
_HEADING_OPT_IN = "approved third-party endpoints (opt-in)"

# Default lookup path when no `--config` / env var is supplied.
DEFAULT_CONFIG_FILENAME = "privacy-llm.md"
ENV_CONFIG_PATH = "PRIVACY_LLM_CONFIG"

# The standard adopter location: <repo-root>/<project-config>/
# privacy-llm.md. The framework's <project-config> placeholder
# resolves at adoption time to either `.apache-magpie/` (the
# committed adopter-config dir under the tracker) or
# `.apache-magpie-overrides/` (the override dir). The checker
# tries both, in that order.
DEFAULT_CONFIG_DIRS = (".apache-magpie", ".apache-magpie-overrides")


@dataclasses.dataclass(frozen=True)
class LLMEntry:
    """One row from the *Currently configured LLM stack* section.

    ``raw`` is the verbatim bullet text (post-`- ` strip) for use in
    error messages. ``url`` is the parsed URL when present (matched
    against the *first* http(s) URL in the bullet); for entries that
    only name a provider without a URL (e.g. ``Claude Code``) it is
    ``None``.
    """

    raw: str
    url: str | None


@dataclasses.dataclass(frozen=True)
class OptInEntry:
    """One opt-in third-party endpoint declaration.

    ``name`` is the top-level bullet text. ``data_residency`` and
    ``approved_by`` are the values from the matching sub-bullets if
    present; ``None`` if absent. The gate-check considers the entry
    valid only when both sub-bullets carry non-placeholder values.
    """

    name: str
    data_residency: str | None
    approved_by: str | None


@dataclasses.dataclass(frozen=True)
class ParsedConfig:
    """The parser's output."""

    path: pathlib.Path
    llm_stack: list[LLMEntry]
    opt_in: list[OptInEntry]


def locate_config_path(explicit: str | None = None) -> pathlib.Path:
    """Resolve the config path: ``--config`` → env → default lookup.

    Default lookup walks the standard adopter locations relative to
    the current working directory. Returns the first existing file;
    raises :class:`FileNotFoundError` if none exists, with the list
    of paths tried.
    """
    if explicit:
        return pathlib.Path(explicit).expanduser()
    if env_path := os.environ.get(ENV_CONFIG_PATH):
        return pathlib.Path(env_path).expanduser()
    cwd = pathlib.Path.cwd()
    candidates = [cwd / d / DEFAULT_CONFIG_FILENAME for d in DEFAULT_CONFIG_DIRS]
    for c in candidates:
        if c.is_file():
            return c
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"No privacy-llm config found. Tried: {tried}. Set ${ENV_CONFIG_PATH} or pass --config <path>."
    )


def _strip_html_comments(text: str) -> str:
    """Drop HTML-comment blocks. Adopters often leave the template's
    instructional comments in place; the parser should treat the
    bullet structure as ground truth."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _section(lines: list[str], heading_lc: str) -> list[str]:
    """Return the lines under the named ``## <heading>`` until the
    next ``## `` heading (or end of file). Returns ``[]`` if the
    section is not present."""
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip().lower()
            if current == heading_lc:
                in_section = True
                continue
            if in_section:
                # Hit the next H2 — stop.
                break
        if in_section:
            out.append(line)
    return out


def _parse_llm_stack(section_lines: list[str]) -> list[LLMEntry]:
    """Each bullet in the section becomes one ``LLMEntry``."""
    entries: list[LLMEntry] = []
    for raw_line in section_lines:
        line = raw_line.rstrip()
        m = re.match(r"\s*-\s+(.+)$", line)
        if not m:
            continue
        text = m.group(1).strip()
        if not text or text.startswith("#"):
            continue
        # Skip the literal placeholder/example bullet from the template.
        if text.startswith("(none") or text.startswith("(default"):
            continue
        url = _first_url(text)
        entries.append(LLMEntry(raw=text, url=url))
    return entries


def _parse_opt_in(section_lines: list[str]) -> list[OptInEntry]:
    """Top-level ``- <name>`` bullets become entries; their indented
    sub-bullets supply *Data-residency contract* and *Approved-by*."""
    entries: list[OptInEntry] = []
    current_name: str | None = None
    data_residency: str | None = None
    approved_by: str | None = None

    def flush() -> None:
        nonlocal current_name, data_residency, approved_by
        if current_name is not None:
            entries.append(
                OptInEntry(
                    name=current_name,
                    data_residency=data_residency,
                    approved_by=approved_by,
                )
            )
        current_name = None
        data_residency = None
        approved_by = None

    for raw_line in section_lines:
        line = raw_line.rstrip()
        # Top-level bullet: zero or one leading space, then `- `.
        m_top = re.match(r"^-\s+(.+)$", line)
        if m_top:
            flush()
            text = m_top.group(1).strip()
            if text.startswith("(none") or text.startswith("(default"):
                continue
            current_name = text
            continue
        # Sub-bullet: 2+ spaces then `- `.
        m_sub = re.match(r"^\s{2,}-\s+(.+)$", line)
        if m_sub and current_name is not None:
            sub_text = m_sub.group(1).strip()
            lc = sub_text.lower()
            if lc.startswith("data-residency contract"):
                data_residency = sub_text.split(":", 1)[1].strip() if ":" in sub_text else ""
            elif lc.startswith("approved-by"):
                approved_by = sub_text.split(":", 1)[1].strip() if ":" in sub_text else ""
    flush()
    return entries


def _first_url(text: str) -> str | None:
    """Return the first http(s) URL in ``text``, or ``None``.

    The regex is intentionally simple — adopter configs name URLs
    in clear unambiguous form. We do not try to extract URLs from
    inside markdown link syntax; if the adopter writes
    ``[label](URL)`` we still match the bare URL.
    """
    m = re.search(r"https?://[^\s)>]+", text)
    if m is None:
        return None
    return m.group(0).rstrip(".,;:")


def parse_config(path: pathlib.Path) -> ParsedConfig:
    """Parse the file at ``path`` into a :class:`ParsedConfig`."""
    raw = path.read_text(encoding="utf-8")
    raw = _strip_html_comments(raw)
    lines = raw.splitlines()
    llm_stack_section = _section(lines, _HEADING_LLM_STACK)
    opt_in_section = _section(lines, _HEADING_OPT_IN)
    return ParsedConfig(
        path=path,
        llm_stack=_parse_llm_stack(llm_stack_section),
        opt_in=_parse_opt_in(opt_in_section),
    )


def host_of(url: str) -> str | None:
    """Lowercase host of ``url``, or ``None`` if unparsable."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None
    if not parsed.hostname:
        return None
    return parsed.hostname.lower()
