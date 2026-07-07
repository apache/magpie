<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR: velox-community/velox-stream#88
Title: "fix(connectors): handle null schema in Avro deserializer"
Author: external-contributor
Labels: component:connectors, kind:bug
Changed paths:
  velox/connectors/avro/AvroDeserializer.java
  velox/connectors/avro/SchemaRegistry.java

Roster (from projects/non-asf-example/reviewer-roster.md — no ASF infrastructure):
  - handle: priya-velox
    areas: [component:core, component:pipeline, velox/core/, velox/pipeline/]
    max_reviews: 4
    open_review_count: 2
  - handle: mateo-stream
    areas: [component:connectors, component:serialization, velox/connectors/, velox/serialization/]
    max_reviews: 5
    open_review_count: 1
  - handle: yuki-velox
    areas: [component:docs, component:testing, docs/, tests/]
    max_reviews: 6
    open_review_count: 0

Git-history familiarity (recent authors of changed paths):
  velox/connectors/avro/AvroDeserializer.java  → mateo-stream (4 commits)
  velox/connectors/avro/SchemaRegistry.java    → mateo-stream (2 commits), priya-velox (1 commit)

Organization: independent (no ASF PMC, no Apache ID, no Whimsy lookup required)
