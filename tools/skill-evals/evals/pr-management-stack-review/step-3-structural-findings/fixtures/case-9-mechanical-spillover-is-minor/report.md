<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Layer titles: 1 "Drop Python 3.10 from CI and images"; 2 "Bump inline script metadata"; 3 "Remove Python 3.10 compatibility shims"; 4 "Apply ruff Python 3.11 fixes to core"; 5 "Apply ruff Python 3.11 fixes to dev tooling"; 6 "Update provider READMEs"; 7 "Require Python 3.11 in all distributions".
Per-layer gates: all green, all approved, no unresolved threads.

`stack_chain.py chain`:
```json
{
 "linear": true,
 "behind_trunk_commits": 0,
 "trunk_touches_stack_files": [],
 "layers": [
  {
   "position": 1,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0
  },
  {
   "position": 2,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0
  },
  {
   "position": 3,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0,
   "commit_messages": [
    {
     "headline": "Remove Python 3.10 compatibility shims",
     "body": "Drops the sys.version_info branches and the PY311 markers."
    }
   ]
  },
  {
   "position": 4,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0
  },
  {
   "position": 5,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0
  },
  {
   "position": 6,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0
  },
  {
   "position": 7,
   "contains_below": true,
   "own_commits": 1,
   "merge_commits": 0
  }
 ]
}
```
`stack_chain.py seams`:
```json
{
 "layers": [
  {
   "position": 1,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  },
  {
   "position": 2,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  },
  {
   "position": 3,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  },
  {
   "position": 4,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  },
  {
   "position": 5,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  },
  {
   "position": 6,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  },
  {
   "position": 7,
   "removed_definitions": 0,
   "removed_names": [],
   "hits": {}
  }
 ]
}
```
`stack_ledger.py ledger` (excerpt):
```json
{
 "overlap": {},
 "detectors": {
  "release_note_in_several_layers": [],
  "generated_in_several_layers": [],
  "lock_without_manifest": []
 },
 "layer_outliers": {
  "3": [
   "airflow-core/tests/unit/test_dagbag.py:27",
   "shared/logging/tests/test_structlog.py:24"
  ]
 }
}
```
Step 4 read both layer-3 outlier hunks: they are `timezone.utc` → `UTC` rewrites that ruff's UP017 applies, the kind of hunk layer 4 is titled for. The end state after layer 4 is identical whether they sit in layer 3 or 4; layer 3 stays green on its own and no packaging or runtime behaviour differs. Neither the body nor the commit of layer 3 mentions them.
