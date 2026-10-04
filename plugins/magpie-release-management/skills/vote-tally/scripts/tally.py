#!/usr/bin/env python3
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
"""Resolve binding status and evaluate the release-vote pass rule.

Input is a JSON list of votes the model has *already* classified — one
object per reply with ``from`` (address or handle), optional ``date``, and
``value`` (``+1``, ``0``, ``-1``, a fractional ``+0.x`` or ``fractional``,
or ``AMBIGUOUS``). Reply bodies never reach this script.

Binding resolution against the roster (a markdown table with ``Apache ID``
and ``Primary email`` columns):

1. exact, case-insensitive match of ``from`` against ``Primary email``;
2. when ``from`` ends in ``@apache.org``, its local part against ``Apache ID``;
3. otherwise non-binding.

Fractional votes are always non-binding. Ambiguous votes are never counted;
without ``--force-close`` they halt the tally (``result`` is null).

Pass rule (``dev-list-vote``): ``binding_plus1 >= 3`` and
``binding_plus1 > binding_minus1``. ``--overrides`` may only strengthen it;
a weakening or unknown key is rejected and reported, never applied.

Prints one JSON object on stdout. Exit 0 on success, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BASELINE_MIN_BINDING_PLUS1 = 3
BASELINE_RULE = "ASF baseline: binding_plus1 >= 3 AND binding_plus1 > binding_minus1"
FRACTIONAL_RE = re.compile(r"^[+-]?0?\.\d+$")
EMAIL_RE = re.compile(r"<([^<>\s]+@[^<>\s]+)>")


class InputError(Exception):
    pass


def _cells(line: str) -> list[str]:
    parts = [c.strip().strip("`").strip() for c in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def parse_roster(text: str) -> list[dict[str, str]]:
    """Return roster rows as {apache_id, primary_email} dicts (lower-cased)."""
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = _cells(line)
        lowered = [c.lower() for c in cells]
        if "apache id" in lowered and "primary email" in lowered:
            header = lowered
            continue
        if header is None or all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        row = dict(zip(header, cells, strict=False))  # short rows leave trailing columns unset
        apache_id = row.get("apache id", "").lower()
        email = row.get("primary email", "").lower()
        if apache_id or email:
            rows.append({"apache_id": apache_id, "primary_email": email})
    return rows


def normalise_address(sender: str) -> str:
    match = EMAIL_RE.search(sender)
    return (match.group(1) if match else sender).strip().lower()


def resolve_binding(sender: str, roster: list[dict[str, str]]) -> str | None:
    """Return how the voter resolved as binding, or None when non-binding."""
    address = normalise_address(sender)
    for row in roster:
        if row["primary_email"] and address == row["primary_email"]:
            return "primary_email"
    if address.endswith("@apache.org"):
        local = address.rsplit("@", 1)[0]
        for row in roster:
            if row["apache_id"] and local == row["apache_id"]:
                return "apache_id"
    return None


def _identity(sender: str, roster: list[dict[str, str]], via: str | None) -> str:
    """The person behind a vote: their roster Apache ID when on the roster, else the address.

    The two are namespaced, so a non-roster sender written as a bare ``alice`` can
    never collide with the roster member whose Apache ID is ``alice``.
    """
    address = normalise_address(sender)
    if via is not None:
        for row in roster:
            if address in (row["primary_email"].lower(), f"{row['apache_id'].lower()}@apache.org"):
                return "roster:" + row["apache_id"].lower()
    return "address:" + address


def _superseded(old: dict[str, Any], by: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity": old["identity"],
        "from": old["from"],
        "date": old["date"],
        "value": old["value"],
        "superseded_by": {"from": by["from"], "date": by["date"], "value": by["value"]},
    }


def normalise_value(value: Any) -> str:
    text = str(value).strip()
    upper = text.upper()
    if upper == "AMBIGUOUS":
        return "AMBIGUOUS"
    if upper == "FRACTIONAL" or FRACTIONAL_RE.match(text):
        return "fractional"
    if text in {"+1", "1"}:
        return "+1"
    if text in {"0", "+0", "-0"}:
        return "0"
    if text == "-1":
        return "-1"
    raise InputError(f"unrecognised vote value {value!r}")


def apply_overrides(overrides: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return the effective rule and the list of rejected overrides."""
    rule: dict[str, Any] = {
        "min_binding_plus1": BASELINE_MIN_BINDING_PLUS1,
        "binding_plus1_must_exceed_minus1": True,
        "max_binding_minus1": None,
    }
    errors: list[str] = []
    for key, value in overrides.items():
        if key == "min_binding_plus1":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"min_binding_plus1={value!r} is not an integer; ignored")
            elif value < BASELINE_MIN_BINDING_PLUS1:
                errors.append(
                    f"min_binding_plus1={value} weakens the ASF baseline of "
                    f"{BASELINE_MIN_BINDING_PLUS1}; ignored (configuration error)"
                )
            else:
                rule["min_binding_plus1"] = value
        elif key == "binding_plus1_must_exceed_minus1":
            if value is not True:
                errors.append(
                    "binding_plus1_must_exceed_minus1 cannot be disabled; ignored (configuration error)"
                )
        elif key == "max_binding_minus1":
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"max_binding_minus1={value!r} is not a non-negative integer; ignored")
            else:
                rule["max_binding_minus1"] = value
        else:
            errors.append(f"unknown override {key!r}; not applied")
    return rule, errors


def describe_rule(rule: dict[str, Any]) -> str:
    if rule["min_binding_plus1"] == BASELINE_MIN_BINDING_PLUS1 and rule["max_binding_minus1"] is None:
        return BASELINE_RULE
    text = (
        f"strengthened ASF baseline: binding_plus1 >= {rule['min_binding_plus1']} "
        "AND binding_plus1 > binding_minus1"
    )
    if rule["max_binding_minus1"] is not None:
        text += f" AND binding_minus1 <= {rule['max_binding_minus1']}"
    return text


def tally(
    votes: list[dict[str, Any]],
    roster: list[dict[str, str]],
    overrides: dict[str, Any],
    force_close: bool,
    mechanism: str,
) -> dict[str, Any]:
    voters: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    counts = {
        "binding_plus1": 0,
        "binding_minus1": 0,
        "binding_zero": 0,
        "nonbinding_plus1": 0,
        "nonbinding_minus1": 0,
        "nonbinding_zero": 0,
        "fractional_count": 0,
        "excluded_ambiguous_count": 0,
    }
    # One person, one vote: when someone votes more than once (a changed vote, or a
    # member writing from two addresses), only their latest vote counts. "Latest" is
    # thread order, the order the list archive received the votes, which is the order
    # they must be passed in. A sender sets their own Date header, so the date never
    # decides; a vote whose date runs backwards against thread order is flagged in
    # `date_order_mismatches` for the RM. Earlier votes are listed in
    # `superseded_votes` and never counted.
    latest: dict[str, tuple[int, dict[str, Any]]] = {}
    superseded: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for index, vote in enumerate(votes):
        if not isinstance(vote, dict) or "from" not in vote or "value" not in vote:
            raise InputError(f"vote #{index} needs 'from' and 'value'")
        value = normalise_value(vote["value"])
        via = resolve_binding(str(vote["from"]), roster)
        identity = _identity(str(vote["from"]), roster, via)
        candidate = {
            "from": vote["from"],
            "date": vote.get("date"),
            "value": value,
            "via": via,
            "identity": identity,
        }
        previous = latest.get(identity)
        if previous is not None:
            superseded.append(_superseded(previous[1], candidate))
            before, after = previous[1]["date"], candidate["date"]
            if before and after and str(after) < str(before):
                mismatches.append(
                    {
                        "identity": identity,
                        "earlier_in_thread": previous[1]["from"],
                        "earlier_date": before,
                        "later_in_thread": candidate["from"],
                        "later_date": after,
                    }
                )
        latest[identity] = (index, candidate)

    for _, counted in sorted(latest.values(), key=lambda item: item[0]):
        entry = {"from": counted["from"], "date": counted["date"]}
        value, via = counted["value"], counted["via"]
        if value == "AMBIGUOUS":
            ambiguous.append(entry)
            counts["excluded_ambiguous_count"] += 1
            continue
        binding = via is not None and value != "fractional"
        voters.append(
            {
                **entry,
                "value": value,
                "binding": binding,
                "matched_by": via if binding else None,
                "on_roster": via is not None,
            }
        )
        if value == "fractional":
            counts["fractional_count"] += 1
            continue
        suffix = {"+1": "plus1", "-1": "minus1", "0": "zero"}[value]
        counts[("binding_" if binding else "nonbinding_") + suffix] += 1

    rule, override_errors = apply_overrides(overrides)
    halted = bool(ambiguous) and not force_close
    result: str | None = None
    rule_text: str | None = None
    if mechanism == "dev-list-vote":
        rule_text = describe_rule(rule)
        if not halted:
            passed = (
                counts["binding_plus1"] >= rule["min_binding_plus1"]
                and counts["binding_plus1"] > counts["binding_minus1"]
                and (
                    rule["max_binding_minus1"] is None
                    or counts["binding_minus1"] <= rule["max_binding_minus1"]
                )
            )
            result = "PASSED" if passed else "FAILED"
    return {
        "mechanism": mechanism,
        "voters": voters,
        "ambiguous": ambiguous,
        "halted_on_ambiguous": halted,
        "superseded_votes": superseded,
        "date_order_mismatches": mismatches,
        "force_close": force_close,
        **counts,
        "pass_rule_applied": rule_text,
        "override_errors": override_errors,
        "result": result,
        "proposed_label": {"PASSED": "vote-passed", "FAILED": "rc-rolled"}.get(result or ""),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--votes", required=True, help="JSON file: list of classified votes")
    parser.add_argument("--roster", required=True, help="approver roster markdown file")
    parser.add_argument(
        "--overrides",
        default="{}",
        help="JSON object of pass-rule overrides (min_binding_plus1, max_binding_minus1)",
    )
    parser.add_argument("--force-close", action="store_true")
    parser.add_argument("--mechanism", default="dev-list-vote")
    args = parser.parse_args(argv)
    try:
        votes = json.loads(Path(args.votes).read_text(encoding="utf-8"))
        if not isinstance(votes, list):
            raise InputError("--votes must hold a JSON list")
        overrides = json.loads(args.overrides)
        if not isinstance(overrides, dict):
            raise InputError("--overrides must be a JSON object")
        roster = parse_roster(Path(args.roster).read_text(encoding="utf-8"))
        if not roster:
            raise InputError("roster has no rows with an Apache ID / Primary email header")
        out = tally(votes, roster, overrides, args.force_close, args.mechanism)
    except (InputError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
