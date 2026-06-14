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

"""Pure rendering helpers for the security-tracker statistics dashboard.

All functions here are dependency-free (stdlib only) and have no side
effects, making them straightforwardly unit-testable without a cache
directory or live GitHub credentials.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
import statistics
from collections.abc import Iterator
from typing import Any

# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


def parse_dt(s: str | None) -> dt.datetime | None:
    """Parse an ISO-8601 timestamp string to an aware datetime, or None."""
    if not s:
        return None
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Bucket abstraction (monthly / quarterly)
# ---------------------------------------------------------------------------


def month_of(d: dt.datetime) -> tuple[int, int]:
    """Return (year, month) bucket key for a datetime."""
    return d.year, d.month


def quarter_of(d: dt.datetime) -> tuple[int, int]:
    """Return (year, quarter) bucket key for a datetime.  Quarter in 1..4."""
    return d.year, (d.month - 1) // 3 + 1


def month_label(y: int, m: int) -> str:
    """Format a monthly bucket key as "YYYY-MM"."""
    return f"{y}-{m:02d}"


def quarter_label(y: int, q: int) -> str:
    """Format a quarterly bucket key as "YYYY-Qn"."""
    return f"{y}-Q{q}"


def month_end(y: int, m: int) -> dt.datetime:
    """Return the last instant of the given calendar month (UTC)."""
    last_day = calendar.monthrange(y, m)[1]
    return dt.datetime(y, m, last_day, 23, 59, 59, tzinfo=dt.timezone.utc)


def quarter_end(y: int, q: int) -> dt.datetime:
    """Return the last instant of the given calendar quarter (UTC)."""
    last_month = q * 3
    last_day = calendar.monthrange(y, last_month)[1]
    return dt.datetime(y, last_month, last_day, 23, 59, 59, tzinfo=dt.timezone.utc)


def iter_months(y0: int, m0: int, y1: int, m1: int) -> Iterator[tuple[int, int]]:
    """Yield (year, month) tuples from (y0, m0) to (y1, m1) inclusive."""
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1


def iter_quarters(y0: int, q0: int, y1: int, q1: int) -> Iterator[tuple[int, int]]:
    """Yield (year, quarter) tuples from (y0, q0) to (y1, q1) inclusive."""
    y, q = y0, q0
    while (y, q) <= (y1, q1):
        yield y, q
        q += 1
        if q == 5:
            q = 1
            y += 1


# Weekly buckets key on ISO (year, week) — note the ISO year can differ from
# the calendar year in late December / early January, but (iso_year, iso_week)
# tuples remain chronologically ordered, so the existing <=-based iteration
# and bucketing carry over unchanged.
def week_of(d: dt.datetime) -> tuple[int, int]:
    iso = d.isocalendar()
    return iso[0], iso[1]


def week_label(y: int, w: int) -> str:
    return f"{y}-W{w:02d}"


def week_end(y: int, w: int) -> dt.datetime:
    # ISO weeks run Monday (day 1) .. Sunday (day 7); end at Sunday 23:59:59.
    sunday = dt.date.fromisocalendar(y, w, 7)
    return dt.datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=dt.timezone.utc)


def iter_weeks(y0: int, w0: int, y1: int, w1: int) -> Iterator[tuple[int, int]]:
    # Step by 7 days from the Monday of the start week through the end week;
    # ISO years have 52 or 53 weeks, so stepping by date avoids that edge.
    cur = dt.date.fromisocalendar(y0, w0, 1)
    last = dt.date.fromisocalendar(y1, w1, 1)
    while cur <= last:
        iso = cur.isocalendar()
        yield iso[0], iso[1]
        cur += dt.timedelta(days=7)


def milestone_x(milestone_date: str, buckets_mode: str = "monthly") -> str:
    """Map a milestone date string (YYYY-MM-DD) to a bucket-axis label."""
    y = int(milestone_date[:4])
    mo = int(milestone_date[5:7])
    if buckets_mode == "monthly":
        return f"{y}-{mo:02d}"
    if buckets_mode == "weekly":
        d = dt.date(y, mo, int(milestone_date[8:10]))
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return f"{y}-Q{(mo - 1) // 3 + 1}"


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def deep_merge(base: Any, overlay: Any) -> Any:
    """Deep-merge *overlay* into *base*.  Lists are REPLACED, not concatenated."""
    if overlay is None:
        return base
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _minimal_yaml_load(text: str) -> Any:
    """Tiny YAML subset parser sufficient for default-config.yaml.

    Supports: nested block mappings, block sequences (``- ...``), inline
    flow lists ``[a, b, "c d"]``, string scalars (with optional quotes),
    integers, floats, booleans, null.  Comments start at ``#`` outside
    quoted strings.  No anchors, no merge keys, no flow mappings.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        in_q = None
        out: list[str] = []
        i = 0
        while i < len(raw):
            ch = raw[i]
            if in_q:
                out.append(ch)
                if ch == "\\" and i + 1 < len(raw):
                    out.append(raw[i + 1])
                    i += 2
                    continue
                if ch == in_q:
                    in_q = None
                i += 1
                continue
            if ch in ('"', "'"):
                in_q = ch
                out.append(ch)
                i += 1
                continue
            if ch == "#":
                break
            out.append(ch)
            i += 1
        line = "".join(out).rstrip()
        if line.strip():
            lines.append(line)

    def indent_of(s: str) -> int:
        return len(s) - len(s.lstrip(" "))

    def scalar(s: str) -> Any:
        s = s.strip()
        if not s:
            return None
        if s.lower() in ("null", "~"):
            return None
        if s.lower() == "true":
            return True
        if s.lower() == "false":
            return False
        if s.startswith('"') and s.endswith('"') and len(s) >= 2:
            return s[1:-1].encode().decode("unicode_escape")
        if s.startswith("'") and s.endswith("'") and len(s) >= 2:
            return s[1:-1]
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            if not inner:
                return []
            return [scalar(x) for x in _split_flow_list(inner)]
        try:
            if "." in s or "e" in s or "E" in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    def _split_flow_list(inner: str) -> list[str]:
        parts: list[str] = []
        cur: list[str] = []
        in_q2 = None
        depth = 0
        for ch in inner:
            if in_q2:
                cur.append(ch)
                if ch == in_q2:
                    in_q2 = None
                continue
            if ch in ('"', "'"):
                in_q2 = ch
                cur.append(ch)
                continue
            if ch == "[":
                depth += 1
                cur.append(ch)
                continue
            if ch == "]":
                depth -= 1
                cur.append(ch)
                continue
            if ch == "," and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
                continue
            cur.append(ch)
        if cur:
            parts.append("".join(cur).strip())
        return parts

    def parse_block(idx: int, base_indent: int) -> tuple[Any, int]:
        if idx >= len(lines):
            return None, idx
        first = lines[idx]
        ind = indent_of(first)
        if ind < base_indent:
            return None, idx
        if first.lstrip().startswith("- "):
            return parse_seq(idx, ind)
        return parse_map(idx, ind)

    def _split_key_value(stripped: str) -> tuple[str, str, str]:
        in_q3 = None
        for i, ch in enumerate(stripped):
            if in_q3:
                if ch == in_q3:
                    in_q3 = None
                continue
            if ch in ('"', "'"):
                in_q3 = ch
                continue
            if ch == ":":
                key = stripped[:i].strip()
                rest = stripped[i + 1 :]
                if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                    key = key[1:-1]
                return key, ":", rest
        return stripped, "", ""

    def parse_map(idx: int, base_indent: int) -> tuple[dict, int]:
        out: dict[str, Any] = {}
        while idx < len(lines):
            line = lines[idx]
            ind = indent_of(line)
            if ind < base_indent:
                break
            if ind > base_indent:
                break
            stripped = line.strip()
            if stripped.startswith("- "):
                break
            if ":" not in stripped:
                idx += 1
                continue
            key, _, rest = _split_key_value(stripped)
            rest = rest.strip()
            idx += 1
            if rest == "" or rest is None:
                if idx < len(lines) and indent_of(lines[idx]) > base_indent:
                    child, idx = parse_block(idx, indent_of(lines[idx]))
                    out[key] = child
                else:
                    out[key] = None
            else:
                out[key] = scalar(rest)
        return out, idx

    def parse_seq(idx: int, base_indent: int) -> tuple[list, int]:
        out: list[Any] = []
        while idx < len(lines):
            line = lines[idx]
            ind = indent_of(line)
            if ind < base_indent:
                break
            if ind > base_indent:
                break
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            after_dash = stripped[2:].rstrip()
            item_inner_indent = base_indent + 2
            idx += 1
            if after_dash == "":
                if idx < len(lines) and indent_of(lines[idx]) > base_indent:
                    child, idx = parse_block(idx, indent_of(lines[idx]))
                    out.append(child)
                else:
                    out.append(None)
                continue
            if ":" in after_dash and not (after_dash.startswith('"') or after_dash.startswith("'")):
                key, _, rest = _split_key_value(after_dash)
                rest = rest.strip()
                item: dict[str, Any] = {}
                if rest == "":
                    if idx < len(lines) and indent_of(lines[idx]) > item_inner_indent:
                        child, idx = parse_block(idx, indent_of(lines[idx]))
                        item[key] = child
                    else:
                        item[key] = None
                else:
                    item[key] = scalar(rest)
                while idx < len(lines):
                    nline = lines[idx]
                    nind = indent_of(nline)
                    if nind < item_inner_indent:
                        break
                    if nind > item_inner_indent:
                        break
                    nstripped = nline.strip()
                    if nstripped.startswith("- "):
                        break
                    if ":" not in nstripped:
                        idx += 1
                        continue
                    nkey, _, nrest = _split_key_value(nstripped)
                    nrest = nrest.strip()
                    idx += 1
                    if nrest == "":
                        if idx < len(lines) and indent_of(lines[idx]) > item_inner_indent:
                            child, idx = parse_block(idx, indent_of(lines[idx]))
                            item[nkey] = child
                        else:
                            item[nkey] = None
                    else:
                        item[nkey] = scalar(nrest)
                out.append(item)
            else:
                out.append(scalar(after_dash))
        return out, idx

    val, _ = parse_block(0, 0)
    return val


# ---------------------------------------------------------------------------
# Category predicate evaluator
# ---------------------------------------------------------------------------


def eval_predicate(pred: Any, ctx: dict[str, Any]) -> bool:
    """Evaluate a category predicate against a snapshot context dict.

    Expected *ctx* keys:
      - ``labels``               : set of label strings present at snapshot time
      - ``is_open``              : bool — tracker is open at snapshot time
      - ``state_reason``         : str | None — GitHub stateReason
      - ``pr_merged_by_snapshot``: bool — a linked upstream PR is merged by snapshot
      - ``scope_labels``         : set of label strings that are scope labels
                                   (optional; defaults to empty set)

    Returns True when the predicate matches the context.
    """
    if not isinstance(pred, dict):
        return False
    scope_labels: set[str] = ctx.get("scope_labels") or set()  # type: ignore[assignment]
    for key, val in pred.items():
        if key == "any_of":
            if not any(eval_predicate(p, ctx) for p in val):
                return False
        elif key == "all_of":
            if isinstance(val, list):
                if not all(eval_predicate(p, ctx) for p in val):
                    return False
            elif isinstance(val, dict):
                if not eval_predicate(val, ctx):
                    return False
            else:
                return False
        elif key == "state":
            want_open = val == "open"
            if ctx["is_open"] != want_open:
                return False
        elif key == "state_reason":
            if ctx["state_reason"] != val:
                return False
        elif key == "any_label":
            if not any(lb in ctx["labels"] for lb in val):
                return False
        elif key == "all_labels":
            if not all(lb in ctx["labels"] for lb in val):
                return False
        elif key == "not_label":
            if val in ctx["labels"]:
                return False
        elif key == "not_any_label":
            if any(lb in ctx["labels"] for lb in val):
                return False
        elif key == "no_scope_label":
            has_scope = bool(ctx["labels"] & scope_labels)
            if val and has_scope:
                return False
            if not val and not has_scope:
                return False
        elif key == "has_scope_label":
            has_scope = bool(ctx["labels"] & scope_labels)
            if val and not has_scope:
                return False
            if not val and has_scope:
                return False
        elif key == "pr_merged_by_snapshot":
            if val and not ctx["pr_merged_by_snapshot"]:
                return False
            if not val and ctx["pr_merged_by_snapshot"]:
                return False
        else:
            return False
    return True


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def mean_or_none(xs: list[float]) -> float | None:
    """Return the mean of *xs* rounded to 2 decimal places, or None if empty."""
    return round(statistics.mean(xs), 2) if xs else None


# ---------------------------------------------------------------------------
# HTML / JS serialisation helpers
# ---------------------------------------------------------------------------


def js_array(xs: list[Any], fmt_null: str = "null") -> str:
    """Serialise a Python list to a JavaScript array literal string."""
    parts = []
    for x in xs:
        if x is None:
            parts.append(fmt_null)
        elif isinstance(x, float):
            parts.append(f"{x:.2f}" if x != int(x) else f"{int(x)}")
        else:
            parts.append(str(x))
    return "[" + ", ".join(parts) + "]"


def js_quotes(xs: list[str]) -> str:
    """Serialise a list of strings to a JavaScript array of quoted string literals."""
    return "[" + ", ".join(f'"{x}"' for x in xs) + "]"


# ---------------------------------------------------------------------------
# Triage helpers
# ---------------------------------------------------------------------------


def build_triage_regex(keywords: list[str]) -> re.Pattern[str] | None:
    """Compile a triage keyword list into a single OR-pattern regex."""
    if not keywords:
        return None
    parts = []
    for kw in keywords:
        if (kw.isupper() and " " not in kw and "-" not in kw) or (
            kw.isalpha() and kw.islower() and " " not in kw
        ):
            parts.append(rf"\b{re.escape(kw)}\b")
        else:
            parts.append(re.escape(kw))
    return re.compile("|".join(parts), re.IGNORECASE)


def is_bot_body(body: str | None, bot_prefixes: tuple[str, ...] = ()) -> bool:
    """Return True when *body* begins with one of the known bot comment prefixes."""
    if not body:
        return False
    b = body.lstrip()
    return any(b.startswith(p) for p in bot_prefixes)
