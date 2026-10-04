<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: plan. Version: 2.11.0.
Previous tag: 2.10.3. Release branch base: main.
--skip-empty-check was NOT passed.

Merged PR set since 2.10.3 on apache/airflow main branch: 0 PRs.
(No PRs were merged between tag 2.10.3 and the current HEAD of main.)

Tags on apache/airflow (`git ls-remote --tags`): 2.9.3, 2.10.0, 2.10.1, 2.10.2, 2.10.3.

Output of `python3 <skill-dir>/scripts/prev_tag.py --tags tags.txt --version 2.11.0 --train 2.x`:

```json
{
  "version": "2.11.0",
  "train": "2.x",
  "previous_tag": "2.10.3",
  "candidates_in_train": [
    "2.9.3",
    "2.10.0",
    "2.10.1",
    "2.10.2",
    "2.10.3"
  ],
  "skipped_prerelease_tags": []
}
```
