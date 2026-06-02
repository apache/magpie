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
"""``privacy-llm-check`` — verify the active LLM stack is approved.

Exit codes:

- ``0`` — every entry in the *Currently configured LLM stack*
  section is approved per the rules in
  ``tools/privacy-llm/models.md``.
- ``1`` — at least one entry is unapproved (or the config file is
  missing values an opt-in entry needs); the stderr explanation
  names the offending entries.
- ``2`` — the config file could not be located or parsed.

Skills shell out to this command at Step 0 (pre-flight) when they
may read ``<private-list>`` content. The wiring contract is in
``tools/privacy-llm/wiring.md``.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

from checker.config import (
    LLMEntry,
    OptInEntry,
    ParsedConfig,
    host_of,
    locate_config_path,
    parse_config,
)

# Hosts that resolve to "local-only inference" — not over the wire.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Free-text matches for the always-approved Claude Code entry.
# Case-insensitive, matched as a substring of the bullet's raw
# text. Adopters may write "Claude Code (the agent ...)" or
# "Claude Code itself" or just "Claude Code" — all fine.
_CLAUDE_CODE_MATCH = "claude code"


@dataclasses.dataclass(frozen=True)
class Verdict:
    """The check result for one ``LLMEntry``."""

    entry: LLMEntry
    approved: bool
    reason: str


def _approve_by_default_rules(entry: LLMEntry) -> Verdict | None:
    """Return a verdict if the entry matches a default-approved rule;
    otherwise ``None`` (the caller falls back to the opt-in match)."""
    if _CLAUDE_CODE_MATCH in entry.raw.lower():
        return Verdict(entry, True, "Claude Code itself (default-approved)")
    if entry.url is not None:
        host = host_of(entry.url)
        if host is None:
            return Verdict(entry, False, f"unparsable URL host in {entry.url!r}")
        if host in _LOCAL_HOSTS:
            return Verdict(entry, True, f"local-only inference at {host} (default-approved)")
        if host.endswith(".apache.org") or host == "apache.org":
            return Verdict(entry, True, f"*.apache.org-hosted endpoint at {host} (default-approved)")
    return None


def _approve_by_opt_in(entry: LLMEntry, opt_in: list[OptInEntry]) -> Verdict:
    """Match ``entry`` against the adopter's opt-in registry.

    A match requires either:
    - the entry's URL appears in the opt-in entry's ``name`` (free-text), OR
    - the entry's first non-URL token sequence matches the opt-in entry's name
      (case-insensitive substring on either side).

    A *valid* match additionally requires the opt-in entry to carry
    a non-empty ``Data-residency contract`` and ``Approved-by`` line.
    """
    raw_lc = entry.raw.lower()
    url_lc = entry.url.lower() if entry.url else ""
    for opt in opt_in:
        name_lc = opt.name.lower()
        # Match if either the bullet's raw text contains the opt-in
        # name, or vice versa, or the URL is a substring of the
        # opt-in name (or vice versa).
        if not (
            name_lc in raw_lc
            or _shortname(name_lc) in raw_lc
            or (url_lc and (url_lc in name_lc or name_lc in url_lc))
        ):
            continue
        if not opt.data_residency:
            return Verdict(
                entry,
                False,
                f"opt-in entry {opt.name!r} matches but is missing the 'Data-residency contract' sub-bullet",
            )
        if not opt.approved_by or _is_placeholder(opt.approved_by):
            return Verdict(
                entry,
                False,
                f"opt-in entry {opt.name!r} matches but the 'Approved-by' "
                f"sub-bullet is missing or still has placeholder text "
                f"({opt.approved_by!r}); a real PMC member must sign off.",
            )
        return Verdict(entry, True, f"opt-in entry {opt.name!r} (data-residency + approved-by present)")
    return Verdict(
        entry,
        False,
        "no default-approval rule matches and no opt-in entry was declared "
        "for this LLM. Add an entry under 'Approved third-party endpoints "
        "(opt-in)' with a Data-residency contract line and an Approved-by "
        "sign-off, or remove this LLM from the active stack.",
    )


def _shortname(name_lc: str) -> str:
    """Heuristic: take the leading word(s) before the first ``—`` /
    ``-`` / ``,`` / ``(`` so that ``aws bedrock — eu-central-1``
    matches a stack bullet that just says ``aws bedrock``."""
    for sep in (" — ", " - ", ",", "(", ":"):
        if sep in name_lc:
            return name_lc.split(sep, 1)[0].strip()
    return name_lc


def _is_placeholder(text: str) -> bool:
    """Recognise the template's placeholder forms so we don't accept
    them as valid sign-off."""
    lc = text.lower().strip()
    if not lc:
        return True
    return any(
        marker in lc for marker in ("<pmc-member-initials>", "<initials>", "<yyyy-mm-dd>", "yyyy-mm-dd")
    )


def check_stack(config: ParsedConfig) -> list[Verdict]:
    """Run every default-approval rule, falling back to the opt-in
    registry. Returns one :class:`Verdict` per LLM stack entry."""
    out: list[Verdict] = []
    for entry in config.llm_stack:
        v = _approve_by_default_rules(entry)
        if v is None:
            v = _approve_by_opt_in(entry, config.opt_in)
        out.append(v)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="privacy-llm-check",
        description=(
            "Verify every entry in <project-config>/privacy-llm.md's "
            "'Currently configured LLM stack' is approved per "
            "tools/privacy-llm/models.md."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Path to the privacy-llm.md config. Default: "
            "$PRIVACY_LLM_CONFIG, then "
            "<cwd>/.apache-magpie/privacy-llm.md, then "
            "<cwd>/.apache-magpie-overrides/privacy-llm.md."
        ),
    )
    parser.add_argument(
        "--reads-private-list",
        action="store_true",
        help=(
            "Set this when the calling skill may read <private-list> "
            "content. The check itself is the same — the flag just "
            "tells the user via the printed banner why the gate is firing."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="On approval, print nothing. On rejection, print stderr only.",
    )
    args = parser.parse_args(argv)

    try:
        path = locate_config_path(args.config)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        cfg = parse_config(path)
    except OSError as e:
        print(f"{path}: {e}", file=sys.stderr)
        return 2

    verdicts = check_stack(cfg)
    if not verdicts:
        print(
            f"{path}: 'Currently configured LLM stack' is empty — at least "
            f"one entry (typically 'Claude Code') is required.",
            file=sys.stderr,
        )
        return 1

    bad = [v for v in verdicts if not v.approved]
    if not bad:
        if not args.quiet:
            banner = "privacy-llm-check: every active-stack entry is approved" + (
                " (skill reads <private-list>)" if args.reads_private_list else ""
            )
            print(banner)
            for v in verdicts:
                print(f"  ✓ {v.entry.raw}  —  {v.reason}")
        return 0

    print(
        f"privacy-llm-check: {len(bad)} of {len(verdicts)} "
        f"active-stack entr{'y is' if len(bad) == 1 else 'ies are'} not approved.",
        file=sys.stderr,
    )
    for v in verdicts:
        marker = "✓" if v.approved else "✗"
        print(f"  {marker} {v.entry.raw}  —  {v.reason}", file=sys.stderr)
    print(
        f"\nFix: edit {path} per tools/privacy-llm/models.md.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
