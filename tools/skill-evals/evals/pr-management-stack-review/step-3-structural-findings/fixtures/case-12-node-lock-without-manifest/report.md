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
  }
 ]
}
```
`stack_ledger.py ledger` (excerpt):
```json
{
 "overlap": {
  "packages/web/pnpm-lock.yaml": [
   2
  ]
 },
 "detectors": {
  "release_note_in_several_layers": [],
  "generated_in_several_layers": [],
  "lock_without_manifest": [
   {
    "path": "packages/web/pnpm-lock.yaml",
    "layer": 2,
    "manifest_layers": [
     1
    ]
   }
  ]
 }
}
```
Layer 1 renames the package in `packages/web/package.json`; layer 2 carries the regenerated `packages/web/pnpm-lock.yaml` without touching the manifest.
