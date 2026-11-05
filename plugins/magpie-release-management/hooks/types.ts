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
// validation. Any property added to VerifyRcState or VerifyRcStep must be
// kept in sync across both files.

export type VerifyStepId =
  | 'preflight'
  | 'inventory'
  | 'signatures'
  | 'checksums'
  | 'rat-license-headers'
  | 'notice-license'
  | 'binary-exclusion'
  | 'source-tree-integrity'
  | 'version-consistency'
  | 'reproducibility'
  | 'verdict';

export type StepStatus = 'pending' | 'running' | 'passed' | 'failed' | 'warning' | 'skipped';

export type OverallVerifyStatus = 'running' | 'passed' | 'passed-with-warnings' | 'failed';

export interface VerifyRcStep {
  id: VerifyStepId;
  label: string;
  status: StepStatus;
  detail?: string | null;
  durationMs?: number | null;
}

export interface VerifyRcState {
  rcTag: string;
  version: string;
  stagingUrl?: string | null;
  postTo?: string | null;
  overallStatus: OverallVerifyStatus;
  currentStepId?: VerifyStepId | null;
  steps: VerifyRcStep[];
  startedAt: number;
  completedAt?: number | null;
}

/**
 * Returns the canonical 11 verification steps in exact SKILL.md execution order,
 * all initialized in 'pending' status.
 */
export function createDefaultVerifySteps(): VerifyRcStep[] {
  return [
    { id: 'preflight', label: 'Pre-flight check & config resolution', status: 'pending' },
    { id: 'inventory', label: 'Staged artefacts inventory', status: 'pending' },
    { id: 'signatures', label: 'GPG signatures (KEYS verification)', status: 'pending' },
    { id: 'checksums', label: 'SHA512 & digest checksums', status: 'pending' },
    { id: 'rat-license-headers', label: 'Apache RAT license headers', status: 'pending' },
    { id: 'notice-license', label: 'NOTICE and LICENSE integrity', status: 'pending' },
    { id: 'binary-exclusion', label: 'Prohibited binaries scan', status: 'pending' },
    { id: 'source-tree-integrity', label: 'Source integrity & symlinks', status: 'pending' },
    { id: 'version-consistency', label: 'Version manifest consistency', status: 'pending' },
    { id: 'reproducibility', label: 'Reproducible build verification', status: 'pending' },
    { id: 'verdict', label: 'Final verification verdict', status: 'pending' },
  ];
}
