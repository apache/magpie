<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Layer titles: 1 "Rename the HTTP client package to @acme/http"; 2 "Update callers to the new package name"; 3 "Drop the compatibility re-export".
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
     "headline": "Drop the compatibility re-export",
     "body": "Every caller moved in layer 2; the shim had no remaining importers (checked with the seams grep)."
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
   "removed_definitions": 1,
   "removed_names": [
    "createLegacyClient"
   ],
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
Step 4 read all three layers in full: layer 1 renames the package and its imports inside the package, layer 2 updates 41 callers, layer 3 deletes `packages/web/src/legacy.ts` and its re-export. Each body matches its diff and commits.
