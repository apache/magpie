<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: https://github.com/apache/airflow/issues/45100 (closed)
Title: "Release Apache Airflow 2.10.3"

Planning issue body:
  RC: rc2
  [VOTE] thread: https://lists.apache.org/thread/vote-airflow-2.10.3-rc2
  # [RESULT] thread URL was not recorded on the planning issue
  RC artefacts:
    - apache-airflow-2.10.3.tar.gz  sha512: 112233...  sig: apache-airflow-2.10.3.tar.gz.asc
  # SVN promote revision was not recorded
  # [ANNOUNCE] archive URL was not recorded

pmc-roster.md: entries present but [RESULT] thread is missing so
binding-voter details cannot be extracted.

release-management-config.md:
  audit_log_path: audit-logs/releases
  release_approver_roster_path: projects/airflow/pmc-roster.md

`release-management audit-report gather --load <scratch>/audit-load.json --schema <skill-dir>/audit-record-schema.md --rc rc2` output:

```json
{
  "version": "2.10.3",
  "product_name": "Apache Airflow",
  "mail_archive": "ponymail",
  "permalink_shape": "https://lists.apache.org/thread/<id>",
  "searches": [
    {
      "field": "vote_thread_url",
      "subject": "[VOTE] Release Apache Airflow 2.10.3 from 2.10.3-rc2",
      "query": "[VOTE] Release Apache Airflow 2.10.3 from 2.10.3-rc2",
      "lists": [
        "dev@airflow.apache.org"
      ],
      "archive_urls": [
        "https://lists.apache.org/list.html?dev@airflow.apache.org"
      ]
    },
    {
      "field": "result_thread_url",
      "subject": "[RESULT] [VOTE] Release Apache Airflow 2.10.3 from 2.10.3-rc2",
      "query": "[RESULT] [VOTE] Release Apache Airflow 2.10.3 from 2.10.3-rc2",
      "lists": [
        "dev@airflow.apache.org"
      ],
      "archive_urls": [
        "https://lists.apache.org/list.html?dev@airflow.apache.org"
      ]
    },
    {
      "field": "announce_archive_url",
      "subject": "[ANNOUNCE] Apache Airflow 2.10.3 released",
      "query": "[ANNOUNCE] Apache Airflow 2.10.3 released",
      "lists": [
        "announce@apache.org",
        "dev@airflow.apache.org",
        "users@airflow.apache.org"
      ],
      "archive_urls": [
        "https://lists.apache.org/list.html?announce@apache.org",
        "https://lists.apache.org/list.html?dev@airflow.apache.org",
        "https://lists.apache.org/list.html?users@airflow.apache.org"
      ]
    }
  ],
  "promote_revision": {
    "backend": "svnpubsub",
    "command": "svn info --show-item last-changed-revision https://dist.apache.org/repos/dist/release/airflow/2.10.3/",
    "note": "the revision of the Step 10 `svn mv` commit that created the promoted directory; record it as r<N>"
  },
  "roster_path": "projects/airflow/pmc-roster.md",
  "required_fields": [
    "version",
    "rc_label",
    "vote_thread_url",
    "result_thread_url",
    "artefacts",
    "promote_revision",
    "announce_archive_url",
    "vote_binding_plus1",
    "vote_binding_minus1",
    "binding_voters"
  ]
}
```

`release-management audit-report check --step1 <scratch>/audit-step1.json --schema <skill-dir>/audit-record-schema.md` output (on the fields gathered above):

```json
{
  "fields_missing": [
    "result_thread_url",
    "promote_revision",
    "announce_archive_url",
    "vote_binding_plus1",
    "vote_binding_minus1",
    "binding_voters"
  ],
  "fields_redacted": [],
  "schema_violations": [
    "result_thread_url — required field is MISSING",
    "promote_revision — required field is MISSING",
    "announce_archive_url — required field is MISSING",
    "vote_binding_plus1 — required field is MISSING",
    "vote_binding_minus1 — required field is MISSING",
    "binding_voters — required field is MISSING"
  ],
  "problems": [],
  "input_gaps": []
}
```
