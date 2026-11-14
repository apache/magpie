// SPDX-License-Identifier: Apache-2.0
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

/**
 * Candidate issue surfaced during triage or deduplication.
 */
export interface CandidateIssue {
  issue_number: number;
  title: string;
  author: string;
  created_at?: string;
  similarity_score?: number;
  labels?: string[];
  excerpt?: string;
}

/**
 * Staged candidate payload written by the agent/skill to disk.
 */
export interface DuplicateCandidatePayload {
  schema_version: 1;
  target_issue: number;
  target_title: string;
  target_author?: string;
  candidates: CandidateIssue[];
}

/**
 * Curated decision staged by maintainer interaction in the UI pane.
 */
export interface DuplicatePickerDecision {
  schema_version: 1;
  target_issue: number;
  status: 'reviewing' | 'curated' | 'dismissed';
  kept_issue: number;
  dropped_issues: number[];
  dismissed_issues: number[];
  updated_at: string;
}

/**
 * Reactive state stored in the Claude Code atom for the duplicate-picker pane.
 */
export interface DuplicatePickerState {
  targetIssue: number;
  targetTitle: string;
  targetAuthor?: string;
  candidates: CandidateIssue[];
  selectedKeptIssue: number | null;
  dismissedIssues: number[];
}
