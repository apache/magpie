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

export type ReviewAxis = 'correctness' | 'security' | 'conventions';
export type FindingSeverity = 'blocking' | 'advisory';
export type FindingStatus = 'pending' | 'accepted' | 'dismissed';

/**
 * An individual review finding emitted by a sub-agent pass.
 */
export interface ReviewFinding {
  id: string;
  axis: ReviewAxis;
  severity: FindingSeverity;
  location: string;
  summary: string;
  evidence?: string;
  rule?: string;
  alsoFlaggedBy?: ReviewAxis[];
  status: FindingStatus;
}

/**
 * Summary breakdown of findings for a specific axis or overall.
 */
export interface AxisSummary {
  blocking: number;
  advisory: number;
  total: number;
}

/**
 * Staged candidate payload written by the skill to disk.
 */
export interface MultiAgentReviewPayload {
  schema_version: 1;
  head_sha: string;
  base_ref: string;
  files_changed: number;
  lines_added: number;
  lines_removed: number;
  findings: Array<{
    axis: ReviewAxis;
    severity: FindingSeverity;
    location: string;
    summary: string;
    evidence?: string;
    rule?: string;
    also_flagged_by?: ReviewAxis[];
  }>;
  injection_attempts?: string[];
}

/**
 * Curated decision staged by maintainer interaction in the terminal UI pane.
 */
export interface MultiAgentReviewDecision {
  schema_version: 1;
  head_sha: string;
  source_payload_sha256: string;
  accepted_ids: string[];
  dismissed_ids: string[];
  status: 'reviewing' | 'curated' | 'ready';
  updated_at: string;
}

/**
 * Reactive state stored in the Claude Code atom for the multi-agent review pane.
 */
export interface MultiAgentReviewState {
  headSha: string;
  baseRef: string;
  filesChanged: number;
  linesAdded: number;
  linesRemoved: number;
  findings: ReviewFinding[];
  injectionAttempts: string[];
  activeFilter: 'all' | ReviewAxis;
  selectedFindingId: string | null;
  overallStatus: 'reviewing' | 'blocked' | 'ready';
  payloadPath?: string;
  payloadHash?: string;
  updatedAt: string;
}

export interface ParseReviewPayloadResult {
  state: MultiAgentReviewState | null;
  error?: string;
}
