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

import datetime as dt

import pytest

from security_tracker_stats_dashboard.core import (
    _minimal_yaml_load,
    build_triage_regex,
    deep_merge,
    eval_predicate,
    is_bot_body,
    iter_months,
    iter_quarters,
    iter_weeks,
    js_array,
    js_quotes,
    mean_or_none,
    milestone_x,
    month_end,
    month_label,
    month_of,
    parse_dt,
    quarter_end,
    quarter_label,
    quarter_of,
    week_end,
    week_label,
    week_of,
)

# ---------------------------------------------------------------------------
# parse_dt
# ---------------------------------------------------------------------------


class TestParseDt:
    def test_none_returns_none(self):
        assert parse_dt(None) is None

    def test_empty_returns_none(self):
        assert parse_dt("") is None

    def test_z_suffix(self):
        result = parse_dt("2024-03-15T10:30:00Z")
        assert result == dt.datetime(2024, 3, 15, 10, 30, 0, tzinfo=dt.timezone.utc)

    def test_plus_offset(self):
        result = parse_dt("2024-03-15T10:30:00+00:00")
        assert result == dt.datetime(2024, 3, 15, 10, 30, 0, tzinfo=dt.timezone.utc)

    def test_aware(self):
        result = parse_dt("2025-01-01T00:00:00Z")
        assert result is not None
        assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# Bucket categorisation — monthly
# ---------------------------------------------------------------------------


class TestMonthOf:
    def test_basic(self):
        d = dt.datetime(2024, 6, 15, tzinfo=dt.timezone.utc)
        assert month_of(d) == (2024, 6)

    def test_january(self):
        d = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
        assert month_of(d) == (2025, 1)

    def test_december(self):
        d = dt.datetime(2024, 12, 31, tzinfo=dt.timezone.utc)
        assert month_of(d) == (2024, 12)


class TestQuarterOf:
    def test_q1(self):
        d = dt.datetime(2024, 2, 15, tzinfo=dt.timezone.utc)
        assert quarter_of(d) == (2024, 1)

    def test_q2(self):
        d = dt.datetime(2024, 4, 1, tzinfo=dt.timezone.utc)
        assert quarter_of(d) == (2024, 2)

    def test_q3(self):
        d = dt.datetime(2024, 9, 30, tzinfo=dt.timezone.utc)
        assert quarter_of(d) == (2024, 3)

    def test_q4(self):
        d = dt.datetime(2024, 12, 1, tzinfo=dt.timezone.utc)
        assert quarter_of(d) == (2024, 4)

    def test_boundary_month_3_is_q1(self):
        d = dt.datetime(2024, 3, 31, tzinfo=dt.timezone.utc)
        assert quarter_of(d) == (2024, 1)

    def test_boundary_month_4_is_q2(self):
        d = dt.datetime(2024, 4, 1, tzinfo=dt.timezone.utc)
        assert quarter_of(d) == (2024, 2)


class TestMonthLabel:
    def test_basic(self):
        assert month_label(2024, 3) == "2024-03"

    def test_two_digit_month(self):
        assert month_label(2024, 11) == "2024-11"

    def test_january_zero_padded(self):
        assert month_label(2025, 1) == "2025-01"


class TestQuarterLabel:
    def test_q1(self):
        assert quarter_label(2024, 1) == "2024-Q1"

    def test_q4(self):
        assert quarter_label(2023, 4) == "2023-Q4"


class TestMonthEnd:
    def test_january(self):
        result = month_end(2024, 1)
        assert result.day == 31
        assert result.hour == 23
        assert result.minute == 59
        assert result.tzinfo == dt.timezone.utc

    def test_february_leap(self):
        result = month_end(2024, 2)
        assert result.day == 29

    def test_february_nonleap(self):
        result = month_end(2023, 2)
        assert result.day == 28

    def test_april(self):
        result = month_end(2024, 4)
        assert result.day == 30


class TestQuarterEnd:
    def test_q1(self):
        result = quarter_end(2024, 1)
        assert result.month == 3
        assert result.day == 31

    def test_q2(self):
        result = quarter_end(2024, 2)
        assert result.month == 6
        assert result.day == 30

    def test_q3(self):
        result = quarter_end(2024, 3)
        assert result.month == 9
        assert result.day == 30

    def test_q4(self):
        result = quarter_end(2024, 4)
        assert result.month == 12
        assert result.day == 31

    def test_aware(self):
        assert quarter_end(2024, 1).tzinfo == dt.timezone.utc


# ---------------------------------------------------------------------------
# iter_months / iter_quarters
# ---------------------------------------------------------------------------


class TestIterMonths:
    def test_single(self):
        assert list(iter_months(2024, 3, 2024, 3)) == [(2024, 3)]

    def test_spans_year(self):
        result = list(iter_months(2024, 11, 2025, 2))
        assert result == [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]

    def test_empty_when_start_after_end(self):
        assert list(iter_months(2025, 1, 2024, 12)) == []

    def test_full_year(self):
        result = list(iter_months(2024, 1, 2024, 12))
        assert len(result) == 12
        assert result[0] == (2024, 1)
        assert result[-1] == (2024, 12)


class TestIterQuarters:
    def test_single(self):
        assert list(iter_quarters(2024, 2, 2024, 2)) == [(2024, 2)]

    def test_spans_year(self):
        result = list(iter_quarters(2024, 3, 2025, 2))
        assert result == [(2024, 3), (2024, 4), (2025, 1), (2025, 2)]

    def test_empty_when_start_after_end(self):
        assert list(iter_quarters(2025, 1, 2024, 4)) == []

    def test_full_year(self):
        result = list(iter_quarters(2024, 1, 2024, 4))
        assert len(result) == 4


# ---------------------------------------------------------------------------
# week_of / week_label / week_end / iter_weeks  (ISO-week buckets)
# ---------------------------------------------------------------------------


class TestWeekOf:
    def test_basic(self):
        # 2026-01-01 is a Thursday -> ISO week 1 of 2026.
        assert week_of(dt.datetime(2026, 1, 1)) == (2026, 1)

    def test_iso_year_behind_calendar_year(self):
        # 2023-01-01 is a Sunday -> still ISO week 52 of 2022.
        assert week_of(dt.datetime(2023, 1, 1)) == (2022, 52)

    def test_iso_year_ahead_of_calendar_year(self):
        # 2024-12-30 is a Monday -> ISO week 1 of 2025.
        assert week_of(dt.datetime(2024, 12, 30)) == (2025, 1)


class TestWeekLabel:
    def test_zero_padded(self):
        assert week_label(2026, 3) == "2026-W03"

    def test_two_digit_week(self):
        assert week_label(2025, 52) == "2025-W52"


class TestWeekEnd:
    def test_sunday_end_of_week(self):
        # ISO 2026-W01 runs Mon 2025-12-29 .. Sun 2026-01-04.
        result = week_end(2026, 1)
        assert (result.year, result.month, result.day) == (2026, 1, 4)
        assert (result.hour, result.minute, result.second) == (23, 59, 59)

    def test_is_utc(self):
        assert week_end(2025, 52).tzinfo == dt.timezone.utc

    def test_week_52(self):
        # ISO 2025-W52 ends Sun 2025-12-28.
        result = week_end(2025, 52)
        assert (result.year, result.month, result.day) == (2025, 12, 28)


class TestIterWeeks:
    def test_single(self):
        assert list(iter_weeks(2026, 1, 2026, 1)) == [(2026, 1)]

    def test_spans_iso_year_rollover(self):
        # 2025-W52 -> 2026-W01 -> 2026-W02; the ISO year flips mid-range.
        result = list(iter_weeks(2025, 52, 2026, 2))
        assert result == [(2025, 52), (2026, 1), (2026, 2)]

    def test_empty_when_start_after_end(self):
        assert list(iter_weeks(2026, 5, 2026, 2)) == []

    def test_consecutive_count(self):
        result = list(iter_weeks(2026, 1, 2026, 10))
        assert len(result) == 10


# ---------------------------------------------------------------------------
# milestone_x
# ---------------------------------------------------------------------------


class TestMilestoneX:
    def test_monthly(self):
        assert milestone_x("2024-03-15") == "2024-03"

    def test_quarterly_q1(self):
        assert milestone_x("2024-02-01", buckets_mode="quarterly") == "2024-Q1"

    def test_quarterly_q2(self):
        assert milestone_x("2024-04-01", buckets_mode="quarterly") == "2024-Q2"

    def test_quarterly_q4(self):
        assert milestone_x("2024-11-30", buckets_mode="quarterly") == "2024-Q4"

    def test_monthly_default(self):
        assert milestone_x("2025-01-01") == "2025-01"

    def test_weekly(self):
        # 2026-01-15 is a Thursday -> ISO week 3 of 2026.
        assert milestone_x("2026-01-15", buckets_mode="weekly") == "2026-W03"

    def test_weekly_iso_year_rollover(self):
        # 2024-12-30 is a Monday -> ISO week 1 of 2025.
        assert milestone_x("2024-12-30", buckets_mode="weekly") == "2025-W01"


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_overlay_none_returns_base(self):
        base = {"a": 1}
        assert deep_merge(base, None) == {"a": 1}

    def test_non_dict_overlay_replaces(self):
        assert deep_merge({"a": 1}, "scalar") == "scalar"

    def test_simple_merge(self):
        result = deep_merge({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        overlay = {"x": {"b": 99, "c": 3}}
        result = deep_merge(base, overlay)
        assert result == {"x": {"a": 1, "b": 99, "c": 3}}

    def test_list_replaced_not_concatenated(self):
        base = {"items": [1, 2, 3]}
        overlay = {"items": [4, 5]}
        result = deep_merge(base, overlay)
        assert result["items"] == [4, 5]

    def test_deep_nested(self):
        base = {"a": {"b": {"c": 1}}}
        overlay = {"a": {"b": {"d": 2}}}
        result = deep_merge(base, overlay)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}


# ---------------------------------------------------------------------------
# _minimal_yaml_load
# ---------------------------------------------------------------------------


class TestMinimalYamlLoad:
    def test_simple_mapping(self):
        text = "key: value\nnum: 42\n"
        result = _minimal_yaml_load(text)
        assert result == {"key": "value", "num": 42}

    def test_boolean(self):
        result = _minimal_yaml_load("flag: true\n")
        assert result == {"flag": True}

    def test_null(self):
        result = _minimal_yaml_load("x: null\n")
        assert result == {"x": None}

    def test_nested(self):
        text = "outer:\n  inner: 1\n"
        result = _minimal_yaml_load(text)
        assert result == {"outer": {"inner": 1}}

    def test_sequence(self):
        text = "items:\n  - a\n  - b\n"
        result = _minimal_yaml_load(text)
        assert result == {"items": ["a", "b"]}

    def test_inline_list(self):
        result = _minimal_yaml_load("tags: [alpha, beta]\n")
        assert result == {"tags": ["alpha", "beta"]}

    def test_comment_stripped(self):
        result = _minimal_yaml_load("key: value  # comment\n")
        assert result == {"key": "value"}

    def test_float(self):
        result = _minimal_yaml_load("v: 3.14\n")
        assert result == {"v": pytest.approx(3.14)}

    def test_quoted_string(self):
        result = _minimal_yaml_load("s: 'hello world'\n")
        assert result == {"s": "hello world"}

    def test_mapping_in_sequence(self):
        text = "cats:\n  - name: foo\n    color: red\n"
        result = _minimal_yaml_load(text)
        assert result == {"cats": [{"name": "foo", "color": "red"}]}


# ---------------------------------------------------------------------------
# eval_predicate
# ---------------------------------------------------------------------------


def _ctx(labels=None, is_open=True, state_reason=None, pr_merged=False, scope_labels=None):
    return {
        "labels": set(labels or []),
        "is_open": is_open,
        "state_reason": state_reason,
        "pr_merged_by_snapshot": pr_merged,
        "scope_labels": set(scope_labels or []),
    }


class TestEvalPredicate:
    def test_non_dict_pred_returns_false(self):
        assert eval_predicate("bad", _ctx()) is False

    def test_empty_pred_matches_anything(self):
        assert eval_predicate({}, _ctx()) is True

    def test_state_open(self):
        assert eval_predicate({"state": "open"}, _ctx(is_open=True)) is True
        assert eval_predicate({"state": "open"}, _ctx(is_open=False)) is False

    def test_state_closed(self):
        assert eval_predicate({"state": "closed"}, _ctx(is_open=False)) is True

    def test_state_reason(self):
        assert eval_predicate({"state_reason": "COMPLETED"}, _ctx(state_reason="COMPLETED")) is True
        assert eval_predicate({"state_reason": "COMPLETED"}, _ctx(state_reason="NOT_PLANNED")) is False

    def test_any_label(self):
        assert eval_predicate({"any_label": ["a", "b"]}, _ctx(labels=["b"])) is True
        assert eval_predicate({"any_label": ["a", "b"]}, _ctx(labels=["c"])) is False

    def test_all_labels(self):
        assert eval_predicate({"all_labels": ["a", "b"]}, _ctx(labels=["a", "b", "c"])) is True
        assert eval_predicate({"all_labels": ["a", "b"]}, _ctx(labels=["a"])) is False

    def test_not_label(self):
        assert eval_predicate({"not_label": "bad"}, _ctx(labels=["good"])) is True
        assert eval_predicate({"not_label": "bad"}, _ctx(labels=["bad"])) is False

    def test_not_any_label(self):
        assert eval_predicate({"not_any_label": ["a", "b"]}, _ctx(labels=["c"])) is True
        assert eval_predicate({"not_any_label": ["a", "b"]}, _ctx(labels=["a"])) is False

    def test_pr_merged_by_snapshot(self):
        assert eval_predicate({"pr_merged_by_snapshot": True}, _ctx(pr_merged=True)) is True
        assert eval_predicate({"pr_merged_by_snapshot": True}, _ctx(pr_merged=False)) is False

    def test_no_scope_label_true(self):
        ctx = _ctx(labels=["bug"], scope_labels=["area/api", "area/core"])
        assert eval_predicate({"no_scope_label": True}, ctx) is True

    def test_no_scope_label_false_when_scope_present(self):
        ctx = _ctx(labels=["area/api"], scope_labels=["area/api", "area/core"])
        assert eval_predicate({"no_scope_label": True}, ctx) is False

    def test_has_scope_label(self):
        ctx = _ctx(labels=["area/api"], scope_labels=["area/api"])
        assert eval_predicate({"has_scope_label": True}, ctx) is True
        ctx2 = _ctx(labels=["bug"], scope_labels=["area/api"])
        assert eval_predicate({"has_scope_label": True}, ctx2) is False

    def test_any_of(self):
        pred = {"any_of": [{"state": "open"}, {"any_label": ["wontfix"]}]}
        assert eval_predicate(pred, _ctx(is_open=True)) is True
        assert eval_predicate(pred, _ctx(is_open=False, labels=["wontfix"])) is True
        assert eval_predicate(pred, _ctx(is_open=False)) is False

    def test_all_of_list(self):
        pred = {"all_of": [{"state": "closed"}, {"state_reason": "COMPLETED"}]}
        assert eval_predicate(pred, _ctx(is_open=False, state_reason="COMPLETED")) is True
        assert eval_predicate(pred, _ctx(is_open=False, state_reason="NOT_PLANNED")) is False

    def test_unknown_key_returns_false(self):
        assert eval_predicate({"unknown_key": "value"}, _ctx()) is False

    def test_composite(self):
        pred = {
            "state": "closed",
            "state_reason": "COMPLETED",
            "any_label": ["cve allocated"],
        }
        ctx = _ctx(is_open=False, state_reason="COMPLETED", labels=["cve allocated"])
        assert eval_predicate(pred, ctx) is True
        ctx2 = _ctx(is_open=False, state_reason="COMPLETED", labels=[])
        assert eval_predicate(pred, ctx2) is False


# ---------------------------------------------------------------------------
# mean_or_none
# ---------------------------------------------------------------------------


class TestMeanOrNone:
    def test_empty(self):
        assert mean_or_none([]) is None

    def test_single(self):
        assert mean_or_none([5.0]) == 5.0

    def test_multiple(self):
        assert mean_or_none([1.0, 2.0, 3.0]) == 2.0

    def test_rounds_to_two_places(self):
        result = mean_or_none([1.0, 2.0])
        assert result == 1.5
        result2 = mean_or_none([1.0, 2.0, 4.0])
        assert result2 == pytest.approx(2.33, abs=0.01)


# ---------------------------------------------------------------------------
# build_triage_regex
# ---------------------------------------------------------------------------


class TestBuildTriageRegex:
    def test_empty_returns_none(self):
        assert build_triage_regex([]) is None

    def test_single_keyword(self):
        pat = build_triage_regex(["triage"])
        assert pat is not None
        assert pat.search("please triage this") is not None
        assert pat.search("TRIAGE this") is not None

    def test_uppercase_word_boundary(self):
        pat = build_triage_regex(["CVE"])
        assert pat is not None
        # \b matches before '-', so "CVE-2024" still triggers
        assert pat.search("CVE-2024-1234") is not None
        # Does NOT match inside a longer word token
        assert pat.search("XCVE") is None
        assert pat.search("CVEx") is None
        assert pat.search("is a CVE here") is not None

    def test_phrase_keyword(self):
        pat = build_triage_regex(["needs triage"])
        assert pat is not None
        assert pat.search("this needs triage today") is not None

    def test_multiple_keywords(self):
        pat = build_triage_regex(["triage", "CVE", "needs review"])
        assert pat is not None
        assert pat.search("triage this") is not None
        assert pat.search("see the CVE today") is not None
        assert pat.search("needs review please") is not None
        assert pat.search("nothing here") is None


# ---------------------------------------------------------------------------
# is_bot_body
# ---------------------------------------------------------------------------


class TestIsBotBody:
    def test_none_returns_false(self):
        assert is_bot_body(None) is False

    def test_empty_returns_false(self):
        assert is_bot_body("") is False

    def test_no_prefix_match(self):
        assert is_bot_body("regular comment", ("<!-- bot -->",)) is False

    def test_prefix_match(self):
        assert is_bot_body("<!-- bot --> auto generated", ("<!-- bot -->",)) is True

    def test_leading_whitespace_stripped(self):
        assert is_bot_body("  <!-- bot -->body", ("<!-- bot -->",)) is True

    def test_multiple_prefixes(self):
        assert is_bot_body("[BOT] hello", ("[BOT]", "<!-- auto -->")) is True
        assert is_bot_body("<!-- auto --> hi", ("[BOT]", "<!-- auto -->")) is True

    def test_default_empty_prefixes(self):
        assert is_bot_body("<!-- bot -->") is False


# ---------------------------------------------------------------------------
# js_array / js_quotes
# ---------------------------------------------------------------------------


class TestJsArray:
    def test_empty(self):
        assert js_array([]) == "[]"

    def test_integers(self):
        assert js_array([1, 2, 3]) == "[1, 2, 3]"

    def test_none_default(self):
        assert js_array([1, None, 3]) == "[1, null, 3]"

    def test_none_custom(self):
        assert js_array([None], fmt_null="undefined") == "[undefined]"

    def test_float_with_decimal(self):
        assert js_array([1.5]) == "[1.50]"

    def test_float_whole_number(self):
        assert js_array([2.0]) == "[2]"

    def test_mixed(self):
        result = js_array([1, None, 2.5])
        assert result == "[1, null, 2.50]"


class TestJsQuotes:
    def test_empty(self):
        assert js_quotes([]) == "[]"

    def test_single(self):
        assert js_quotes(["hello"]) == '["hello"]'

    def test_multiple(self):
        assert js_quotes(["a", "b", "c"]) == '["a", "b", "c"]'
