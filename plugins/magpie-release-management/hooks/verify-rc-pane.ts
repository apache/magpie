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

import { atom, read, update } from 'claude-code';
import { createDefaultVerifySteps } from './types.ts';
import type {
  VerifyRcState,
  VerifyRcStep,
  VerifyStepId,
  StepStatus,
  OverallVerifyStatus,
} from './types.ts';

export const verifyRcState = atom(
  { plugin: 'magpie-release-management', key: 'verifyRcState' },
  null as VerifyRcState | null
);

/**
 * Retrieves the current verifyRcState from the session state store.
 */
export async function getVerifyRcState($: any): Promise<VerifyRcState | null> {
  try {
    return (await read($, verifyRcState)) ?? null;
  } catch {
    return null;
  }
}

/**
 * Sets the verifyRcState in the session state store and invalidates the UI.
 */
export async function setVerifyRcState($: any, state: VerifyRcState | null): Promise<void> {
  try {
    await update($, verifyRcState, () => state);
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // UI invalidation optional in non-interactive / headless contexts
    }
  } catch {
    // Fail-open
  }
}

/**
 * Strips ANSI CSI and OSC sequences and C0/C1 control characters, and folds line
 * breaks to a space so that one detail cannot draw a second checklist row.
 */
export function sanitizeText(raw: unknown): string {
  if (typeof raw !== 'string') {
    return '';
  }
  return raw
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .trim();
}

/**
 * Maps step statuses to terminal display badges, symbols, colors, and emphasis.
 */
export function formatStepStatusBadge(status: StepStatus): {
  symbol: string;
  label: string;
  color: string;
  bold: boolean;
} {
  switch (status) {
    case 'passed':
      return { symbol: '[\u2713]', label: 'PASS', color: 'success', bold: true };
    case 'failed':
      return { symbol: '[\u2717]', label: 'FAIL', color: 'error', bold: true };
    case 'warning':
      return { symbol: '[!]', label: 'WARN', color: 'warning', bold: true };
    case 'running':
      return { symbol: '[*]', label: 'RUNNING', color: 'info', bold: true };
    case 'skipped':
      return { symbol: '[-]', label: 'SKIP', color: 'dim', bold: false };
    case 'pending':
    default:
      return { symbol: '[ ]', label: 'PENDING', color: 'dim', bold: false };
  }
}

export interface ProgressSummary {
  total: number;
  completed: number;
  passed: number;
  failed: number;
  warning: number;
  running: number;
  pending: number;
  skipped: number;
}

/**
 * Aggregates progress metrics across the checklist steps.
 */
export function calculateProgressSummary(steps: VerifyRcStep[]): ProgressSummary {
  let passed = 0;
  let failed = 0;
  let warning = 0;
  let running = 0;
  let pending = 0;
  let skipped = 0;

  for (const step of steps) {
    switch (step.status) {
      case 'passed':
        passed += 1;
        break;
      case 'failed':
        failed += 1;
        break;
      case 'warning':
        warning += 1;
        break;
      case 'running':
        running += 1;
        break;
      case 'skipped':
        skipped += 1;
        break;
      case 'pending':
      default:
        pending += 1;
        break;
    }
  }

  const completed = passed + failed + warning + skipped;
  return {
    total: steps.length,
    completed,
    passed,
    failed,
    warning,
    running,
    pending,
    skipped,
  };
}

/**
 * Truncates text cleanly with an ellipsis when exceeding maxLen.
 */
export function truncateText(text: string, maxLen: number): string {
  if (!text || text.length <= maxLen) {
    return text;
  }
  return text.slice(0, maxLen - 1) + '\u2026';
}

/**
 * Resolves color for overall verification status.
 */
function getOverallStatusColor(status: OverallVerifyStatus): string {
  switch (status) {
    case 'passed':
      return 'success';
    case 'passed-with-warnings':
      return 'warning';
    case 'failed':
      return 'error';
    case 'running':
    default:
      return 'info';
  }
}

/**
 * Renders the Release Candidate verification checklist Pane.
 *
 * Designed with a compact vertical budget:
 * - Clean single-line rows for passed or pending steps
 * - Inline details rendered on failures or warnings
 * - Returns null when state is unpopulated or UI components are unavailable
 */
export function renderVerifyRcPane($: any, e: any, state: VerifyRcState | null): any {
  if (!state || !state.steps || state.steps.length === 0) {
    return null;
  }

  let Box: any;
  let Text: any;
  try {
    const resolved = $.ui.resolve(e);
    Box = resolved.Box;
    Text = resolved.Text;
  } catch {
    return null;
  }

  if (!Box || !Text) {
    return null;
  }

  const summary = calculateProgressSummary(state.steps);
  const statusColor = getOverallStatusColor(state.overallStatus);
  const cleanTag = sanitizeText(state.rcTag) || 'Release Candidate';

  const headerChildren = [
    Text({
      children: [`RC Verification: ${cleanTag}`],
      bold: true,
    }),
    Text({
      children: [
        `Progress: ${summary.completed}/${summary.total} completed \u00B7 Status: ${state.overallStatus.toUpperCase()}`,
      ],
      color: statusColor,
      bold: true,
    }),
  ];

  const stepRows: any[] = [];
  for (const step of state.steps) {
    const badgeSpec = formatStepStatusBadge(step.status);
    const cleanLabel = sanitizeText(step.label);
    const isSpecialState = step.status === 'failed' || step.status === 'warning';

    const rowChildren = [
      Text({
        children: [`${badgeSpec.symbol} `],
        color: badgeSpec.color,
        bold: badgeSpec.bold,
      }),
      Text({
        children: [`${cleanLabel} `],
        bold: step.status === 'running' || step.status === 'failed',
      }),
      Text({
        children: [`[${badgeSpec.label}]`],
        color: badgeSpec.color,
        bold: badgeSpec.bold,
      }),
    ];

    if (isSpecialState && step.detail) {
      const cleanDetail = truncateText(sanitizeText(step.detail), 60);
      rowChildren.push(
        Text({
          children: [` \u2014 ${cleanDetail}`],
          color: badgeSpec.color,
        })
      );
    }

    stepRows.push(
      Box({
        children: rowChildren,
      })
    );
  }

  const footerText =
    state.overallStatus === 'running'
      ? state.currentStepId
        ? `Current: ${sanitizeText(state.steps.find((s) => s.id === state.currentStepId)?.label || 'Running check')}...`
        : 'Running mechanical release checks...'
      : state.overallStatus === 'passed'
        ? 'Verdict: PASS (All mechanical checks passed; voter obligation remains)'
        : state.overallStatus === 'passed-with-warnings'
          ? 'Verdict: PASS-WITH-WARNINGS (Review warnings prior to vote draft)'
          : 'Verdict: FAIL (Hard blocker encountered; do not release candidate)';

  const footerBox = Box({
    paddingTop: 1,
    children: [
      Text({
        children: [footerText],
        color: statusColor,
        bold: state.overallStatus !== 'running',
      }),
    ],
  });

  return Box({
    flexDirection: 'column',
    children: [
      Box({
        flexDirection: 'column',
        paddingBottom: 1,
        children: headerChildren,
      }),
      Box({
        flexDirection: 'column',
        children: stepRows,
      }),
      footerBox,
    ],
  });
}

/**
 * Extracts a release candidate tag from a shell command string.
 */
export function extractRcTag(command: string): string | null {
  if (!command || typeof command !== 'string') return null;
  const match =
    command.match(/(?:verify-rc|--rc-tag|--tag)[=\s]+([0-9A-Za-z_.\-]+-rc\d+)/i) ||
    command.match(/\b([0-9A-Za-z_.\-]+-rc\d+)\b/);
  return match ? match[1] : null;
}

/**
 * Derives the base release version from a candidate tag (e.g. '2.11.0-rc1' -> '2.11.0').
 */
export function deriveVersionFromRcTag(rcTag: string): string {
  if (!rcTag || typeof rcTag !== 'string') return '';
  return rcTag.replace(/-rc\d+$/i, '');
}

/**
 * Maps a verify-rc or release-verify CLI invocation to a canonical VerifyStepId or 'all'.
 */
export function mapCliSubcommandToStepId(command: string): VerifyStepId | 'all' | null {
  if (!command || typeof command !== 'string') return null;

  // Batch runner
  if (/\brelease-verify(?:\.py|\.cli)?\s+all\b/.test(command)) {
    return 'all';
  }

  // Preflight check & config load
  if (/\brelease-config(?:\.py|\.cli)?\s+(?:preflight|load)\b/.test(command)) {
    return 'preflight';
  }

  // Subcommands matching canonical steps
  if (/\brelease-verify(?:\.py|\.cli)?\s+inventory\b/.test(command)) {
    return 'inventory';
  }
  if (/\brelease-verify(?:\.py|\.cli)?\s+signatures\b/.test(command)) {
    return 'signatures';
  }
  if (/\brelease-verify(?:\.py|\.cli)?\s+checksums\b/.test(command)) {
    return 'checksums';
  }
  if (/\b(?:release-verify(?:\.py|\.cli)?\s+rat|verify-rc\s+rat)\b/.test(command)) {
    return 'rat-license-headers';
  }
  if (/\brelease-verify(?:\.py|\.cli)?\s+notice-license\b/.test(command)) {
    return 'notice-license';
  }
  if (/\brelease-verify(?:\.py|\.cli)?\s+binaries\b/.test(command)) {
    return 'binary-exclusion';
  }
  if (/\b(?:verify-rc\s+jvm|maven-artifact-verify)\b/.test(command)) {
    return 'jvm-artefacts';
  }
  if (/\bverify-rc\s+nexus\b/.test(command)) {
    return 'nexus-staging';
  }
  if (/\b(?:release-verify(?:\.py|\.cli)?\s+symlinks|verify-rc\s+source-tree)\b/.test(command)) {
    return 'source-tree-integrity';
  }
  if (/\brelease-verify(?:\.py|\.cli)?\s+version\b/.test(command)) {
    return 'version-consistency';
  }
  if (/\b(?:verify-rc\s+repro|repro-archive(?:\.py|\.cli)?\s+compare)\b/.test(command)) {
    return 'reproducibility';
  }
  if (/\b(?:release-verify(?:\.py|\.cli)?\s+verdict|verify-rc\s+report)\b/.test(command)) {
    return 'verdict';
  }

  return null;
}

/**
 * Extracts and parses the first JSON payload found in a tool's output string.
 */
export function extractJsonFromOutput(output: unknown): any | null {
  if (!output) return null;
  const str = typeof output === 'string' ? output : JSON.stringify(output);
  const start = str.indexOf('{');
  const end = str.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) {
    return null;
  }
  try {
    return JSON.parse(str.slice(start, end + 1));
  } catch {
    return null;
  }
}

/**
 * Normalizes tool exit/status strings to the StepStatus union.
 */
export function normalizeStepStatus(status: unknown): StepStatus {
  if (typeof status !== 'string') return 'pending';
  const clean = status.trim().toUpperCase();
  switch (clean) {
    case 'PASS':
    case 'PASSED':
    case 'OK':
    case 'SUCCESS':
    case 'PROCEED':
      return 'passed';
    case 'FAIL':
    case 'FAILED':
    case 'ERROR':
    case 'BLOCKED':
      return 'failed';
    case 'WARN':
    case 'WARNING':
    case 'REVIEW':
      return 'warning';
    case 'SKIP':
    case 'SKIPPED':
      return 'skipped';
    case 'RUNNING':
      return 'running';
    default:
      return 'pending';
  }
}

/**
 * Calculates the overall status rollup across all verification steps.
 */
export function calculateOverallStatus(steps: VerifyRcStep[]): OverallVerifyStatus {
  if (steps.some((s) => s.status === 'failed')) {
    return 'failed';
  }
  const isComplete = steps.every(
    (s) => s.status === 'passed' || s.status === 'warning' || s.status === 'skipped'
  );
  if (isComplete) {
    return steps.some((s) => s.status === 'warning') ? 'passed-with-warnings' : 'passed';
  }
  return 'running';
}

/**
 * Extracts concise detail text from structured tool JSON payloads.
 */
export function extractDetailFromPayload(payload: any): string | null {
  if (!payload || typeof payload !== 'object') return null;

  if (typeof payload.detail === 'string' && payload.detail.trim().length > 0) {
    return sanitizeText(payload.detail);
  }
  if (typeof payload.diff_summary === 'string' && payload.diff_summary.trim().length > 0) {
    return sanitizeText(payload.diff_summary);
  }
  if (Array.isArray(payload.unapproved_files) && payload.unapproved_files.length > 0) {
    return sanitizeText(`Unapproved headers: ${payload.unapproved_files.length} file(s)`);
  }
  if (Array.isArray(payload.missing) && payload.missing.length > 0) {
    return sanitizeText(`Missing: ${payload.missing.join(', ')}`);
  }
  if (Array.isArray(payload.prohibited_found) && payload.prohibited_found.length > 0) {
    return sanitizeText(`Prohibited: ${payload.prohibited_found.join(', ')}`);
  }
  if (payload.deprecated_md5_present) {
    return 'Deprecated md5 digest staged';
  }
  if (Array.isArray(payload.dangling_symlinks) && payload.dangling_symlinks.length > 0) {
    return sanitizeText(`Dangling symlink: ${payload.dangling_symlinks[0]}`);
  }
  if (Array.isArray(payload.validator_failures) && payload.validator_failures.length > 0) {
    const f = payload.validator_failures[0];
    return sanitizeText(f.detail || f.validator || 'Validator failed');
  }
  if (Array.isArray(payload.blockers) && payload.blockers.length > 0) {
    return sanitizeText(payload.blockers[0]);
  }
  return null;
}

/**
 * Applies skip rules for non-applicable steps (Potiuk feedback):
 * - If staged inventory contains no JVM artifacts (.jar, .pom, .war), mark steps 6b and 6c as skipped.
 * - If --skip-repro was passed, mark reproducibility (step 9) as skipped.
 */
export function applyJvmAndReproSkipRules(
  steps: VerifyRcStep[],
  inventoryPayload?: any,
  command?: string
): void {
  const inv =
    inventoryPayload && Array.isArray(inventoryPayload.steps)
      ? inventoryPayload.steps.find(
          (s: any) => s.step === 'inventory' || s.id === 'inventory'
        )
      : inventoryPayload;

  if (inv && Array.isArray(inv.found)) {
    const hasJvm = inv.found.some((f: string) =>
      /\.(?:jar|war|ear|pom)$/i.test(f)
    );
    if (!hasJvm) {
      const jvmStep = steps.find((s) => s.id === 'jvm-artefacts');
      if (jvmStep && jvmStep.status === 'pending') {
        jvmStep.status = 'skipped';
        jvmStep.detail = 'No JVM artefacts staged';
      }
      const nexusStep = steps.find((s) => s.id === 'nexus-staging');
      if (nexusStep && nexusStep.status === 'pending') {
        nexusStep.status = 'skipped';
        nexusStep.detail = 'No JVM artefacts staged';
      }
    }
  }

  if (command && /--skip-repro\b/.test(command)) {
    const reproStep = steps.find((s) => s.id === 'reproducibility');
    if (reproStep && reproStep.status === 'pending') {
      reproStep.status = 'skipped';
      reproStep.detail = 'Skipped via --skip-repro';
    }
  }
}

/**
 * Bash tool.call middleware interceptor for release candidate verification.
 *
 * Passively observes release-config and release-verify commands:
 * 1. Initializes or updates the verifyRcState atom before command execution.
 * 2. Invokes next(e) to run the CLI tool.
 * 3. Parses stdout / result JSON to update step status, details, and overall rollup.
 * 4. Fails open on any error so command execution is never obstructed.
 */
export async function handleBashToolCall($: any, e: any, next: any): Promise<any> {
  const command = e && typeof e.command === 'string' ? e.command : '';
  if (!command) {
    return typeof next === 'function' ? next(e) : undefined;
  }

  const stepId = mapCliSubcommandToStepId(command);
  let state = await getVerifyRcState($);

  // Initialize state if starting verify-rc and state is not yet populated
  if (!state && stepId) {
    const rcTag = extractRcTag(command) || 'RC';
    state = {
      rcTag,
      version: deriveVersionFromRcTag(rcTag),
      overallStatus: 'running',
      currentStepId: stepId === 'all' ? 'inventory' : stepId,
      steps: createDefaultVerifySteps(),
      startedAt: Date.now(),
    };
    if (stepId !== 'all') {
      const target = state.steps.find((s) => s.id === stepId);
      if (target) {
        target.status = 'running';
      }
    }
    await setVerifyRcState($, state);
  } else if (state && stepId) {
    // Mark target step as running
    state.currentStepId = stepId === 'all' ? 'inventory' : stepId;
    if (stepId !== 'all') {
      const target = state.steps.find((s) => s.id === stepId);
      if (target && target.status === 'pending') {
        target.status = 'running';
      }
    }
    await setVerifyRcState($, state);
  }

  const stepStartTime = Date.now();

  let res: any;
  try {
    res = typeof next === 'function' ? await next(e) : undefined;
  } catch (err) {
    if (state && stepId && stepId !== 'all') {
      const target = state.steps.find((s) => s.id === stepId);
      if (target) {
        target.status = 'failed';
        target.detail = sanitizeText(err instanceof Error ? err.message : String(err));
        target.durationMs = Date.now() - stepStartTime;
      }
      state.overallStatus = calculateOverallStatus(state.steps);
      await setVerifyRcState($, state);
    }
    throw err;
  }

  if (state && stepId) {
    try {
      const rawOutput =
        res?.output ?? res?.stdout ?? res?.content ?? res?.text ?? (typeof res === 'string' ? res : '');
      const json = extractJsonFromOutput(rawOutput);

      if (stepId === 'all' && json && Array.isArray(json.steps)) {
        for (const batchStep of json.steps) {
          const matchedId = mapCliSubcommandToStepId(`release-verify ${batchStep.step || batchStep.name}`);
          if (matchedId && matchedId !== 'all') {
            const target = state.steps.find((s) => s.id === matchedId);
            if (target) {
              target.status = normalizeStepStatus(batchStep.status);
              target.detail = extractDetailFromPayload(batchStep);
            }
          }
        }
        applyJvmAndReproSkipRules(state.steps, json, command);
        state.currentStepId = null;
      } else if (stepId !== 'all') {
        const target = state.steps.find((s) => s.id === stepId);
        if (target) {
          target.durationMs = Date.now() - stepStartTime;
          if (json && json.status) {
            target.status = normalizeStepStatus(json.status);
            target.detail = extractDetailFromPayload(json);
          } else if (res?.exitCode === 0 || (typeof res === 'object' && !res.isError)) {
            target.status = 'passed';
          } else {
            target.status = 'failed';
            target.detail = truncateText(sanitizeText(rawOutput || 'Check failed'), 60);
          }
        }

        if (stepId === 'inventory' && json) {
          applyJvmAndReproSkipRules(state.steps, json, command);
        }

        if (/--skip-repro\b/.test(command)) {
          const repro = state.steps.find((s) => s.id === 'reproducibility');
          if (repro && repro.status === 'pending') {
            repro.status = 'skipped';
            repro.detail = 'Skipped via --skip-repro';
          }
        }
      }

      if (
        stepId === 'verdict' ||
        state.steps.every((s) => s.status !== 'pending' && s.status !== 'running')
      ) {
        state.completedAt = Date.now();
      }

      state.overallStatus = calculateOverallStatus(state.steps);
      await setVerifyRcState($, state);
    } catch {
      // Fail-open
    }
  }

  return res;
}

/**
 * Registers the magpie-release-management verify-rc checklist mod hooks.
 *
 * 1. session.start - Initializes or resets the verifyRcState atom to null
 * 2. ui.render (component=Pane) - Renders the verification checklist pane
 * 3. tool.call (tool=Bash) - Passively feeds CLI check progress to the atom
 */
export function register(hooks: any): void {
  hooks('session.start', async ($: any, e: any, next: any) => {
    try {
      await setVerifyRcState($, null);
    } catch {
      // Fail-open
    }
    return next(e);
  });

  hooks('ui.render', async ($: any, e: any, next: any) => {
    if (e.component === 'Pane') {
      try {
        const state = await getVerifyRcState($);
        const pane = renderVerifyRcPane($, e, state);
        if (pane) {
          return pane;
        }
      } catch {
        // Fail-open to next render handler
      }
    }
    return next(e);
  });

  hooks('tool.call', { tool: 'Bash' }, handleBashToolCall);
}
