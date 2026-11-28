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

// Companion ambient declaration lives in types.d.ts for Claude Code mod plugin
// validation. Any property added to ReviewFindingsState, ReviewFinding, or
// TriageProgressState must be kept in sync across both files.

export type FindingSeverity = 'blocking' | 'major' | 'minor' | 'nit';

export type FindingSource = 'primary' | 'adversarial' | 'both';

export type FindingAction = 'accept' | 'skip' | 'edit';

export interface ReviewFinding {
  id: string;
  file: string;
  line?: number | null;
  severity: FindingSeverity;
  body: string;
  rule?: string;
  source?: FindingSource;
  fixup?: string | null;
  action: FindingAction;
  raw?: unknown;
}

export interface ReviewFindingsSummary {
  blockingCount: number;
  majorCount: number;
  minorCount: number;
  nitCount: number;
  total: number;
  anchoredCount: number;
  unanchoredCount: number;
}

export interface ReviewFindingsState {
  prNumber?: number;
  prTitle?: string;
  findingsPath?: string;
  sourceHash?: string | null;
  findings: ReviewFinding[];
  summary: ReviewFindingsSummary;
  selectedIndex: number;
  syncError?: string | null;
}

export interface ParseFindingsResult {
  findings: ReviewFinding[];
  errors: string[];
  summary: ReviewFindingsSummary;
}

export interface TriageDispositionCounts {
  labeled: number;
  nudged: number;
  closed: number;
  drafted: number;
  approved: number;
}

export interface TriageProgressState {
  skill: 'pr-triage' | 'pr-stale-sweep' | (string & {});
  total: number;
  evaluated: number;
  dispositions: TriageDispositionCounts;
  remaining: number;
  currentPr?: {
    number: number;
    title?: string;
  } | null;
  processedPrs?: number[];
  status: 'running' | 'paused' | 'completed';
  updatedAt?: string;
  renderCount?: number;
}

export interface ParseTriagePayloadResult {
  state: TriageProgressState | null;
  error?: string;
}

export interface PrStatsFunnel {
  ready: number;
  responded: number;
  waiting_manual: number;
  waiting_ai: number;
  untriaged: number;
  other: number;
}

export interface PrStatsAreaPressure {
  area: string;
  score: number;
  contribs: number;
  age_4w: number;
  age_1to4w: number;
  age_rec: number;
}

export interface PrStatsWeeklyTotals {
  merged: number;
  closed_not_merged: number;
}

export interface PrStatsPaneState {
  repo: string;
  fetchedAt: string;
  cutoff: string;
  jsonPath: string;
  healthRating: string;
  openCount: number;
  closedCount: number;
  readyCount: number;
  untriagedCount: number;
  untriaged4wCount: number;
  engagedCount: number;
  aiTriagedCount: number;
  recommendationCount: number;
  funnel: PrStatsFunnel;
  pressureAreas: PrStatsAreaPressure[];
  weeklyVelocityTotals: PrStatsWeeklyTotals;
  partial: boolean;
  capNote: string | null;
  syncError: string | null;
  isOpen: boolean;
  updatedAt: string;
}

export type ParsePrStatsResult =
  | { ok: true; state: PrStatsPaneState }
  | { ok: false; error: string };
