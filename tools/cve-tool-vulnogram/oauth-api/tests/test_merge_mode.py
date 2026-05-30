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
"""Unit tests for :mod:`vulnogram_api.merge_mode`.

The integration tests in ``test_record_update.py`` exercise these
through the CLI's exit codes. This file pins down the merge / refusal
contract at the function level so a regression there is caught even
when the CLI wiring changes.
"""

from __future__ import annotations

import copy

import pytest

from vulnogram_api.merge_mode import (
    MergeModeRefused,
    _diff_affected_products,
    _merge_references_by_url,
    apply_merge_mode_guards,
)


def _current(
    *,
    state: str = "PUBLIC",
    references: list[dict] | None = None,
    affected: list[dict] | None = None,
) -> dict:
    """Build a current-record snapshot (the ``get_record`` shape:
    ``comments`` / ``files`` / ``body`` envelope).
    """
    return {
        "comments": [],
        "files": [],
        "body": {
            "cveMetadata": {"cveId": "CVE-2026-00001", "state": "PUBLISHED"},
            "CNA_private": {"state": state},
            "containers": {
                "cna": {
                    "affected": affected
                    if affected is not None
                    else [{"packageName": "apache-foo", "product": "Apache Foo"}],
                    "references": references
                    if references is not None
                    else [
                        {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                        {
                            "url": "https://lists.apache.org/thread/abc",
                            "tags": ["vendor-advisory"],
                        },
                    ],
                },
            },
        },
    }


def _new(
    *,
    state: str = "PUBLIC",
    references: list[dict] | None = None,
    affected: list[dict] | None = None,
) -> dict:
    """Build the new push body shape (no ``comments`` / ``files`` wrapper)."""
    return {
        "cveMetadata": {"cveId": "CVE-2026-00001", "state": "PUBLISHED"},
        "CNA_private": {"state": state},
        "containers": {
            "cna": {
                "affected": affected
                if affected is not None
                else [{"packageName": "apache-foo", "product": "Apache Foo"}],
                "references": references
                if references is not None
                else [{"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]}],
            },
        },
    }


# ---------------------------------------------------------------------------
# State-downgrade guard
# ---------------------------------------------------------------------------


class TestStateDowngradeGuard:
    def test_public_to_review_refused(self):
        with pytest.raises(MergeModeRefused, match="state downgrade"):
            apply_merge_mode_guards(_current(state="PUBLIC"), _new(state="REVIEW"))

    def test_public_to_draft_refused(self):
        with pytest.raises(MergeModeRefused, match="state downgrade"):
            apply_merge_mode_guards(_current(state="PUBLIC"), _new(state="DRAFT"))

    def test_public_to_public_allowed(self):
        # No transition at all — emit identical state.
        merged = apply_merge_mode_guards(_current(state="PUBLIC"), _new(state="PUBLIC"))
        assert merged["CNA_private"]["state"] == "PUBLIC"

    def test_review_to_review_allowed(self):
        # Not a downgrade from PUBLIC; the guard does not fire.
        merged = apply_merge_mode_guards(_current(state="REVIEW"), _new(state="REVIEW"))
        assert merged["CNA_private"]["state"] == "REVIEW"

    def test_review_to_public_allowed(self):
        # Upgrade — exactly what release managers do on publication.
        merged = apply_merge_mode_guards(_current(state="REVIEW"), _new(state="PUBLIC"))
        assert merged["CNA_private"]["state"] == "PUBLIC"

    def test_public_to_review_with_override_allowed(self):
        merged = apply_merge_mode_guards(
            _current(state="PUBLIC"),
            _new(state="REVIEW"),
            allow_state_downgrade=True,
        )
        assert merged["CNA_private"]["state"] == "REVIEW"

    def test_message_names_both_states(self):
        with pytest.raises(MergeModeRefused) as excinfo:
            apply_merge_mode_guards(_current(state="PUBLIC"), _new(state="REVIEW"))
        message = str(excinfo.value)
        assert "PUBLIC" in message
        assert "REVIEW" in message
        assert "--allow-state-downgrade" in message


# ---------------------------------------------------------------------------
# References merge
# ---------------------------------------------------------------------------


class TestReferencesMerge:
    def test_merge_preserves_url_not_in_new(self):
        merged = _merge_references_by_url(
            current=[
                {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                {"url": "https://lists.apache.org/thread/abc", "tags": ["vendor-advisory"]},
            ],
            new=[
                {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
            ],
        )
        urls = [ref["url"] for ref in merged]
        assert "https://lists.apache.org/thread/abc" in urls

    def test_merge_new_entries_come_first(self):
        merged = _merge_references_by_url(
            current=[{"url": "https://existing", "tags": []}],
            new=[{"url": "https://just-added", "tags": ["patch"]}],
        )
        urls = [ref["url"] for ref in merged]
        assert urls == ["https://just-added", "https://existing"]

    def test_merge_deduplicates_by_url(self):
        # When the same URL appears in both, the new emission's
        # entry wins (its tags / metadata may have changed).
        merged = _merge_references_by_url(
            current=[{"url": "https://x", "tags": ["old-tag"]}],
            new=[{"url": "https://x", "tags": ["new-tag"]}],
        )
        assert len(merged) == 1
        assert merged[0]["tags"] == ["new-tag"]

    def test_apply_merges_references_by_default(self):
        merged = apply_merge_mode_guards(_current(), _new())
        urls = {ref["url"] for ref in merged["containers"]["cna"]["references"]}
        assert "https://github.com/apache/foo/pull/1" in urls
        assert "https://lists.apache.org/thread/abc" in urls

    def test_apply_replaces_references_with_flag(self):
        # state=REVIEW so this stays scoped to the references-merge
        # guard; the new state-upgrade-to-PUBLIC guard fires only on
        # PUBLIC pushes without a vendor-advisory reference and is
        # covered separately in TestStateUpgradeToPublicGuard.
        merged = apply_merge_mode_guards(
            _current(state="REVIEW"),
            _new(state="REVIEW"),
            replace_references=True,
        )
        urls = {ref["url"] for ref in merged["containers"]["cna"]["references"]}
        assert urls == {"https://github.com/apache/foo/pull/1"}

    def test_apply_does_not_create_empty_references_block(self):
        """When both current and new have no references, the merged
        document should not sprout an empty ``references: []`` field.
        """
        # state=REVIEW for the same reason as above — keeps this test
        # scoped to the references-merge guard.
        current = _current(state="REVIEW", references=[])
        new = _new(state="REVIEW", references=[])
        del current["body"]["containers"]["cna"]["references"]
        new_copy = copy.deepcopy(new)
        del new_copy["containers"]["cna"]["references"]
        merged = apply_merge_mode_guards(current, new_copy)
        # The new doc has no `references` key — merged should keep it absent.
        assert "references" not in merged["containers"]["cna"]


# ---------------------------------------------------------------------------
# State-upgrade-to-PUBLIC guard
# ---------------------------------------------------------------------------


class TestStateUpgradeToPublicGuard:
    """The guard refuses ``state=PUBLIC`` pushes when the document
    (after the references merge) carries no ``vendor-advisory``
    reference. Per Arnout Engelen's 2026-05-29 review on
    CVE-2026-40913: PUBLIC is only legitimate after the advisory has
    shipped and the archived users-list URL has been added to
    ``references[]``.
    """

    def test_public_without_vendor_advisory_refused(self):
        with pytest.raises(MergeModeRefused, match='state = "PUBLIC" push'):
            apply_merge_mode_guards(
                _current(state="REVIEW", references=[]),
                _new(
                    state="PUBLIC",
                    references=[
                        {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                    ],
                ),
            )

    def test_public_with_vendor_advisory_allowed(self):
        merged = apply_merge_mode_guards(
            _current(state="REVIEW", references=[]),
            _new(
                state="PUBLIC",
                references=[
                    {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                    {"url": "https://lists.apache.org/thread/abc", "tags": ["vendor-advisory"]},
                ],
            ),
        )
        assert merged["CNA_private"]["state"] == "PUBLIC"

    def test_public_picks_up_vendor_advisory_from_current_via_merge(self):
        """When the new doc lacks the vendor-advisory reference but
        the current doc has it, the references merge restores it
        before the guard runs — the push succeeds.

        This is the idempotent re-push case: the generator emits a
        record that omits the advisory URL the operator added by
        hand on a previous push; the merge restores it; the guard
        sees the final state has the vendor-advisory ref and passes.
        """
        merged = apply_merge_mode_guards(
            _current(
                state="PUBLIC",
                references=[
                    {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                    {"url": "https://lists.apache.org/thread/abc", "tags": ["vendor-advisory"]},
                ],
            ),
            _new(
                state="PUBLIC",
                references=[
                    {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                ],
            ),
        )
        assert merged["CNA_private"]["state"] == "PUBLIC"
        urls = {ref["url"] for ref in merged["containers"]["cna"]["references"]}
        assert "https://lists.apache.org/thread/abc" in urls

    def test_public_with_replace_references_and_no_vendor_advisory_refused(self):
        """``replace_references=True`` drops the current doc's
        references — the merge does NOT restore the vendor-advisory
        ref. State=PUBLIC must still be refused.
        """
        with pytest.raises(MergeModeRefused, match='state = "PUBLIC" push'):
            apply_merge_mode_guards(
                _current(
                    state="REVIEW",
                    references=[
                        {"url": "https://lists.apache.org/thread/abc", "tags": ["vendor-advisory"]},
                    ],
                ),
                _new(
                    state="PUBLIC",
                    references=[
                        {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                    ],
                ),
                replace_references=True,
            )

    def test_review_to_review_no_vendor_advisory_passes(self):
        """The guard only fires on PUBLIC pushes — REVIEW pushes
        without a vendor-advisory ref are normal.
        """
        merged = apply_merge_mode_guards(
            _current(state="REVIEW", references=[]),
            _new(
                state="REVIEW",
                references=[
                    {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                ],
            ),
        )
        assert merged["CNA_private"]["state"] == "REVIEW"

    def test_error_message_names_record_publish(self):
        """The error message must point the operator at the sanctioned
        path (``vulnogram-api-record-publish``) so they don't reach for
        the ``--allow-state-upgrade`` flag (which intentionally
        doesn't exist).
        """
        with pytest.raises(MergeModeRefused) as exc_info:
            apply_merge_mode_guards(
                _current(state="REVIEW", references=[]),
                _new(
                    state="PUBLIC",
                    references=[
                        {"url": "https://github.com/apache/foo/pull/1", "tags": ["patch"]},
                    ],
                ),
            )
        msg = str(exc_info.value)
        assert "vulnogram-api-record-publish" in msg
        assert "vendor-advisory" in msg


# ---------------------------------------------------------------------------
# Product / packageName change guard
# ---------------------------------------------------------------------------


class TestProductChangeGuard:
    def test_packagename_change_refused(self):
        with pytest.raises(MergeModeRefused, match="product"):
            apply_merge_mode_guards(
                _current(affected=[{"packageName": "apache-foo-bar", "product": "Apache Foo Bar"}]),
                _new(affected=[{"packageName": "apache-foo", "product": "Apache Foo"}]),
            )

    def test_product_only_change_refused(self):
        # Same packageName, different product display name. Still
        # refused — the display name is what shows on the cve.org page.
        with pytest.raises(MergeModeRefused, match="product"):
            apply_merge_mode_guards(
                _current(affected=[{"packageName": "apache-foo", "product": "Apache Foo Original"}]),
                _new(affected=[{"packageName": "apache-foo", "product": "Apache Foo Rewritten"}]),
            )

    def test_same_product_allowed(self):
        merged = apply_merge_mode_guards(_current(), _new())
        assert merged["containers"]["cna"]["affected"][0]["packageName"] == "apache-foo"

    def test_change_allowed_with_flag(self):
        merged = apply_merge_mode_guards(
            _current(affected=[{"packageName": "apache-foo-bar", "product": "Apache Foo Bar"}]),
            _new(affected=[{"packageName": "apache-foo", "product": "Apache Foo"}]),
            allow_product_change=True,
        )
        assert merged["containers"]["cna"]["affected"][0]["packageName"] == "apache-foo"

    def test_diff_lists_dropped_and_added(self):
        diffs = _diff_affected_products(
            current=[{"packageName": "apache-foo-bar", "product": "Apache Foo Bar"}],
            new=[{"packageName": "apache-foo", "product": "Apache Foo"}],
        )
        joined = "\n".join(diffs)
        assert "removed" in joined
        assert "added" in joined
        assert "apache-foo-bar" in joined
        assert "apache-foo" in joined

    def test_diff_empty_when_unchanged(self):
        diffs = _diff_affected_products(
            current=[{"packageName": "apache-foo", "product": "Apache Foo"}],
            new=[{"packageName": "apache-foo", "product": "Apache Foo"}],
        )
        assert diffs == []

    def test_diff_ignores_order(self):
        # The signatures are compared as a set, so re-ordering
        # affected[] entries between the current record and the new
        # emission must not trip the guard.
        diffs = _diff_affected_products(
            current=[
                {"packageName": "apache-foo", "product": "Apache Foo"},
                {"packageName": "apache-bar", "product": "Apache Bar"},
            ],
            new=[
                {"packageName": "apache-bar", "product": "Apache Bar"},
                {"packageName": "apache-foo", "product": "Apache Foo"},
            ],
        )
        assert diffs == []

    def test_diff_empty_when_current_is_first_time_populated(self):
        # A freshly-allocated RESERVED record carries an empty ``affected[]``;
        # the first push that populates it must not be treated as a product
        # *change* (there is no prior signature to be renamed away from).
        diffs = _diff_affected_products(
            current=[],
            new=[{"packageName": "apache-foo", "product": "Apache Foo"}],
        )
        assert diffs == []

    def test_first_time_population_does_not_require_allow_product_change(self):
        # End-to-end: pushing a populated ``affected[]`` onto a record that
        # had none before must succeed without ``--allow-product-change``.
        merged = apply_merge_mode_guards(
            _current(affected=[]),
            _new(affected=[{"packageName": "apache-foo", "product": "Apache Foo"}]),
        )
        assert merged["containers"]["cna"]["affected"][0]["packageName"] == "apache-foo"


# ---------------------------------------------------------------------------
# Composition + edge cases
# ---------------------------------------------------------------------------


class TestApplyComposition:
    def test_no_current_doc_is_noop(self):
        new = _new(state="REVIEW", affected=[{"packageName": "x", "product": "X"}])
        merged = apply_merge_mode_guards(None, new)
        # Nothing to compare against → return the input verbatim.
        assert merged is new

    def test_input_not_mutated_on_merge(self):
        new = _new()
        original_refs = list(new["containers"]["cna"]["references"])
        apply_merge_mode_guards(_current(), new)
        # The original new doc still has its original references list
        # (the merge made a deep copy).
        assert new["containers"]["cna"]["references"] == original_refs

    def test_all_guards_pass_returns_merged_doc(self):
        merged = apply_merge_mode_guards(_current(), _new())
        assert merged["CNA_private"]["state"] == "PUBLIC"
        urls = {ref["url"] for ref in merged["containers"]["cna"]["references"]}
        assert urls == {
            "https://github.com/apache/foo/pull/1",
            "https://lists.apache.org/thread/abc",
        }
