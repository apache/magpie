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
"""Merge-mode safety nets for ``vulnogram-api-record-update``.

The default Vulnogram API push is a full record replacement: whatever
JSON the script sends becomes the record. That model has bitten the
security team in three concrete ways during 2026:

* ``CVE-2026-41016`` — a regenerated push from the wrong sibling
  tracker moved the record's ``CNA_private.state`` from ``PUBLIC``
  back to ``REVIEW``, broke the ``cve.org`` advisory's lifecycle
  ownership, and required a manual revert.
* Same record — the regenerator overwrote ``affected[].product`` /
  ``packageName`` (the originally-published shape was
  ``Apache Airflow Providers SMTP`` / ``apache-airflow-providers-smtp``;
  the re-push from the core-scope sibling produced
  ``Apache Airflow`` / ``apache-airflow``), changing the meaning of
  the record after publication.
* Same record — the hand-added ``lists.apache.org/thread/<hash>``
  advisory URL in ``references[]`` was lost when the regenerated
  document only carried the fix PR.

This module supplies three guard checks the push can run before
sending. Each one is **opt-out**: by default the guard is active and
the push refuses (or merges) when it would otherwise regress the
record. Explicit override flags let a release manager force the
change when the regression is intentional.

The guards work on the **document body** that the API push sends
(``cveMetadata`` / ``CNA_private`` / ``containers``) versus the
**body** sub-object of the fetched record (Vulnogram's GET endpoint
wraps the same shape under ``body``). The asymmetry is unavoidable —
the API was built that way long before this module existed.
"""

from __future__ import annotations

import copy
from typing import Any


class MergeModeRefused(Exception):
    """Raised when a merge-mode guard rejects the push.

    The constructor takes a single ``message`` argument; the script
    surfaces it verbatim to the user with a non-zero exit code so the
    release manager sees exactly which guard fired and which override
    flag to add if the change is deliberate.
    """


def _path(obj: Any, *keys: str) -> Any:
    """Navigate ``obj`` along ``keys``; return ``None`` on any miss."""
    current: Any = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _current_state(current_doc: dict[str, Any]) -> str | None:
    """Return ``current_doc.body.CNA_private.state`` or ``None``."""
    return _path(current_doc, "body", "CNA_private", "state")


def _new_state(new_doc: dict[str, Any]) -> str | None:
    """Return ``new_doc.CNA_private.state`` or ``None``."""
    return _path(new_doc, "CNA_private", "state")


def _current_references(current_doc: dict[str, Any]) -> list[dict[str, Any]]:
    refs = _path(current_doc, "body", "containers", "cna", "references")
    return list(refs) if isinstance(refs, list) else []


def _new_references(new_doc: dict[str, Any]) -> list[dict[str, Any]]:
    refs = _path(new_doc, "containers", "cna", "references")
    return list(refs) if isinstance(refs, list) else []


def _has_vendor_advisory_reference(refs: list[dict[str, Any]]) -> bool:
    """Return ``True`` when ``refs`` contains an entry tagged
    ``vendor-advisory``.

    The ``vendor-advisory`` tag is the structural signal that a public
    advisory URL has shipped (typically the archived ``users-list``
    thread on ``lists.apache.org`` or ``security.apache.org``). The
    state-upgrade-to-PUBLIC guard in :func:`apply_merge_mode_guards`
    refuses any push that lacks one — per ASF Security policy (Arnout
    Engelen's 2026-05-29 review on CVE-2026-40913), a record may only
    reach ``PUBLIC`` *after* the advisory has actually shipped, not
    while the team is still preparing it.
    """
    for ref in refs:
        tags = ref.get("tags")
        if isinstance(tags, list) and "vendor-advisory" in tags:
            return True
    return False


def _current_affected(current_doc: dict[str, Any]) -> list[dict[str, Any]]:
    aff = _path(current_doc, "body", "containers", "cna", "affected")
    return list(aff) if isinstance(aff, list) else []


def _new_affected(new_doc: dict[str, Any]) -> list[dict[str, Any]]:
    aff = _path(new_doc, "containers", "cna", "affected")
    return list(aff) if isinstance(aff, list) else []


def _merge_references_by_url(
    current: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Union-merge references, keyed by ``url``.

    Order: the new emission's entries come first (in their original
    order), followed by any current-record entries whose URL is not
    in the new emission. The order matters for human-readability of
    the rendered advisory page; the new emission is presumed to
    reflect the latest reviewer intent.

    Entries without a ``url`` field are passed through as-is from the
    new emission (current-record duplicates are not detected because
    there is no key to match on).
    """
    new_urls = {entry.get("url") for entry in new}
    merged: list[dict[str, Any]] = list(new)
    for entry in current:
        url = entry.get("url")
        if url and url not in new_urls:
            merged.append(entry)
    return merged


def _product_signature(entry: dict[str, Any]) -> tuple[str, str]:
    """Return ``(packageName, product)`` for an ``affected[]`` entry.

    Either field may be missing; the signature uses ``""`` to keep
    set semantics consistent.
    """
    package = str(entry.get("packageName") or "")
    product = str(entry.get("product") or "")
    return (package, product)


def _diff_affected_products(
    current: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[str]:
    """Return a list of human-readable diffs for product/packageName
    changes between the current and new affected[] arrays.

    Returns an empty list when both arrays carry the same
    ``(packageName, product)`` signatures (order ignored). Otherwise
    returns one line per dropped, added, or renamed signature so the
    caller can decide whether to refuse or warn.
    """
    current_sigs = {_product_signature(entry) for entry in current if isinstance(entry, dict)}
    new_sigs = {_product_signature(entry) for entry in new if isinstance(entry, dict)}
    if current_sigs == new_sigs:
        return []
    # First-time population (e.g. a freshly-allocated RESERVED record with an
    # empty ``affected[]``) is not a product *change* — there is no prior
    # signature to be renamed away from. Treat it as a non-diff so the guard
    # does not force --allow-product-change for the normal first push.
    if not current_sigs:
        return []
    diffs: list[str] = []
    for sig in sorted(current_sigs - new_sigs):
        package, product = sig
        diffs.append(f"  - removed:  packageName={package!r}, product={product!r}")
    for sig in sorted(new_sigs - current_sigs):
        package, product = sig
        diffs.append(f"  + added:    packageName={package!r}, product={product!r}")
    return diffs


def apply_merge_mode_guards(
    current_doc: dict[str, Any] | None,
    new_doc: dict[str, Any],
    *,
    allow_state_downgrade: bool = False,
    replace_references: bool = False,
    allow_product_change: bool = False,
) -> dict[str, Any]:
    """Apply the three safety nets and return the document to push.

    ``current_doc`` is the record's current state as returned by
    :func:`vulnogram_api.client.get_record` (i.e. the ``comments`` /
    ``files`` / ``body`` envelope). When ``None`` — the record does
    not exist yet — the guards are no-ops and ``new_doc`` is returned
    unchanged (no current state to compare against).

    ``new_doc`` is the body the script intends to push (``cveMetadata``
    / ``CNA_private`` / ``containers`` at the top level). A deep copy
    is taken before mutation; the input is not modified in place so
    the caller's reference stays stable.

    The three guards in order:

    1. **State downgrade**: refuse when ``current.CNA_private.state ==
       "PUBLIC"`` and ``new.CNA_private.state != "PUBLIC"``. Raise
       :class:`MergeModeRefused` unless ``allow_state_downgrade`` is
       ``True``. PUBLIC means the record was pushed to cve.org and
       walking it back to REVIEW / DRAFT is almost always an
       accidental side-effect of a regenerator re-push.
    2. **References merge**: when ``replace_references`` is ``False``
       (the default), union the current record's ``references[]``
       with the new emission's by URL, preserving any URL not in the
       new emission. This catches the hand-added advisory URL that
       the regenerator does not know about.
    3. **Product / packageName change**: when ``allow_product_change``
       is ``False`` (the default) and any ``affected[]`` entry's
       ``(packageName, product)`` signature differs between the
       current record and the new emission, raise
       :class:`MergeModeRefused` with a diff so the caller can decide
       whether the change is intentional (e.g. broadening the scope
       to add a new package) or a regression.
    """
    if current_doc is None:
        # First push — nothing to merge against. The guards exist to
        # prevent regressions of already-published state, and a new
        # record has no published state to regress.
        return new_doc

    merged = copy.deepcopy(new_doc)

    current_state = _current_state(current_doc)
    new_state_value = _new_state(merged)
    if (
        current_state == "PUBLIC"
        and new_state_value is not None
        and new_state_value != "PUBLIC"
        and not allow_state_downgrade
    ):
        raise MergeModeRefused(
            f"Refusing CNA_private.state downgrade "
            f"{current_state!r} → {new_state_value!r}. The record was "
            f"published to cve.org at the PUBLIC state; walking it "
            f"back to REVIEW/DRAFT is almost always an accidental "
            f"regression. Pass --allow-state-downgrade to force "
            f'the push, or set CNA_private.state = "PUBLIC" in the '
            f"JSON file before re-running."
        )

    if not replace_references:
        merged_refs = _merge_references_by_url(
            current=_current_references(current_doc),
            new=_new_references(merged),
        )
        # Only write back when the merge added something — avoids
        # an empty `references` block sprouting on records that
        # never had one.
        if merged_refs:
            containers = merged.setdefault("containers", {})
            cna = containers.setdefault("cna", {})
            cna["references"] = merged_refs

    # State-upgrade-to-PUBLIC guard: refuse pushing state=PUBLIC when
    # the document about to be pushed (post-references-merge) does not
    # carry a `vendor-advisory` reference. PUBLIC is only legitimate
    # after the advisory has shipped to users@ / announce@ and the
    # archived users-list URL has been added to references[] (which
    # `classify_reference` tags as `vendor-advisory`). Without that,
    # the operator is hand-flipping the state ahead of the actual
    # advisory send — the exact failure mode Arnout Engelen flagged on
    # CVE-2026-40913 (2026-05-29). The generator's
    # `compute_cna_private_state` already enforces this on the emit
    # side; this guard catches the case where the operator hand-edits
    # the JSON file (or pastes via Vulnogram's `#source` tab and then
    # re-pushes) before re-running.
    #
    # The check runs AFTER the references merge so a record whose
    # current state already has the vendor-advisory reference (e.g.
    # an idempotent re-push of an already-PUBLIC record where the new
    # JSON dropped the advisory ref for some reason) passes — the
    # merge restores the ref, and that is the intended behaviour. The
    # guard catches the case where neither side carries the
    # vendor-advisory reference, which is the only true failure mode.
    #
    # There is intentionally no `--allow-state-upgrade` override: the
    # sanctioned path to PUBLIC is `vulnogram-api-record-publish`,
    # which fires on the archive-URL signal and inserts the
    # `vendor-advisory` reference at the same time.
    if new_state_value == "PUBLIC" and not _has_vendor_advisory_reference(_new_references(merged)):
        raise MergeModeRefused(
            'Refusing CNA_private.state = "PUBLIC" push: the JSON '
            "carries no `vendor-advisory` reference. PUBLIC is only "
            "legitimate after the advisory has shipped to users@ / "
            "announce@ and the archived users-list URL has been added "
            "to references[]. The sanctioned path to PUBLIC is "
            "`vulnogram-api-record-publish`, which fires on the archive-"
            "URL signal — invoke that instead of pushing PUBLIC via "
            "record-update. (See Arnout Engelen's 2026-05-29 review "
            "comment on CVE-2026-40913 for why this guard exists.)"
        )

    diffs = _diff_affected_products(
        current=_current_affected(current_doc),
        new=_new_affected(merged),
    )
    if diffs and not allow_product_change:
        raise MergeModeRefused(
            "Refusing affected[].product / packageName change(s):\n"
            + "\n".join(diffs)
            + "\nIf the change is intentional (e.g. broadening the "
            "scope to add a new package, or correcting the originally-"
            "published product name), pass --allow-product-change to "
            "force the push. Otherwise the regenerator emitted the "
            "wrong scope — check the originating tracker's labels."
        )

    return merged
