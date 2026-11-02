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
  findings: ReviewFinding[];
  summary: ReviewFindingsSummary;
  selectedIndex: number;
}

export interface ParseFindingsResult {
  findings: ReviewFinding[];
  errors: string[];
  summary: ReviewFindingsSummary;
}
