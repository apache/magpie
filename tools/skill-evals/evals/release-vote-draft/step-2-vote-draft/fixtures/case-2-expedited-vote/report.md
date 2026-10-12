<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (--expedited accepted)
product_name: Apache Airflow
version: 2.10.4
rc_number: rc1
staging_url: https://dist.apache.org/repos/dist/dev/airflow/2.10.4-rc1/
tag_url: https://github.com/apache/airflow/releases/tag/2.10.4-rc1
keys_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
changelog_url: https://github.com/apache/airflow/blob/2.10.4-rc1/CHANGELOG.md
vote_list: dev@airflow.apache.org
vote_window_hours: 48
subject_template: "[VOTE] Release Apache Airflow <version> from <version>-<rcN>"
canned_body: none
expedited: true
expedited_reason: "Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair."
skip_verify_logged: false
repro_record: commit a1b2c3d4e5f60718293a4b5c6d7e8f9012345678, SOURCE_DATE_EPOCH 1758400000, sha512 77ab…10 (apache_airflow-2.10.4.tar.gz)
verification_doc_url: https://github.com/apache/airflow/blob/2.10.4-rc1/docs/verifying-a-release-candidate.md
reproducibility_doc_url: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md
verification_skill: magpie-release-management:verify-rc
vote_backend: manual
signing_mode: rm-key
repro_record (cont.): repository https://github.com/apache/airflow; swhid_dir swh:1:dir:9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c;origin=https://github.com/apache/airflow;anchor=swh:1:rev:a1b2c3d4e5f60718293a4b5c6d7e8f9012345678

`release-management vote-draft render --step 2 --load <scratch>/vote-draft-load.json --product-name "Apache Airflow" --tag-url https://github.com/apache/airflow/releases/tag/2.10.4-rc1 --changelog-url https://github.com/apache/airflow/blob/2.10.4-rc1/CHANGELOG.md --repository … --commit … --swhid … --epoch … --sha512 … --expedited "Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair."` output (rendered with the reason exactly as the RM typed it):

```json
{
  "ok": true,
  "step": "2",
  "subject": "[VOTE] Release Apache Airflow 2.10.4 from 2.10.4-rc1",
  "body": "To: dev@airflow.apache.org\nSubject: [VOTE] Release Apache Airflow 2.10.4 from 2.10.4-rc1\n\nHi all,\n\nI propose we release the following artifacts as Apache Airflow 2.10.4.\n\nThe release artifacts, signatures, and checksums are available at:\n  https://dist.apache.org/repos/dist/dev/airflow/2.10.4-rc1/\n\nThe release tag to be voted upon:\n  https://github.com/apache/airflow/releases/tag/2.10.4-rc1\n\nThe changelog for this release:\n  https://github.com/apache/airflow/blob/2.10.4-rc1/CHANGELOG.md\n\nKeys to verify artifact signatures:\n  https://dist.apache.org/repos/dist/release/airflow/KEYS\n\nHow to verify this candidate before voting\n------------------------------------------\nReproducibility record (from the planning issue):\n  repository:        https://github.com/apache/airflow\n  source commit:     a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n  SWHID (content):   swh:1:dir:9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c;origin=https://github.com/apache/airflow;anchor=swh:1:rev:a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n  SOURCE_DATE_EPOCH: 1758400000\n  sha512:            77ab…10 (apache_airflow-2.10.4.tar.gz)\n\nAgentic path (any agent with the Magpie release skills, read-only):\n  /magpie-release-management:verify-rc 2.10.4-rc1\n  It checks the signature against KEYS, the checksum, licence headers\n  (RAT), LICENSE/NOTICE, prohibited binaries, dangling links, version\n  strings, rebuilds the source artefact from the tag to confirm it is\n  byte-identical to what is staged and that its SWHID is the recorded\n  one, and rebuilds and compares every convenience artefact.\n\nManual path (the same checks, longhand):\n  https://github.com/apache/airflow/blob/2.10.4-rc1/docs/verifying-a-release-candidate.md\n  Reproducibility background: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md\n\nA binding +1 means you downloaded the artefact, verified it, and built\nand tested it on your own hardware; the tools above are an aid, not a\nsubstitute (https://www.apache.org/legal/release-policy.html#release-approval).\n\nPlease vote to release:\n  [ ] +1  Release Apache Airflow 2.10.4\n  [ ] +0\n  [ ] -1  Do not release (please comment with specific reasons)\n\nThis vote is open for at least 48 hours.\n\n[EXPEDITED: Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair. ASF policy requires this deviation to be noted in the project's next board report.]\n\nThanks,\n<RM name>",
  "vote_window_hours": 48,
  "vote_backend": "manual",
  "atr_vote_command": "",
  "expedited": true,
  "skip_verify_logged": false,
  "verify_section_appended": false,
  "warnings": [
    "the --expedited reason names 'CVE-2026-12345', 'security': the [VOTE] thread and the planning issue are public, so reword it neutrally (e.g. 'Time-sensitive fix release'), keep any approval the RM cited, tell the RM what was left out, and render again"
  ],
  "text": "Subject: [VOTE] Release Apache Airflow 2.10.4 from 2.10.4-rc1\n\nTo: dev@airflow.apache.org\nSubject: [VOTE] Release Apache Airflow 2.10.4 from 2.10.4-rc1\n\nHi all,\n\nI propose we release the following artifacts as Apache Airflow 2.10.4.\n\nThe release artifacts, signatures, and checksums are available at:\n  https://dist.apache.org/repos/dist/dev/airflow/2.10.4-rc1/\n\nThe release tag to be voted upon:\n  https://github.com/apache/airflow/releases/tag/2.10.4-rc1\n\nThe changelog for this release:\n  https://github.com/apache/airflow/blob/2.10.4-rc1/CHANGELOG.md\n\nKeys to verify artifact signatures:\n  https://dist.apache.org/repos/dist/release/airflow/KEYS\n\nHow to verify this candidate before voting\n------------------------------------------\nReproducibility record (from the planning issue):\n  repository:        https://github.com/apache/airflow\n  source commit:     a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n  SWHID (content):   swh:1:dir:9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c;origin=https://github.com/apache/airflow;anchor=swh:1:rev:a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n  SOURCE_DATE_EPOCH: 1758400000\n  sha512:            77ab…10 (apache_airflow-2.10.4.tar.gz)\n\nAgentic path (any agent with the Magpie release skills, read-only):\n  /magpie-release-management:verify-rc 2.10.4-rc1\n  It checks the signature against KEYS, the checksum, licence headers\n  (RAT), LICENSE/NOTICE, prohibited binaries, dangling links, version\n  strings, rebuilds the source artefact from the tag to confirm it is\n  byte-identical to what is staged and that its SWHID is the recorded\n  one, and rebuilds and compares every convenience artefact.\n\nManual path (the same checks, longhand):\n  https://github.com/apache/airflow/blob/2.10.4-rc1/docs/verifying-a-release-candidate.md\n  Reproducibility background: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md\n\nA binding +1 means you downloaded the artefact, verified it, and built\nand tested it on your own hardware; the tools above are an aid, not a\nsubstitute (https://www.apache.org/legal/release-policy.html#release-approval).\n\nPlease vote to release:\n  [ ] +1  Release Apache Airflow 2.10.4\n  [ ] +0\n  [ ] -1  Do not release (please comment with specific reasons)\n\nThis vote is open for at least 48 hours.\n\n[EXPEDITED: Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair. ASF policy requires this deviation to be noted in the project's next board report.]\n\nThanks,\n<RM name>"
}
```
