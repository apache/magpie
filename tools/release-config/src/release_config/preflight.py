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
"""Each release-* skill's deterministic Step 0 checks, and its Step 1 metadata.

Every rule here is transcribed from the skill's own `## Step 0 — Pre-flight
check` list. Rules several skills share have one implementation: the source
version / RC format (`versions`), the approver roster
(`release_approver_roster_path`), the ASF identity (`organization: ASF`, from
which `non_asf` derives), the automated-signing gate (the organization's
`release_process.automated_signing`) and the archive default for the ASF
backends (see the README's *Shared rules*). Checks that need
the network, GitHub or judgement (planning-issue discovery, labels, RC tag
existence, staging-URL reachability, KEYS contents) stay with the skill; the
values they need are passed in as flags or returned for the skill to use.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from release_config import mdconfig as md
from release_config import versions
from release_config.config import (
    ASF_ARCHIVE_DEFAULT,
    ASF_DIST_BACKENDS,
    BUILD,
    DIST_BACKENDS,
    RMC,
    TRAINS,
    Loaded,
    iso,
    parse_time,
    plus_one_hour,
    render_dist_url,
)

FINGERPRINT = re.compile(r"^[0-9A-F]{40}$")

SKILLS = (
    "rc-cut",
    "vote-draft",
    "vote-tally",
    "announce-draft",
    "promote",
    "verify-rc",
    "archive-sweep",
    "audit-report",
    "keys-sync",
    "prepare",
)


def normalise_skill(name: str) -> str:
    short = name.split(":", 1)[-1]
    short = short.removeprefix("magpie-").removeprefix("release-")
    if short not in SKILLS:
        raise ValueError(f"unknown skill {name!r}; expected one of: {', '.join(SKILLS)}")
    return short


@dataclass
class Result:
    skill: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)

    def block(self, message: str) -> None:
        self.blockers.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": not self.blockers, "skill": self.skill, "blockers": self.blockers, "warnings": self.warnings, "values": self.values}


# --------------------------------------------------------------------------- shared


def _now(args: argparse.Namespace) -> datetime:
    return parse_time(args.now) if args.now else datetime.now(UTC)


def _require_file(result: Result, cfg: Loaded, name: str) -> bool:
    if cfg.sources.get(name) is None:
        result.block(f"{name} not found in <project-config> (looked in .apache-magpie-local/ then .apache-magpie-overrides/)")
        return False
    return True


def _require_keys(result: Result, cfg: Loaded, keys: tuple[str, ...]) -> None:
    if not _require_file(result, cfg, RMC):
        return
    for key in keys:
        if not cfg.present(key):
            result.block(f"required key `{key}` is missing from release-management-config.md")
        elif md.is_placeholder(cfg.raw[key]):
            result.warn(f"`{key}` still holds the template placeholder {cfg.raw[key]!r}")


def _positional(args: argparse.Namespace, index: int) -> str | None:
    return args.args[index] if len(args.args) > index else None


def _rc_id(result: Result, args: argparse.Namespace, pattern: re.Pattern[str], shape: str) -> tuple[str | None, str | None]:
    raw = _positional(args, 0)
    if raw is None:
        result.block(f"RC identifier missing; expected {shape}")
        return None, None
    match = pattern.match(raw)
    if not match:
        result.block(f"RC identifier {raw!r} does not match {shape}")
        return None, None
    return match.group("version"), match.group("rc")


def _version(result: Result, args: argparse.Namespace, pattern: re.Pattern[str], shape: str, index: int = 0) -> str | None:
    raw = _positional(args, index)
    if raw is None:
        result.block(f"version argument missing; expected {shape}")
        return None
    if not pattern.match(raw):
        result.block(f"version {raw!r} does not match {shape}")
        return None
    return raw


def _roster(result: Result, cfg: Loaded) -> md.Roster | None:
    """The approver roster at `release_approver_roster_path` (default `<project-config>/pmc-roster.md`); blocks when unusable."""
    value = cfg.approver_roster_path
    path = cfg.resolver.resolve_ref(value)
    roster = md.parse_roster(path)
    result.values["roster_path"] = cfg.resolver.display(path) if path else value
    label = "approver roster (release_approver_roster_path)"
    if roster is None:
        result.block(f"{label} {value!r} is not readable")
        return None
    if not roster.rows:
        extra = f" ({roster.placeholder_rows} template placeholder rows)" if roster.placeholder_rows else ""
        result.block(f"{label} {result.values['roster_path']} has no roster rows{extra}")
        return None
    return roster


def _user_value(cfg: Loaded, dotted: str) -> str | None:
    return md.dotted_value(cfg.user_text, dotted)


def _staging_url(cfg: Loaded, version: str | None, rc: str | None) -> str | None:
    template = cfg.raw.get("release_dist_url_template")
    if not isinstance(template, str) or not template or version is None or rc is None:
        return None
    return render_dist_url(template, version, rc, "dev")


def _target_url(cfg: Loaded, version: str | None) -> str | None:
    template = cfg.raw.get("release_dist_url_template")
    if not isinstance(template, str) or not template or version is None:
        return None
    return render_dist_url(template, version, None, "release")


def _source_version(result: Result, args: argparse.Namespace, index: int = 0) -> str | None:
    return _version(result, args, versions.SOURCE_VERSION, versions.SOURCE_VERSION_SHAPE, index)


def _source_rc_id(result: Result, args: argparse.Namespace) -> tuple[str | None, str | None]:
    return _rc_id(result, args, versions.SOURCE_RC_ID, versions.SOURCE_RC_ID_SHAPE)


def _convenience_versions(result: Result, cfg: Loaded, version: str | None, rc: str | None) -> None:
    """Check each convenience artefact's version against its `version_scheme`.

    An unknown or absent scheme is reported as unvalidated, for the RM to judge.
    """
    checks = [versions.check_convenience(entry, version, rc) for entry in cfg.build.convenience_artefacts]
    for check in checks:
        name, scheme = check["name"], check["version_scheme"]
        if check["status"] == "invalid":
            result.block(f"convenience artefact {name!r} (version_scheme {scheme}): " + "; ".join(check["problems"]))
        elif scheme is None:
            result.warn(
                f"convenience artefact {name!r} declares no version_scheme, so its version {check['version']!r} is not validated; "
                f"set `version_scheme` in release-build.md § Convenience artefacts (validated: {', '.join(versions.SCHEMES)})"
            )
        elif check["status"] == "unvalidated":
            result.warn(
                f"convenience artefact {name!r} has version_scheme {scheme!r}, which the tool does not validate; the RM confirms its version {check['version']!r}"
            )
    if checks:
        result.values["convenience_versions"] = [{k: c[k] for k in ("name", "version", "version_scheme", "status")} for c in checks]


def _well_formed(url: str | None) -> bool:
    return bool(url) and bool(re.match(r"^(https?|s3)://\S+$", url or "")) and "<" not in (url or "") and ">" not in (url or "")


def _signing_consistency(result: Result, cfg: Loaded) -> None:
    """rc-cut: automated signing (where the organization offers it) needs the reproducibility it promises."""
    if cfg.signing_mode != "ci-automated":
        return
    build = cfg.build
    if build.reproducibility_source != "on":
        result.block(
            f"automated_release_signing is enabled but release-build.md sets reproducibility_source to {build.reproducibility_source!r}; it must be `on`"
        )
    if build.convenience_artefacts:
        for entry in build.convenience_artefacts:
            if entry.get("reproducibility") != "byte-identical":
                result.block(
                    "automated_release_signing is enabled but convenience artefact "
                    f"{entry.get('name')!r} has reproducibility {entry.get('reproducibility')!r}; it must be `byte-identical`"
                )
    elif any(a["kind"] == "convenience" for a in build.expected_artefacts) and build.reproducibility_binaries != "byte-identical":
        result.block(
            "automated_release_signing is enabled but release-build.md sets reproducibility_binaries to "
            f"{build.reproducibility_binaries!r} with convenience binaries in expected_artefacts; it must be `byte-identical`"
        )


def _render(value: Any, version: str | None, rc: str | None = None) -> Any:
    if not isinstance(value, str) or version is None:
        return value
    out = value
    if rc:
        for spelling in ("<version>-<rcN>", "<version>-rc<N>", "<version>-rcN"):
            out = out.replace(spelling, f"{version}-{rc}")
        out = out.replace("<rcN>", rc).replace("rc<N>", rc)
    return out.replace("<version>", version)


# --------------------------------------------------------------------------- per skill


def check_rc_cut(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version = _source_version(result, args)
    rc_raw = _positional(args, 1)
    rc = rc_raw if rc_raw and versions.RC.match(rc_raw) else None
    if rc_raw is None:
        result.block(f"RC suffix missing; expected {versions.RC_SHAPE}")
    elif rc is None:
        result.block(f"RC suffix {rc_raw!r} does not match {versions.RC_SHAPE}")
    build = cfg.build
    if _require_file(result, cfg, BUILD):
        if not build.build_command_declared:
            result.block("release-build.md declares no build_command (no `build_command` key and no § Build invocation)")
        if not build.expected_artefacts:
            result.block("release-build.md lists no expected_artefacts (§ Expected artefact list is empty or still TODO)")
        if not build.digest_set:
            result.block("release-build.md declares no digest_set (§ Digest set is empty or still TODO)")
        else:
            if "sha512" not in build.digest_set:
                result.block(f"digest_set {build.digest_set} does not contain sha512")
            for weak in ("md5", "sha1"):
                if weak in build.digest_set:
                    result.block(f"digest_set contains {weak}, which is not accepted")
    _require_keys(result, cfg, ("release_dist_backend", "release_dist_url_template"))
    if build.source_archive_method == "custom":
        archive_reviewed = True
    else:
        archive_reviewed = build.value("export_ignore_reviewed") is not None
        if not archive_reviewed:
            if args.allow_unreviewed_archive:
                result.warn(
                    "export_ignore_reviewed is unset; proceeding under --allow-unreviewed-archive — record the override in the Step 4 planning-issue comment"
                )
            elif build.found:
                result.block(
                    "export_ignore_reviewed is unset in release-build.md § Source archive (archive_reviewed: false): "
                    f"run `release-prepare prep {version or '<version>'}` — its Step 2f walks you through what ships in the source archive "
                    "and lands `.gitattributes` in the prep PR"
                )
    _signing_consistency(result, cfg)
    _convenience_versions(result, cfg, version, rc)
    if build.template_example_skipped:
        result.warn("release-build.md § Convenience artefacts still holds the template example entry (name contains `<project>`); ignored")
    result.values.update(
        {
            "version": version,
            "rc_number": rc,
            "archive_reviewed": archive_reviewed,
            "allow_unreviewed_archive": bool(args.allow_unreviewed_archive),
            "signing_mode": cfg.signing_mode,
            "staging_url": _staging_url(cfg, version, rc),
            "rc_tag": f"{version}-{rc}" if version and rc else None,
        }
    )


def check_vote_draft(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version, rc = _source_rc_id(result, args)
    _require_keys(result, cfg, ("vote_window_hours", "vote_dev_list"))
    window: int | None = None
    if cfg.present("vote_window_hours"):
        try:
            window = int(str(cfg.raw["vote_window_hours"]).strip())
        except ValueError:
            result.block(f"vote_window_hours {cfg.raw['vote_window_hours']!r} is not a whole number of hours")
    if window is not None and window < 72:
        if args.expedited:
            result.warn(f"vote_window_hours ({window}) is below the 72-hour floor; proceeding under --expedited: {args.expedited}")
        else:
            result.block(
                f"vote_window_hours ({window}) is below the ASF 72-hour floor. Pass --expedited <reason> to proceed with an "
                "abbreviated window, or raise vote_window_hours to at least 72 in release-management-config.md."
            )
    result.values.update(
        {
            "version": version,
            "rc_number": rc,
            "vote_window_hours": window,
            "skip_verify_override": bool(args.skip_verify_check),
            "expedited": bool(args.expedited),
        }
    )


def check_vote_tally(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version, rc = _source_rc_id(result, args)
    _require_keys(result, cfg, ("release_approval_mechanism", "result_subject_template"))
    mechanism = cfg.raw.get("release_approval_mechanism")
    if cfg.is_asf and mechanism and mechanism != "dev-list-vote":
        result.block(f"an ASF project (project.md → organization: ASF) requires release_approval_mechanism=dev-list-vote; config has {mechanism}")
    if cfg.sources.get(RMC) is not None:
        _roster(result, cfg)
    window_key = "vote_window_hours" if (mechanism or "dev-list-vote") == "dev-list-vote" else "approval_window_hours"
    window_raw = cfg.raw.get(window_key)
    window: int | None = None
    try:
        window = int(str(window_raw)) if window_raw not in (None, "") else None
    except ValueError:
        result.block(f"{window_key} {window_raw!r} is not a whole number of hours")
    elapsed: float | None = None
    closes: str | None = None
    if args.vote_opened and window is not None:
        opened = parse_time(args.vote_opened)
        elapsed = round((_now(args) - opened).total_seconds() / 3600, 2)
        closes = iso(opened + timedelta(hours=window))
    if args.force_close:
        result.warn(f"vote window check overridden with --force-close: {args.force_close}")
    elif window is None:
        result.block(f"{window_key} is not set, so the approval window cannot be checked")
    elif elapsed is None:
        result.block("vote opening time unknown: pass --vote-opened <ISO-8601> from the planning issue, or --force-close <reason>")
    elif elapsed < window:
        result.block(f"vote window has not elapsed: {elapsed:g} hours elapsed of {window}-hour window (closes {closes})")
    result.values.update(
        {
            "version": version,
            "rc_number": rc,
            "force_close": bool(args.force_close),
            "mechanism": mechanism,
            "is_asf": cfg.is_asf,
            "window_hours": window,
            "elapsed_hours": elapsed,
            "window_closes_utc": closes,
        }
    )


def check_announce_draft(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version = _source_version(result, args)
    _require_keys(result, cfg, ("announce_list", "announce_subject_template"))
    backend = cfg.raw.get("release_announce_backend")
    if backend == "announce-list" and cfg.non_asf:
        result.block(
            f"release_announce_backend is announce-list, which only an ASF project uses; project.md declares organization: {cfg.organization} — "
            "set release_announce_backend to this project's channel"
        )
    elif backend and backend != "announce-list" and cfg.is_asf:
        result.block(
            f"release_announce_backend is {backend}, but an ASF project (project.md → organization: ASF) announces on announce-list — "
            "fix release_announce_backend in release-management-config.md"
        )
    clear_after: str | None = None
    wait_active = False
    if not args.promote_timestamp:
        result.block("promote timestamp unavailable: not in the planning issue body and --promote-timestamp was not passed")
    else:
        clear_after = plus_one_hour(args.promote_timestamp)
        wait_active = _now(args) < parse_time(clear_after)
        if wait_active and args.skip_promote_wait:
            result.warn(f"promote-wait gate (clears {clear_after}) overridden with --skip-promote-wait: {args.skip_promote_wait}")
        elif wait_active:
            minutes = int((parse_time(clear_after) - _now(args)).total_seconds() // 60)
            result.block(
                f"Promote-wait gate: promote commit was at {iso(parse_time(args.promote_timestamp))}; the one-hour gate clears at "
                f"{clear_after} (in ~{minutes} minutes). Pass --skip-promote-wait <reason> to override."
            )
    download = args.download_page or cfg.raw.get("download_page_url")
    if not download:
        result.block("Download Page URL unavailable: not in the planning issue body, not in the config, and --download-page was not passed")
    only_wait = wait_active and not args.skip_promote_wait and len(result.blockers) == 1
    result.values.update(
        {
            "version": version,
            "skip_promote_wait_override": bool(args.skip_promote_wait),
            "non_asf": cfg.non_asf,
            "promote_clear_after_utc": clear_after if only_wait else None,
            "promote_wait_active": wait_active,
            "download_page_url": download,
            "release_announce_backend": backend,
        }
    )


def check_promote(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version, rc = _source_rc_id(result, args)
    _require_keys(result, cfg, ("release_dist_backend", "release_dist_url_template"))
    rm_is_pmc: bool | None = None
    if cfg.is_asf:
        identity = args.rm or _user_value(cfg, "apache_id") or _user_value(cfg, "release_manager.apache_id")
        roster_ref = cfg.approver_roster_path
        roster_path = cfg.resolver.resolve_ref(roster_ref)
        roster = md.parse_roster(roster_path)
        result.values["roster_path"] = cfg.resolver.display(roster_path) if roster_path else roster_ref
        if identity is None:
            result.block("RM identity unknown for the PMC gate: pass --rm <apache-id|email|github-handle> (or set apache_id in user.md)")
        elif roster is None:
            rm_is_pmc = False
            result.warn(f"approver roster {roster_ref!r} (release_approver_roster_path) not found; treating the RM as not on the roster (hand-off)")
        else:
            rm_is_pmc = roster.contains(identity)
        result.values["rm_identity"] = identity
    _convenience_versions(result, cfg, version, rc)
    trusted = cfg.signing_mode == "ci-automated"
    result.values.update(
        {
            "version": version,
            "rc": rc,
            "non_asf": cfg.non_asf,
            "rm_is_pmc": True if cfg.non_asf else rm_is_pmc,
            "dist_backend": cfg.raw.get("release_dist_backend"),
            "staging_url": _staging_url(cfg, version, rc),
            "target_url": _target_url(cfg, version),
            "trusted_hardware_attestation_required": trusted,
            "handoff_non_pmc": rm_is_pmc is False and cfg.is_asf,
        }
    )


def check_verify_rc(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version, rc = _source_rc_id(result, args)
    _require_keys(result, cfg, ("keys_file_url", "release_dist_url_template", "version_manifest_files"))
    if _require_file(result, cfg, BUILD):
        labels = {
            "expected_artefacts": "§ Expected artefact list",
            "digest_set": "§ Digest set",
            "binary_exclude": "§ Binary-exclude list",
            "rat_configuration": "§ Apache RAT configuration",
        }
        for key, label in labels.items():
            if not cfg.build.sections.get(key):
                result.block(f"release-build.md is missing the required section {label}")
    staging = _staging_url(cfg, version, rc)
    if cfg.present("release_dist_url_template") and version and not _well_formed(staging):
        result.block(f"staging URL derived from release_dist_url_template is not well-formed: {staging!r}")
        staging = None
    _convenience_versions(result, cfg, version, rc)
    result.values.update(
        {
            "rc_tag": f"{version}-{rc}" if version and rc else _positional(args, 0),
            "staging_url": staging,
            "keyserver": cfg.get("keyserver"),
            "post_to": args.post_to,
        }
    )


def check_archive_sweep(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    _require_keys(result, cfg, ("archive_retention_rule", "release_dist_backend", "release_dist_url_template"))
    lines: list[str] = []
    if _require_file(result, cfg, TRAINS):
        lines = cfg.release_lines()
        if not lines:
            result.block("release-trains.md lists no release line under § Release branches currently in flight (empty or still TODO)")
    backend = cfg.raw.get("release_dist_backend")
    if backend and backend not in DIST_BACKENDS:
        result.block(f"release_dist_backend {backend!r} is not one of {', '.join(DIST_BACKENDS)}")
    archive_url = cfg.raw.get("archive_url_template")
    if not archive_url and backend in ASF_DIST_BACKENDS:
        project = cfg.raw.get("project_dist_name")
        archive_url = ASF_ARCHIVE_DEFAULT.replace("<project>", str(project)) if project else None
        if archive_url is None:
            result.block(f"archive destination for {backend} cannot be derived: neither archive_url_template nor project_dist_name is set")
    elif not archive_url and backend in DIST_BACKENDS:
        result.block(f"archive destination for {backend} backend is not configured (archive_url_template missing)")
    result.values.update(
        {
            "non_asf": cfg.non_asf,
            "dist_backend": backend,
            "archive_url": archive_url,
            "release_lines": lines,
        }
    )


def check_audit_report(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    version = _source_version(result, args)
    _require_keys(result, cfg, ("audit_log_path",))
    if cfg.sources.get(RMC) is not None:
        _roster(result, cfg)
    result.values.update({"version": version, "audit_log_path": cfg.raw.get("audit_log_path") or None})


def check_keys_sync(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    fingerprint: str | None = None
    source = None
    candidates = (
        ("--fingerprint", args.fingerprint),
        ("release-management-config.md rm_key_fingerprint", cfg.raw.get("rm_key_fingerprint")),
        ("user.md release_manager.gpg_fingerprint", _user_value(cfg, "release_manager.gpg_fingerprint")),
    )
    for label, value in candidates:
        if isinstance(value, str) and value.strip() and not md.is_placeholder(value):
            fingerprint, source = re.sub(r"\s+", "", value).upper(), label
            break
    if fingerprint is None:
        result.block("no RM key fingerprint resolvable: set rm_key_fingerprint, user.md release_manager.gpg_fingerprint, or pass --fingerprint")
    elif not FINGERPRINT.match(fingerprint):
        result.warn(f"fingerprint {fingerprint!r} is not 40 hex characters")
    keys_url = args.keys_url or cfg.raw.get("keys_file_url")
    if not keys_url:
        result.block("keys_file_url not resolvable: set it in release-management-config.md § Signing or pass --keys-url")
    keyserver = args.keyserver or cfg.get("keyserver")
    result.values.update({"fingerprint": fingerprint, "fingerprint_source": source, "keys_file_url": keys_url, "keyserver": keyserver})


def check_prepare(cfg: Loaded, args: argparse.Namespace, result: Result) -> None:
    first = _positional(args, 0)
    sub = {"prep": "prep", "post": "post", "automated-signing": "automated-signing"}.get(first or "", "plan")
    version: str | None = None
    if first is None:
        result.block("no sub-command or version given; expected `<version>`, `prep <version>`, `post <version>`, or `automated-signing`")
    elif sub == "automated-signing":
        if not cfg.automated_signing_offered:
            result.block(
                f"automated release signing is not offered by this project's organization ({cfg.organization}): "
                f"release_process.automated_signing is unset or null ({cfg.automated_signing_source})"
            )
    else:
        version = _source_version(result, args, 0 if sub == "plan" else 1)
    _require_keys(result, cfg, ("release_branch_base", "version_manifest_files"))
    lines: list[str] = []
    if _require_file(result, cfg, TRAINS):
        lines = cfg.release_lines()
    result.values.update(
        {
            "sub_command": sub,
            "version": version,
            "release_branch_base": args.release_branch or cfg.raw.get("release_branch_base"),
            "previous_tag": args.previous_tag,
            "release_lines": lines,
            "organization": cfg.organization,
            "automated_signing_offered": cfg.automated_signing_offered,
        }
    )


CHECKS: dict[str, Callable[[Loaded, argparse.Namespace, Result], None]] = {
    "rc-cut": check_rc_cut,
    "vote-draft": check_vote_draft,
    "vote-tally": check_vote_tally,
    "announce-draft": check_announce_draft,
    "promote": check_promote,
    "verify-rc": check_verify_rc,
    "archive-sweep": check_archive_sweep,
    "audit-report": check_audit_report,
    "keys-sync": check_keys_sync,
    "prepare": check_prepare,
}


def preflight(skill: str, cfg: Loaded, args: argparse.Namespace) -> dict[str, Any]:
    result = Result(skill)
    CHECKS[skill](cfg, args, result)
    return result.as_dict()


# --------------------------------------------------------------------------- load


def _convenience_split(cfg: Loaded, version: str | None, verify: list[str]) -> dict[str, list[dict[str, Any]]]:
    """promote Step 2: which convenience artefacts publish and which are held.

    `--verify-binary NAME=STATUS` carries the verify-rc Step 9 result from the
    planning issue: `identical` or `warn` (every difference documented) publish;
    `differs` or no entry hold.
    """
    statuses: dict[str, str] = {}
    for item in verify:
        name, _, status = item.partition("=")
        statuses[_render(name.strip(), version)] = status.strip().lower()
    publish: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for entry in cfg.build.convenience_artefacts:
        own = versions.artefact_version(entry, version)
        name = _render(str(entry.get("name")), own)
        channel = entry.get("publish_channel") or "dist-release"
        verify_status = statuses.get(name) or statuses.get(_render(str(entry.get("name")), version))
        if verify_status in ("identical", "warn", "pass"):
            command = None if channel == "dist-release" else _render(entry.get("publish_command"), own)
            publish.append({"name": name, "publish_channel": channel, "publish_command": command})
        else:
            held.append({"name": name, "reason": "differs" if verify_status == "differs" else "not checked"})
    return {"publish": publish, "held": held}


def metadata(skill: str | None, cfg: Loaded, args: argparse.Namespace) -> dict[str, Any]:
    """The config-derived Step 1 fields of a skill, named as its Step 1 table names them."""
    if skill is None:
        return {}
    build = cfg.build
    version: str | None = None
    rc: str | None = None
    if skill == "rc-cut":
        version, rc = _positional(args, 0), _positional(args, 1)
    elif skill in ("vote-draft", "vote-tally", "promote", "verify-rc"):
        match = versions.SOURCE_RC_ID.match(_positional(args, 0) or "")
        version, rc = (match.group("version"), match.group("rc")) if match else (None, None)
    elif skill in ("announce-draft", "audit-report"):
        version = _positional(args, 0)
    fingerprint = cfg.raw.get("rm_key_fingerprint")
    if not isinstance(fingerprint, str) or md.is_placeholder(fingerprint):
        fingerprint = _user_value(cfg, "release_manager.gpg_fingerprint")
    common = {"version": version, "signing_mode": cfg.signing_mode, "convenience_artefacts": build.convenience_artefacts}
    if skill == "rc-cut":
        return common | {
            "rc_number": rc,
            "build_command": build.build_command,
            "expected_artefacts": [_render(a["name"], version, rc) for a in build.expected_artefacts],
            "digest_set": build.digest_set,
            "backend": cfg.raw.get("release_dist_backend"),
            "vote_backend": cfg.get("release_vote_backend"),
            "staging_url": _staging_url(cfg, version, rc),
            "signing_key_fingerprint": fingerprint or "",
            "release_branch": args.release_branch or cfg.raw.get("release_branch_base"),
            "git_upstream_remote": args.remote or cfg.get("git_upstream_remote"),
            "source_archive_method": build.source_archive_method,
            "source_archive_format": build.as_dict()["source_archive_format"],
            "source_archive_prefix": _render(build.value("source_archive_prefix"), version),
            "reproducibility_source": build.reproducibility_source,
            "reproducibility_binaries": build.reproducibility_binaries,
        }
    if skill == "vote-draft":
        return common | {
            "rc_number": rc,
            "keys_url": cfg.raw.get("keys_file_url"),
            "vote_list": cfg.raw.get("vote_dev_list"),
            "vote_window_hours": cfg.raw.get("vote_window_hours"),
            "subject_template": cfg.raw.get("vote_subject_template"),
            "vote_backend": cfg.get("release_vote_backend"),
            "atr_platform_url": cfg.raw.get("atr_platform_url") if cfg.get("release_vote_backend") == "atr" else None,
            "verification_doc_url": _render(cfg.raw.get("vote_verification_doc_url"), version, rc),
            "reproducibility_doc_url": _render(cfg.raw.get("reproducibility_doc_url"), version, rc),
            "verification_skill": cfg.get("vote_verification_skill"),
            "staging_url": _staging_url(cfg, version, rc),
        }
    if skill == "announce-draft":
        clear = plus_one_hour(args.promote_timestamp) if args.promote_timestamp else None
        return common | {
            "promote_timestamp": iso(parse_time(args.promote_timestamp)) if args.promote_timestamp else None,
            "promote_clear_after_utc": clear,
            "keys_url": cfg.raw.get("keys_file_url"),
            "announce_list": cfg.raw.get("announce_list"),
            "announce_cc_lists": cfg.raw.get("announce_cc_lists") or [],
            "subject_template": cfg.raw.get("announce_subject_template"),
            "site_repo": cfg.raw.get("site_repo"),
            "site_pr_files": [_render(f, version) for f in cfg.raw.get("site_pr_files") or []],
            "release_announce_backend": cfg.raw.get("release_announce_backend"),
            "dist_release_url": _target_url(cfg, version),
        }
    if skill == "promote":
        return common | {
            "rc": rc,
            "dist_backend": cfg.raw.get("release_dist_backend"),
            "dist_url_template": cfg.raw.get("release_dist_url_template"),
            "staging_url": _staging_url(cfg, version, rc),
            "target_url": _target_url(cfg, version),
            "promote_command_template": cfg.raw.get("release_publish_command_template"),
            "rm_gpg_fingerprint": _user_value(cfg, "release_manager.gpg_fingerprint"),
            "git_upstream_remote": cfg.get("git_upstream_remote"),
            "convenience": _convenience_split(cfg, version, args.verify_binary or []),
        }
    return common | {"rc": rc, "staging_url": _staging_url(cfg, version, rc), "target_url": _target_url(cfg, version)}
