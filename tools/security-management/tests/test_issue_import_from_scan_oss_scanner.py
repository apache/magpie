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
"""`issue-import-from-scan parse-email`: the Anthropic OSS Scanner disclosure email as a scan folder.

The fixture is synthetic and follows the real layout, including the hard
line wrapping a mail client applies to the INDEX and `Location:` lines.
"""

from __future__ import annotations

import json
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main
from security_management.issue_import_from_scan import oss_scanner

HASHES = "#" * 76
FENCE = "=" * 76

BODY = f"""Hello,

Below are the results of an automated security scan of
gh:example/widget@main at commit
0123456789ab. This is the result of Anthropic's OSS Scanner.

This scan produced 3 findings: 1 rated high and 2 rated medium or low.

Separately, the scan came across 2 ordinary bugs that are NOT security issues.

THE ATTACHMENT IS ENCRYPTED

  The attachment is encrypted
(widget-20260101-001-findings.tar.gz.gpg). That is the only reason.

INDEX

  HIGH (1)
    ANT-2026-AAAAAAA1 Token endpoint accepts a NUL password
(src/widget/auth.py:42)

  MEDIUM (1)
    ANT-2026-BBBBBBB2 Config API echoes a secret (widget/provider.yaml:7)

  LOW (1)
    ANT-2026-CCCCCCC3 Log line keeps a quoted password
(src/widget/log.py:9)

IF YOU FIX ONE OF THESE

  A line in the commit message, please.

{HASHES}
HIGH: 1 FINDING
{HASHES}

{FENCE}
ANT-2026-AAAAAAA1  [high]  CWE-287  authz
Token endpoint accepts a NUL password
Location: src/widget/auth.py:42 in
Auth.create_token()
Commit:   0123456789abcdef0123456789abcdef01234567
{FENCE}

An unauthenticated client gets a token for any account without a local
password by sending the password "\\x00".

Proposed fixes:
  high/ANT-2026-AAAAAAA1/patches/1.patch — src/widget/auth.py

{HASHES}
MEDIUM: 1 FINDING
{HASHES}

{FENCE}
ANT-2026-BBBBBBB2 [medium] CWE-201 info-leak
Config API echoes a secret
Location: widget/provider.yaml:7
Commit:   0123456789abcdef0123456789abcdef01234567
{FENCE}

With expose_config on, an Op user reads the secret.

Patch: our agents did not produce a fix that passed our checks for this finding.

{HASHES}
LOW: 1 FINDING
{HASHES}

{FENCE}
ANT-2026-CCCCCCC3  [low]  CWE-532  info-leak
Log line keeps a quoted password
Location: src/widget/log.py:9 in mask()
Commit:   0123456789abcdef0123456789abcdef01234567
{FENCE}

A task author already holds the password.

{HASHES}
NOT SECURITY: 2 ORDINARY BUGS
{HASHES}

  ANT-2026-DDDDDDD4 Audit log skips clears (see dry_run)
(src/widget/audit.py:3)
  ANT-2026-EEEEEEE5 Logout is a GET (src/widget/logout.py:5)

--
oss-scanner
"""


def run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["issue-import-from-scan", *argv])
    return code, json.loads(capsys.readouterr().out)


def eml(tmp_path: Path, body: str = BODY) -> Path:
    msg = EmailMessage()
    msg["Subject"] = "[Anthropic OSS Scanner] Disclosing 3 security vulnerabilities in widget"
    msg["From"] = "oss-scanner via security <security@widget.example>"
    msg["Message-ID"] = "<scan@example>"
    msg.set_content(body, cte="quoted-printable")
    msg.add_attachment(
        b"\x8c\r\x04", maintype="application", subtype="octet-stream", filename="widget-findings.tar.gz.gpg"
    )
    path = tmp_path / "scan.eml"
    path.write_bytes(bytes(msg))
    return path


def test_parse_email_writes_a_complete_scan_folder(capsys, tmp_path) -> None:
    out = tmp_path / "scan"
    code, summary = run(capsys, "parse-email", "--source", str(eml(tmp_path)), "--out-dir", str(out))
    assert code == 0
    assert summary["checks"] == {"complete": True, "problems": []}
    assert summary["findings"] == 3 and summary["not_security"] == 2
    assert summary["by_severity"] == {"Critical": 0, "High": 1, "Medium": 1, "Low": 1}
    assert summary["scan"]["target"] == "gh:example/widget@main"
    assert summary["scan"]["commit"] == "0123456789ab"
    assert summary["scan"]["archive"] == "widget-20260101-001-findings.tar.gz.gpg"
    assert "evidence" not in json.dumps(summary)  # the summary never carries finding text
    assert oss_scanner.detect(out) == oss_scanner.FORMAT

    index = json.loads((out / "index.json").read_text())
    assert index["email"]["attachments"] == ["widget-findings.tar.gz.gpg"]
    first = index["findings"][0]
    assert first["id"] == "ANT-2026-AAAAAAA1"
    assert first["title"] == "Token endpoint accepts a NUL password"
    assert first["cwe"] == ["CWE-287"] and first["category"] == "authz"
    assert first["files"] == ["src/widget/auth.py:42"]
    assert first["function"] == "Auth.create_token()"  # re-joined across the wrap
    assert first["remediation"] == ["high/ANT-2026-AAAAAAA1/patches/1.patch"]
    evidence = Path(first["evidence_file"]).read_text()
    assert "Location: src/widget/auth.py:42 in Auth.create_token()" in evidence
    assert 'password "\\x00"' in evidence
    yaml_finding = index["findings"][1]
    assert yaml_finding["function"] is None and yaml_finding["remediation"] == []
    assert [b["id"] for b in index["not_security"]] == ["ANT-2026-DDDDDDD4", "ANT-2026-EEEEEEE5"]
    assert index["not_security"][0]["title"] == "Audit log skips clears (see dry_run)"


def test_a_truncated_email_fails_the_completeness_check(capsys, tmp_path) -> None:
    cut = BODY[: BODY.index("ANT-2026-CCCCCCC3  [low]")]
    source = tmp_path / "body.txt"
    source.write_text(cut)
    _, summary = run(capsys, "parse-email", "--source", str(source), "--out-dir", str(tmp_path / "s"))
    assert summary["checks"]["complete"] is False
    problems = " ".join(summary["checks"]["problems"])
    assert "preamble declares 3 findings, parsed 2" in problems
    assert "only in INDEX ['ANT-2026-CCCCCCC3']" in problems


def test_a_saved_gmail_connector_result_is_read_and_marked_lossy(capsys, tmp_path) -> None:
    saved = tmp_path / "gmail.json"
    saved.write_text(json.dumps({"subject": "s", "plaintextBody": BODY, "attachments": []}))
    _, summary = run(capsys, "parse-email", "--source", str(saved), "--out-dir", str(tmp_path / "s"))
    assert summary["checks"]["complete"] is True
    assert json.loads((tmp_path / "s" / "index.json").read_text())["email"]["lossy"] is True


def test_format_flowed_bodies_are_unflowed(tmp_path) -> None:
    flowed = BODY.replace(
        "Location: src/widget/auth.py:42 in\nAuth", "Location: src/widget/auth.py:42 \nin Auth"
    )
    msg = EmailMessage()
    msg["Subject"] = "s"
    msg.set_content(flowed, params={"format": "flowed"})
    path = tmp_path / "f.eml"
    path.write_bytes(bytes(msg))
    body, _ = oss_scanner.load_body(path)
    finding = oss_scanner.parse(body)["findings"][0]
    assert finding["function"] == "Auth.create_token()"


def test_archive_reports_are_linked_when_decrypted(capsys, tmp_path) -> None:
    archive = tmp_path / "archive"
    (archive / "high" / "ANT-2026-AAAAAAA1").mkdir(parents=True)
    (archive / "high" / "ANT-2026-AAAAAAA1" / "REPORT.md").write_text("full write-up")
    run(
        capsys,
        "parse-email",
        "--source",
        str(eml(tmp_path)),
        "--out-dir",
        str(tmp_path / "s"),
        "--archive-dir",
        str(archive),
    )
    index = json.loads((tmp_path / "s" / "index.json").read_text())
    reports = {f["id"]: f["report_md"] for f in index["findings"]}
    assert reports["ANT-2026-AAAAAAA1"].endswith("high/ANT-2026-AAAAAAA1/REPORT.md")
    assert reports["ANT-2026-BBBBBBB2"] is None


@pytest.mark.parametrize("content", ['{"format": "asvs"}', "[]", "null", "not json"])
def test_detect_ignores_other_folders(tmp_path, content) -> None:
    assert oss_scanner.detect(tmp_path) is None
    (tmp_path / "index.json").write_text(content)
    assert oss_scanner.detect(tmp_path) is None


def test_a_bare_text_body_is_marked_lossy(tmp_path) -> None:
    source = tmp_path / "body.txt"
    source.write_text(BODY)
    _, meta = oss_scanner.load_body(source)
    assert meta["lossy"] is True


def test_attachments_are_saved_byte_exact_with_framing_checked(capsys, tmp_path) -> None:
    # A symmetric-key session packet (old format, tag 3) and a 4-byte data packet (new format, tag 18).
    archive = bytes([0x8C, 0x02, 0x04, 0x07]) + bytes([0xD2, 0x04]) + b"abcd"
    path = eml(tmp_path)
    msg = EmailMessage()
    msg["Subject"] = "s"
    msg.set_content(BODY)
    msg.add_attachment(archive, maintype="application", subtype="octet-stream", filename="../../x.tar.gz.gpg")
    msg.add_attachment(archive[:-1], maintype="application", subtype="octet-stream", filename="x.tar.gz.gpg")
    path.write_bytes(bytes(msg))
    out = tmp_path / "att"
    _, summary = run(
        capsys,
        "parse-email",
        "--source",
        str(path),
        "--out-dir",
        str(tmp_path / "s"),
        "--attachments-dir",
        str(out),
    )
    whole, short = summary["attachments"]
    assert Path(whole["path"]).parent == out  # the sender's ../ is dropped
    assert Path(whole["path"]).read_bytes() == archive and whole["bytes"] == len(archive)
    assert whole["openpgp"] == {"intact": True, "packets": [3, 18], "problem": None}
    assert Path(short["path"]).name == "2-x.tar.gz.gpg"  # no overwrite on a name clash
    assert short["openpgp"]["intact"] is False


def test_a_saved_gmail_connector_result_has_no_attachments_to_save(tmp_path) -> None:
    saved = tmp_path / "gmail.json"
    saved.write_text(json.dumps({"plaintextBody": BODY}))
    try:
        oss_scanner.save_attachments(saved, tmp_path / "att")
    except ValueError as e:
        assert "oauth-draft-fetch-message" in str(e)
    else:
        raise AssertionError("expected a refusal")


@pytest.mark.parametrize(
    ("cut_before", "problem"),
    [
        # Cut right after the last finding's closing header fence: every count still matches.
        ("\nA task author already holds the password.", "ANT-2026-CCCCCCC3: no write-up after its header"),
        # Cut inside the not-security list.
        ("  ANT-2026-EEEEEEE5", "preamble declares 2 ordinary bugs, parsed 1"),
        # Cut before the signature.
        ("--\noss-scanner", "no closing signature"),
    ],
)
def test_a_mail_cut_at_any_section_boundary_is_incomplete(capsys, tmp_path, cut_before, problem) -> None:
    source = tmp_path / "body.txt"
    source.write_text(BODY[: BODY.index(cut_before)])
    _, summary = run(capsys, "parse-email", "--source", str(source), "--out-dir", str(tmp_path / "s"))
    assert summary["checks"]["complete"] is False
    assert problem in " ".join(summary["checks"]["problems"])


def test_delsp_flowed_text_rejoins_a_word_wrapped_mid_token(tmp_path) -> None:
    # RFC 3676 delsp=yes: the trailing space is the soft break, so "pass \nword" is "password".
    flowed = BODY.replace('the password "\\x00"', 'the pass \nword "\\x00"')
    msg = EmailMessage()
    msg["Subject"] = "s"
    msg.set_content(flowed, params={"format": "flowed", "delsp": "yes"})
    path = tmp_path / "f.eml"
    path.write_bytes(bytes(msg))
    body, _ = oss_scanner.load_body(path)
    evidence = oss_scanner.parse(body)["findings"][0]["evidence"]
    assert 'sending the password "\\x00"' in evidence


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        (b"", "empty file"),
        (bytes([0x8C, 0x02, 0x04, 0x07]), "no encrypted-data packet at the end"),
        (bytes([0x8C, 0x02, 0x04, 0x07, 0xD2, 0x04]) + b"ab", "declared 10 bytes, file has 8"),
    ],
)
def test_openpgp_framing_catches_truncation(data, problem) -> None:
    result = oss_scanner.openpgp_framing(data)
    assert result["intact"] is False and result["problem"] == problem


def test_a_mail_missing_its_beginning_is_incomplete(capsys, tmp_path) -> None:
    # Only the last severity section, the ordinary bugs and the signature survive.
    source = tmp_path / "body.txt"
    source.write_text(BODY[BODY.index(f"{HASHES}\nLOW: 1 FINDING") :])
    _, summary = run(capsys, "parse-email", "--source", str(source), "--out-dir", str(tmp_path / "s"))
    assert summary["checks"]["complete"] is False
    problems = " ".join(summary["checks"]["problems"])
    assert "no preamble total" in problems and "no INDEX" in problems


def test_a_second_run_never_overwrites_saved_attachments(tmp_path) -> None:
    path = eml(tmp_path)
    out = tmp_path / "att"
    first = oss_scanner.save_attachments(path, out)
    second = oss_scanner.save_attachments(path, out)
    assert first[0]["path"] != second[0]["path"]
    assert Path(first[0]["path"]).read_bytes() == Path(second[0]["path"]).read_bytes()


def test_a_title_saying_location_is_not_split(capsys, tmp_path) -> None:
    body = BODY.replace(
        "Config API echoes a secret\nLocation:", "Open redirect via Location: header\nLocation:"
    )
    body = body.replace(
        "ANT-2026-BBBBBBB2 Config API echoes a secret", "ANT-2026-BBBBBBB2 Open redirect via Location: header"
    )
    finding = oss_scanner.parse(body)["findings"][1]
    assert finding["title"] == "Open redirect via Location: header"
    assert finding["files"] == ["widget/provider.yaml:7"]


def test_not_security_paths_may_hold_any_character_but_parentheses() -> None:
    body = BODY.replace("(src/widget/logout.py:5)", "(packages/@scope/my widget+x.ts:5)")
    entry = oss_scanner.parse(body)["not_security"][1]
    assert entry["files"] == ["packages/@scope/my widget+x.ts:5"]


def test_every_written_file_is_owner_only(capsys, tmp_path) -> None:
    out, att = tmp_path / "s", tmp_path / "att"
    run(
        capsys,
        "parse-email",
        "--source",
        str(eml(tmp_path)),
        "--out-dir",
        str(out),
        "--attachments-dir",
        str(att),
    )
    written = [*out.rglob("*"), *att.rglob("*")]
    assert written
    for p in written:
        assert p.stat().st_mode & 0o077 == 0, p


def test_a_title_starting_with_location_is_not_the_field() -> None:
    body = BODY.replace(
        "Config API echoes a secret\nLocation:", "Location: header enables open redirects\nLocation:"
    )
    body = body.replace(
        "ANT-2026-BBBBBBB2 Config API echoes a secret",
        "ANT-2026-BBBBBBB2 Location: header enables open redirects",
    )
    finding = oss_scanner.parse(body)["findings"][1]
    assert finding["title"] == "Location: header enables open redirects"
    assert finding["files"] == ["widget/provider.yaml:7"]
    assert finding["cwe"] == ["CWE-201"]


def test_not_security_paths_may_hold_parentheses() -> None:
    body = BODY.replace("(src/widget/logout.py:5)", "(app/(auth)/route.ts:5)")
    parsed = oss_scanner.parse(body)
    assert parsed["checks"]["complete"] is True
    assert parsed["not_security"][1]["files"] == ["app/(auth)/route.ts:5"]


def test_rewriting_an_existing_readable_file_never_widens_it(tmp_path) -> None:
    target = tmp_path / "index.json"
    target.write_text("old")
    target.chmod(0o644)
    oss_scanner._private_write(target, b"secret")
    assert target.read_bytes() == b"secret"
    assert target.stat().st_mode & 0o077 == 0


def test_an_rfc_signature_delimiter_ends_the_last_entry() -> None:
    parsed = oss_scanner.parse(BODY.replace("\n--\noss-scanner", "\n-- \noss-scanner"))
    assert parsed["checks"]["complete"] is True
    assert parsed["not_security"][-1]["files"] == ["src/widget/logout.py:5"]


def test_a_fence_like_line_inside_a_write_up_is_kept_as_evidence() -> None:
    body = BODY.replace(
        "A task author already holds the password.",
        f"A task author already holds the password.\n\n{FENCE}\nTail of the write-up after a fence-like line.",
    )
    parsed = oss_scanner.parse(body)
    assert parsed["checks"]["complete"] is True
    assert "Tail of the write-up after a fence-like line." in parsed["findings"][-1]["evidence"]


def test_a_hash_framed_heading_inside_a_write_up_is_evidence() -> None:
    excerpt = f"{HASHES}\nBUILD NOTES\n{HASHES}\nThe evidence continues after the framed heading."
    body = BODY.replace(
        "A task author already holds the password.", f"A task author already holds the password.\n\n{excerpt}"
    )
    parsed = oss_scanner.parse(body)
    assert parsed["checks"]["complete"] is True
    assert "The evidence continues after the framed heading." in parsed["findings"][-1]["evidence"]


def test_flowed_quotes_join_only_at_the_same_depth() -> None:
    text = "> pass \n> word\n>> deeper \n> shallower"
    assert oss_scanner._unflow(text, delsp=True) == "> password\n>> deeper\n> shallower"
    assert oss_scanner._unflow("plain \nline") == "plain line"


def patch(summary: str, extra: str = "") -> str:
    return f"# src/widget/auth.py\n# {summary}\n#\n# why it works\n{extra}diff --git a/x b/x\n+fixed\n"


def archive_with_patches(tmp_path: Path, patches: dict[str, str]) -> Path:
    archive = tmp_path / "archive"
    folder = archive / "high" / "ANT-2026-AAAAAAA1" / "patches"
    folder.mkdir(parents=True)
    for name, text in patches.items():
        (folder / name).write_text(text)
    return archive


def parse_with_archive(capsys, tmp_path: Path, archive: Path) -> Path:
    run(
        capsys,
        "parse-email",
        "--source",
        str(eml(tmp_path)),
        "--out-dir",
        str(tmp_path / "s"),
        "--archive-dir",
        str(archive),
    )
    return tmp_path / "s" / "index.json"


def render(capsys, tmp_path: Path, index: Path) -> tuple[int, dict[str, Any]]:
    return run(
        capsys,
        "render-patch-comment",
        "--index",
        str(index),
        "--finding",
        "ANT-2026-AAAAAAA1",
        "--out-dir",
        str(tmp_path / "c"),
    )


def test_archive_patches_are_linked_in_numeric_order(capsys, tmp_path) -> None:
    archive = archive_with_patches(tmp_path, {f"{n}.patch": patch(f"fix {n}") for n in (1, 2, 10)})
    index = json.loads(parse_with_archive(capsys, tmp_path, archive).read_text())
    patches = {f["id"]: f["patches"] for f in index["findings"]}
    assert [Path(p).name for p in patches["ANT-2026-AAAAAAA1"]] == ["1.patch", "2.patch", "10.patch"]
    assert patches["ANT-2026-BBBBBBB2"] == []


def test_archive_symlinks_are_never_linked(capsys, tmp_path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("oauth_token: not-for-the-tracker")
    archive = archive_with_patches(tmp_path, {"1.patch": patch("real fix")})
    finding = archive / "high" / "ANT-2026-AAAAAAA1"
    (finding / "patches" / "2.patch").symlink_to(secret)
    (finding / "REPORT.md").symlink_to(secret)
    other = archive / "high" / "ANT-2026-BBBBBBB2"
    other.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "1.patch").write_text(patch("planted"))
    (other / "patches").symlink_to(outside)
    index = json.loads(parse_with_archive(capsys, tmp_path, archive).read_text())
    by_id = {f["id"]: f for f in index["findings"]}
    assert [Path(p).name for p in by_id["ANT-2026-AAAAAAA1"]["patches"]] == ["1.patch"]
    assert by_id["ANT-2026-AAAAAAA1"]["report_md"] is None
    assert by_id["ANT-2026-BBBBBBB2"]["patches"] == []


def test_patch_comment_refuses_a_symlink_at_read_time(tmp_path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("oauth_token: not-for-the-tracker")
    link = tmp_path / "1.patch"
    link.symlink_to(secret)
    with pytest.raises(OSError):
        oss_scanner.render_patch_comments({"id": "ANT-2026-AAAAAAA1", "patches": [str(link)]}, {})


def test_patch_comment_folds_each_candidate(capsys, tmp_path) -> None:
    archive = archive_with_patches(
        tmp_path,
        {"1.patch": patch("Stop rendering @task.bash <args>"), "2.patch": patch("Smaller variant")},
    )
    code, out = render(capsys, tmp_path, parse_with_archive(capsys, tmp_path, archive))
    assert code == 0
    (entry,) = out["bodies"]
    body = Path(entry["path"]).read_text()
    assert body.startswith(
        "<!-- apache-magpie: scan-patches v1 -->\n"
        "**Candidate patches from the security scan — `ANT-2026-AAAAAAA1`**\n"
    )
    assert "against `gh:example/widget@main` at `0123456789ab`" in body
    assert "untested, machine-generated" in body and "public PR" in body
    assert "<details><summary>Candidate 1 — Stop rendering `@task.bash` &lt;args&gt;</summary>" in body
    assert "<details><summary>Candidate 2 — Smaller variant</summary>" in body
    assert body.count("`````diff\n") == 2 and body.count("</details>") == 2
    assert "<details open" not in body


def test_patch_comment_drops_a_target_that_is_not_a_plain_ref(tmp_path) -> None:
    path = tmp_path / "1.patch"
    path.write_text(patch("Fix"))
    finding = {"id": "ANT-2026-AAAAAAA1", "patches": [str(path)]}
    scan = {"target": "x` @someone [link](https://example.com) `", "commit": "0123456789ab"}
    (body,) = oss_scanner.render_patch_comments(finding, scan)
    assert "against `0123456789ab`" in body
    assert "@someone" not in body and "example.com" not in body


def test_patch_fence_outgrows_backticks_in_the_patch() -> None:
    body = oss_scanner._patch_block(patch("Uses fences", "# ``````python\n"), 1)
    assert "```````diff\n" in body


def test_no_patches_means_no_comment() -> None:
    assert oss_scanner.render_patch_comments({"id": "ANT-2026-AAAAAAA1", "patches": []}, {}) == []


def test_patch_comment_refuses_without_archive(capsys, tmp_path) -> None:
    run(capsys, "parse-email", "--source", str(eml(tmp_path)), "--out-dir", str(tmp_path / "s"))
    code, out = render(capsys, tmp_path, tmp_path / "s" / "index.json")
    assert code == 2 and "--archive-dir" in out["refused"]


def test_large_patches_split_across_comments(tmp_path) -> None:
    paths = []
    for n in (1, 2, 3):
        path = tmp_path / f"{n}.patch"
        path.write_text(patch(f"fix {n}", "+x\n" * 300))
        paths.append(str(path))
    finding = {"id": "ANT-2026-AAAAAAA1", "patches": paths}
    bodies = oss_scanner.render_patch_comments(finding, {}, limit=2500)
    assert len(bodies) > 1
    assert all(len(b) <= 2500 for b in bodies)
    assert bodies[0].startswith(
        "<!-- apache-magpie: scan-patches v1 -->\n"
        f"**Candidate patches from the security scan — `ANT-2026-AAAAAAA1`** (part 1 of {len(bodies)})"
    )
    assert "".join(bodies).count("<details>") == 3
    with pytest.raises(ValueError, match="candidate 1"):
        oss_scanner.render_patch_comments(finding, {}, limit=500)
