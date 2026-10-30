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
or ``AMBIGUOUS``). Reply bodies never reach this module.

Moved from ``vote-tally/scripts/tally.py``, adding the ``pr-approval`` rule
(``--min-approvals``); it now runs as ``release-management vote-tally tally``.

Binding resolution against the roster (a markdown table with ``Apache ID``
and ``Primary email`` columns):

1. exact, case-insensitive match of ``from`` against ``Primary email``;
2. when ``from`` ends in ``@apache.org``, its local part against ``Apache ID``;
3. otherwise non-binding.

``from`` is parsed as an address header, so only its real mailbox counts — an
address written into the display name does not, and a ``from`` holding several
addresses or none that parses is non-binding.

Fractional votes are always non-binding. Ambiguous votes are never counted;
without ``--force-close`` they halt the tally (``result`` is null).

Pass rule (``dev-list-vote``): ``binding_plus1 >= 3`` and
``binding_plus1 > binding_minus1``. ``--overrides`` may only strengthen it;
a weakening or unknown key is rejected and reported, never applied.

``pr-approval`` with ``--min-approvals N`` (``approval_pr_min_approvals``):
``binding_plus1 >= N``, a binding approval being a roster member's.
:func:`pr_review_votes` turns the PR's gh ``reviews`` JSON into those votes:
each reviewer's latest review decides (``APPROVED`` +1, ``CHANGES_REQUESTED``
-1, ``DISMISSED`` no vote). A -1 is reported in ``binding_minus1`` but the
rule counts approvals only, so its effect is that the reviewer's +1 is gone. The
``github-discussion`` and ``maintainer-roster`` rules are not specified, so
their ``result`` stays null and the agent applies the configured rule.
"""

from __future__ import annotations

import re
from email.utils import getaddresses
from typing import Any

BASELINE_MIN_BINDING_PLUS1 = 3
BASELINE_RULE = "ASF baseline: binding_plus1 >= 3 AND binding_plus1 > binding_minus1"
FRACTIONAL_RE = re.compile(r"^[+-]?0?\.\d+$")
# Every override error that is an attempt to weaken the rule ends with this marker.
WEAKENING = "(configuration error)"


class InputError(Exception):
    pass


def is_weakening(error: str) -> bool:
    """Whether an ``override_errors`` entry is an attempt to weaken the pass rule (Golden rule 5)."""
    return error.endswith(WEAKENING)


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


def _parse_sender(sender: str) -> str | None:
    """The one mailbox address in ``sender``, lower-cased, or None when it is ambiguous.

    A bare address or handle is taken as written. Anything with angle brackets is
    parsed as an address header, so a display name that itself looks like an
    address (``"<alice@apache.org>" <mallory@example.org>``) yields the real
    mailbox, not the first bracketed string. Several addresses, or a header the
    parser rejects, give None — such a vote is never binding.
    """
    text = sender.strip()
    if "<" not in text and ">" not in text:
        return text.lower()
    addresses = [address for _, address in getaddresses([text]) if address]
    if len(addresses) != 1 or "@" not in addresses[0]:
        return None
    return addresses[0].strip().lower()


def normalise_address(sender: str) -> str:
    address = _parse_sender(sender)
    if address is None:
        # Keep unparsable senders distinct from each other and from any real
        # address, so one can never supersede another voter's vote.
        return "unparsed:" + sender.strip().lower()
    return address


def resolve_binding(sender: str, roster: list[dict[str, str]]) -> str | None:
    """Return how the voter resolved as binding, or None when non-binding."""
    address = _parse_sender(sender)
    if address is None:
        return None
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
    """The person behind a vote: their roster Apache ID when present, else the address.

    The two are namespaced, so a non-roster sender written as a bare ``alice`` can
    never collide with the roster member whose Apache ID is ``alice``.
    """
    address = normalise_address(sender)
    if via is not None:
        for row in roster:
            if row["apache_id"] and address in (
                row["primary_email"].lower(),
                f"{row['apache_id'].lower()}@apache.org",
            ):
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
                    f"{BASELINE_MIN_BINDING_PLUS1}; ignored {WEAKENING}"
                )
            else:
                rule["min_binding_plus1"] = value
        elif key == "binding_plus1_must_exceed_minus1":
            if value is not True:
                errors.append(f"binding_plus1_must_exceed_minus1 cannot be disabled; ignored {WEAKENING}")
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


REVIEW_VALUES = {"APPROVED": "+1", "CHANGES_REQUESTED": "-1"}
# States that are not a decision: a comment, or a review not yet submitted.
REVIEW_IGNORED = frozenset({"COMMENTED", "PENDING"})


def pr_review_votes(
    reviews: Any, login_map: dict[str, str] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn the gh ``reviews`` JSON of the release PR into votes, one per reviewer.

    ``reviews`` is what ``gh pr list --json number,reviews`` printed (a list of
    PRs, the first one used), one PR object, or a bare list of reviews. Each
    reviewer's latest decision (by ``submittedAt``; ``COMMENTED`` and ``PENDING``
    are not decisions) is their vote: ``APPROVED`` is ``+1``, ``CHANGES_REQUESTED``
    is ``-1``, and ``DISMISSED`` withdraws the reviewer's vote, so they cast none.
    An approval followed by a change request therefore counts as ``-1``, never
    ``+1``. ``login_map`` maps a GitHub login (case-insensitive) to the roster
    ``Primary email``; an unmapped login is passed on as-is and stays non-binding.

    Returns ``(votes, reviewers)``: the votes for :func:`tally`, in the order the
    deciding reviews were submitted, and one entry per reviewer saying what
    decided their vote.
    """
    if isinstance(reviews, list) and reviews and isinstance(reviews[0], dict) and "reviews" in reviews[0]:
        reviews = reviews[0]
    if isinstance(reviews, dict):
        reviews = reviews.get("reviews")
    if reviews == []:
        return [], []
    if not isinstance(reviews, list):
        raise InputError(
            "--pr-reviews must hold gh's `reviews` JSON (a PR list, a PR object or a review list)"
        )
    mapping = {str(k).strip().lower(): str(v).strip() for k, v in (login_map or {}).items()}
    latest: dict[str, tuple[str, int, dict[str, Any]]] = {}
    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            raise InputError(f"review #{index} is not an object")
        state = str(review.get("state") or "").upper()
        submitted = review.get("submittedAt")
        login = str((review.get("author") or {}).get("login") or "").strip()
        if not login:
            raise InputError(f"review #{index} has no author.login")
        if state in REVIEW_IGNORED or not submitted:
            continue
        if state not in REVIEW_VALUES and state != "DISMISSED":
            raise InputError(f"review #{index} has unrecognised state {state!r}")
        key = login.lower()
        candidate = (str(submitted), index, review)
        if key not in latest or candidate[:2] >= latest[key][:2]:
            latest[key] = candidate
    votes: list[dict[str, Any]] = []
    reviewers: list[dict[str, Any]] = []
    for key, (submitted, _, review) in sorted(latest.items(), key=lambda item: item[1][:2]):
        state = str(review["state"]).upper()
        login = str(review["author"]["login"]).strip()
        value = REVIEW_VALUES.get(state)
        sender = mapping.get(key, login)
        reviewers.append(
            {"login": login, "from": sender, "mapped": key in mapping, "latest_state": state, "value": value}
        )
        if value is not None:
            votes.append({"from": sender, "date": submitted, "value": value})
    return votes, reviewers


def tally(
    votes: list[dict[str, Any]],
    roster: list[dict[str, str]],
    overrides: dict[str, Any],
    force_close: bool,
    mechanism: str,
    min_approvals: int | None = None,
) -> dict[str, Any]:
    if min_approvals is not None and (
        not isinstance(min_approvals, int) or isinstance(min_approvals, bool) or min_approvals < 1
    ):
        raise InputError(
            f"--min-approvals {min_approvals!r} must be a positive integer (approval_pr_min_approvals)"
        )
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
    elif mechanism == "pr-approval" and min_approvals is not None:
        rule_text = f"pr-approval: binding approvals >= {min_approvals} (approval_pr_min_approvals)"
        if not halted:
            result = "PASSED" if counts["binding_plus1"] >= min_approvals else "FAILED"
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
