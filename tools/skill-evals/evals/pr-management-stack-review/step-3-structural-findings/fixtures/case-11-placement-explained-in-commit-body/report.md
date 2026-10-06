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
   "merge_commits": 0
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
   "merge_commits": 0,
   "commit_messages": [
    {
     "headline": "Apply ruff Python 3.11 fixes to dev tooling",
     "body": "Four modules are left out: dev/registry/extract_metadata.py and extract_versions.py keep a tomli fallback whose removal lands in layer 7, so their UTC fixes land there too."
    }
   ]
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
   "merge_commits": 0,
   "commit_messages": [
    {
     "headline": "Require Python 3.11 in all distributions",
     "body": "Also applies the UP017 fixes deferred from layer 5 to the four tomli-fallback modules."
    }
   ]
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
  "7": [
   "dev/registry/extract_metadata.py:283",
   "dev/registry/extract_versions.py:42"
  ]
 }
}
```
Step 4 read both layer-7 outlier hunks: `timezone.utc` → `UTC` rewrites in dev/registry modules, the rule layer 5 is titled for. Layer 7's PR body does not mention them.
