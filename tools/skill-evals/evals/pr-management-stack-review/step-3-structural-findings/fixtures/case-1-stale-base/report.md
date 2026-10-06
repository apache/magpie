<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Layer titles: 1 "Drop Python 3.10 from CI and images"; 2 "Bump inline script metadata"; 3 "Remove Python 3.10 compatibility shims"; 4 "Apply ruff Python 3.11 fixes".
Per-layer gates: layer 2 CI red (Static checks); all layers approved; no unresolved threads.

`stack_chain.py chain`:
```json
{
 "linear": false,
 "behind_trunk_commits": 0,
 "trunk_touches_stack_files": [],
 "layers": [
  {
   "position": 1,
   "contains_below": true,
   "own_commits": 2,
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
   "contains_below": false,
   "own_commits": 1,
   "merge_commits": 0
  },
  {
   "position": 4,
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
   "removed_definitions": 2,
   "hits": {}
  },
  {
   "position": 2,
   "removed_definitions": 0,
   "hits": {}
  },
  {
   "position": 3,
   "removed_definitions": 5,
   "hits": {}
  },
  {
   "position": 4,
   "removed_definitions": 0,
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
 }
}
```
