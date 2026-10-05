<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1031`. ASF Nexus credentials are available.

Existence check (anonymous):

```text
curl -fsS -o /dev/null -w '%{http_code}
'   "https://repository.apache.org/content/repositories/orgapachefoo-1031/"
→ HTTP 404 Not Found
```

Staging repository details (authenticated):

```text
curl --netrc-file ... "https://repository.apache.org/service/local/staging/repository/orgapachefoo-1031"
→ HTTP 404 Not Found
```

Things to classify here:

- Both paths answer `404`: the repository does not exist at the id
  recorded for this RC (wrong id, already promoted, or never
  deployed). A hard `FAIL`, worded factually — never guessed into a
  pass, and never conflated with an `open` repository (that one says
  "something editable there"; this one says "nothing there").
- The jar surface the vote is supposed to cover is unreachable, so
  no `.asc` / companion checks can run — there is nothing to check
  them against.
