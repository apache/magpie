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
import { createDefaultVerifySteps } from './types.js';
import type {
  VerifyRcState,
  VerifyRcStep,
  VerifyStepId,
  StepStatus,
  OverallVerifyStatus,
} from './types.js';

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
 * Anchored to explicit --rc-tag / --tag flags or positional verify-rc / release-verify arguments
 * to prevent false-positive tag resets from directory paths or commit messages.
 */
export function extractRcTag(command: string): string | null {
  if (!command || typeof command !== 'string') return null;
  const invocations = extractCommandInvocations(command);
  for (const inv of invocations) {
    // 1. Explicit flags: --rc-tag <tag>, --rc-tag=<tag>, --tag <tag>, --tag=<tag>
    const flagMatch = inv.match(/(?:--rc-tag|--tag)[=\s]+([0-9A-Za-z_.\-]+-rc\d+)/i);
    const flagTag = flagMatch?.[1];
    if (flagTag) return flagTag;

    // 2. Positional tag in verify-rc, release-verify, or release-config invocations
    // Matches standalone token like '3.0.0-rc1' that is not a directory path or flag argument
    const toolMatch = inv.match(
      /^(?:(?:\S*\/)?(?:verify-rc|verify_rc|release-verify|release_verify|release-config|release_config)(?:\.py|\.cli)?)(?:\s+(.*))?$/i
    );
    if (toolMatch) {
      const rest = toolMatch[1] || '';
      const tokens = rest.split(/\s+/);
      for (const [i, t] of tokens.entries()) {
        const prev = tokens[i - 1] ?? '';
        // Skip flag values for path/directory arguments
        if (/^--(?:dir|path|tree|previous|keys|recipe-dir|validator|manifest)\b/i.test(prev)) {
          continue;
        }
        if (/^[0-9A-Za-z_.\-]+-rc\d+$/i.test(t)) {
          return t;
        }
      }
    }
  }
  return null;
}

/**
 * Derives the base release version from a candidate tag (e.g. '2.11.0-rc1' -> '2.11.0').
 */
export function deriveVersionFromRcTag(rcTag: string): string {
  if (!rcTag || typeof rcTag !== 'string') return '';
  return rcTag.replace(/-rc\d+$/i, '');
}

/**
 * Canonical set of 13 step IDs defined in SKILL.md.
 */
export const ALL_VERIFY_STEP_IDS: ReadonlySet<string> = new Set([
  'preflight',
  'inventory',
  'signatures',
  'checksums',
  'rat-license-headers',
  'notice-license',
  'binary-exclusion',
  'jvm-artefacts',
  'nexus-staging',
  'source-tree-integrity',
  'version-consistency',
  'reproducibility',
  'verdict',
]);

/**
 * Checks whether an identifier is a valid VerifyStepId.
 */
export function isVerifyStepId(id: string): id is VerifyStepId {
  return ALL_VERIFY_STEP_IDS.has(id);
}

/**
 * Extracts executable command invocations from a bash command line,
 * splitting on command separators (;, &&, ||, |, newline) and stripping
 * environment variable definitions and runner prefixes (uv run, uvx, python).
 */
export function extractCommandInvocations(command: string): string[] {
  if (!command || typeof command !== 'string') return [];
  const segments = command.split(/(?:;|&&|\|\||\||\r?\n)/);
  const invocations: string[] = [];
  for (let seg of segments) {
    seg = seg.trim();
    if (!seg) continue;
    // Strip leading environment variable assignments (e.g. VAR=val, FOO="bar")
    seg = seg.replace(/^(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|"[^"]*"|\S+)\s+)*/, '').trim();
    // Strip runner prefixes (uv run [--project <dir>], uvx, python[0-9.]* [-m])
    seg = seg.replace(/^(?:uv\s+run(?:\s+--project\s+\S+)?(?:\s+python[0-9.]*)?|uvx|python[0-9.]*(?:\s+-m)?)\s+/, '').trim();
    // Strip release-management CLI wrapper prefix if present
    seg = seg.replace(/^release-management\s+/, '').trim();
    if (seg) {
      invocations.push(seg);
    }
  }
  return invocations;
}

/**
 * Maps a verify-rc or release-verify CLI invocation to a canonical VerifyStepId or 'all'.
 * Anchors the check to executable invocations to avoid false positives from grep or commit messages.
 */
export function mapCliSubcommandToStepId(command: string): VerifyStepId | 'all' | null {
  if (!command || typeof command !== 'string') return null;

  const invocations = extractCommandInvocations(command);
  for (const inv of invocations) {
    const toolMatch = inv.match(/^(?:(?:\S*\/)?([a-zA-Z0-9_-]+)(?:\.py|\.cli)?)(?:\s+(.*))?$/);
    if (!toolMatch) continue;
    const tool = (toolMatch[1] ?? '').toLowerCase();
    const rest = toolMatch[2] || '';

    if (tool === 'release-verify' || tool === 'release_verify') {
      if (/^all\b/.test(rest)) return 'all';
      if (/^inventory\b/.test(rest)) return 'inventory';
      if (/^signatures\b/.test(rest)) return 'signatures';
      if (/^checksums\b/.test(rest)) return 'checksums';
      if (/^notice-license\b/.test(rest)) return 'notice-license';
      if (/^binaries\b/.test(rest)) return 'binary-exclusion';
      if (/^symlinks\b/.test(rest)) return 'source-tree-integrity';
      if (/^version\b/.test(rest)) return 'version-consistency';
      if (/^verdict\b/.test(rest)) return 'verdict';
    }

    if (tool === 'release-config' || tool === 'release_config') {
      if (/^preflight\b/.test(rest)) return 'preflight';
    }

    if (tool === 'verify-rc' || tool === 'verify_rc') {
      if (/^rat\b/.test(rest)) return 'rat-license-headers';
      if (/^jvm\b/.test(rest)) return 'jvm-artefacts';
      if (/^nexus\b/.test(rest)) return 'nexus-staging';
      if (/^source-tree\b/.test(rest)) return 'source-tree-integrity';
      if (/^repro\b/.test(rest)) return 'reproducibility';
      if (/^report\b/.test(rest)) return 'verdict';
    }

    if (tool === 'maven-artifact-verify') {
      return 'jvm-artefacts';
    }

    if (tool === 'repro-archive' || tool === 'repro_archive') {
      if (/^compare\b/.test(rest)) return 'reproducibility';
    }
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
      return 'warning';
    case 'REVIEW':
    case 'RUNNING':
      return 'running'; // REVIEW means unresolved/undecided; rollup stays running
    case 'SKIP':
    case 'SKIPPED':
      return 'skipped';
    default:
      return 'running';
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
 * Applies skip rules for non-applicable JVM steps (SKILL.md Steps 6b, 6c):
 * - If staged inventory contains no JVM artifacts (.jar, .war, .ear, .pom), marks
 *   jvm-artefacts (6b) and nexus-staging (6c) as skipped.
 * (Note: Step 9 reproducibility skip is determined directly from verify-rc repro output).
 */
export function applyJvmSkipRules(
  steps: VerifyRcStep[],
  inventoryPayload?: any
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
  if (!stepId) {
    return typeof next === 'function' ? next(e) : undefined;
  }

  const BATCH_STEP_IDS: VerifyStepId[] = [
    'inventory',
    'signatures',
    'checksums',
    'notice-license',
    'binary-exclusion',
    'source-tree-integrity',
    'version-consistency',
  ];

  let state = await getVerifyRcState($);
  const rcTag = extractRcTag(command);
  const isFreshRun = stepId === 'preflight' || (Boolean(rcTag) && Boolean(state?.rcTag) && rcTag !== state?.rcTag);

  // Initialize fresh state if starting verify-rc, if preflight re-runs, or if RC tag changed
  if ((!state && stepId) || (state && isFreshRun)) {
    const effectiveRcTag = rcTag || state?.rcTag || 'RC';
    state = {
      rcTag: effectiveRcTag,
      version: deriveVersionFromRcTag(effectiveRcTag),
      overallStatus: 'running',
      currentStepId: stepId === 'all' ? 'inventory' : stepId,
      steps: createDefaultVerifySteps(),
      startedAt: Date.now(),
      completedAt: null,
    };
    const runningIds: readonly string[] = stepId === 'all' ? BATCH_STEP_IDS : stepId ? [stepId] : [];
    for (const id of runningIds) {
      const target = state.steps.find((s) => s.id === id);
      if (target) {
        target.status = 'running';
      }
    }
    await setVerifyRcState($, state);
  } else if (state && stepId) {
    // Mark target step as running regardless of previous status and clear completion timestamp
    state.currentStepId = stepId === 'all' ? 'inventory' : stepId;
    state.completedAt = null;
    if (stepId === 'all') {
      for (const id of BATCH_STEP_IDS) {
        const step = state.steps.find((s) => s.id === id);
        if (step) {
          step.status = 'running';
        }
      }
    } else {
      const target = state.steps.find((s) => s.id === stepId);
      if (target) {
        target.status = 'running';
      }
    }
    state.overallStatus = calculateOverallStatus(state.steps);
    await setVerifyRcState($, state);
  }

  const stepStartTime = Date.now();

  let res: any;
  try {
    res = typeof next === 'function' ? await next(e) : undefined;
  } catch (err) {
    if (state && stepId) {
      const errMsg = sanitizeText(err instanceof Error ? err.message : String(err));
      if (stepId === 'all') {
        for (const id of BATCH_STEP_IDS) {
          const s = state.steps.find((st) => st.id === id);
          if (s) {
            s.status = 'failed';
            s.detail = errMsg;
            s.durationMs = Date.now() - stepStartTime;
          }
        }
        state.currentStepId = null;
      } else {
        const target = state.steps.find((s) => s.id === stepId);
        if (target) {
          target.status = 'failed';
          target.detail = errMsg;
          target.durationMs = Date.now() - stepStartTime;
        }
      }
      state.overallStatus = calculateOverallStatus(state.steps);
      await setVerifyRcState($, state);
    }
    throw err;
  }

  if (state && stepId) {
    try {
      const resObj = res && typeof res === 'object' ? res : null;
      const innerResult = resObj?.result;
      const innerObj = innerResult && typeof innerResult === 'object' ? innerResult : null;

      const rawOutput: string =
        (typeof innerObj?.output === 'string' ? innerObj.output : null) ??
        (typeof innerObj?.stdout === 'string' ? innerObj.stdout : null) ??
        (typeof innerObj?.content === 'string' ? innerObj.content : null) ??
        (typeof innerObj?.text === 'string' ? innerObj.text : null) ??
        (typeof innerResult === 'string' ? innerResult : null) ??
        (typeof resObj?.output === 'string' ? resObj.output : null) ??
        (typeof resObj?.stdout === 'string' ? resObj.stdout : null) ??
        (typeof resObj?.content === 'string' ? resObj.content : null) ??
        (typeof resObj?.text === 'string' ? resObj.text : null) ??
        (typeof res === 'string' ? res : '');

      const exitCode: number | undefined =
        typeof innerObj?.exitCode === 'number'
          ? innerObj.exitCode
          : typeof resObj?.exitCode === 'number'
            ? resObj.exitCode
            : undefined;

      const isError: boolean = Boolean(
        innerObj?.isError ||
        resObj?.isError ||
        (typeof exitCode === 'number' && exitCode !== 0)
      );

      const json = extractJsonFromOutput(rawOutput);

      let target: VerifyRcStep | undefined;
      if (stepId === 'all') {
        if (json && Array.isArray(json.steps) && !isError && (exitCode === 0 || exitCode === undefined)) {
          for (const batchStep of json.steps) {
            const rawStep = String(batchStep.step || batchStep.name || '');
            const matchedId: VerifyStepId | 'all' | null = isVerifyStepId(rawStep)
              ? rawStep
              : mapCliSubcommandToStepId(`release-verify ${rawStep}`);
            if (matchedId && matchedId !== 'all') {
              const batchTarget = state.steps.find((s) => s.id === matchedId);
              if (batchTarget) {
                batchTarget.status = normalizeStepStatus(batchStep.status);
                batchTarget.detail = extractDetailFromPayload(batchStep);
              }
            }
          }
          applyJvmSkipRules(state.steps, json);
          state.currentStepId = null;
        } else {
          // Batch failure on non-zero exit, error payload, or missing steps array
          const rawErrMsg =
            json && typeof json.error === 'string'
              ? json.error
              : typeof rawOutput === 'string' && rawOutput.trim().length > 0
                ? rawOutput
                : exitCode
                  ? `Command failed (exit ${exitCode})`
                  : 'Batch verification failed';
          const detailMsg = truncateText(sanitizeText(rawErrMsg), 60);
          for (const id of BATCH_STEP_IDS) {
            const batchTarget = state.steps.find((s) => s.id === id);
            if (batchTarget) {
              batchTarget.status = 'failed';
              batchTarget.detail = detailMsg;
            }
          }
          state.currentStepId = null;
        }
      } else {
        target = state.steps.find((s) => s.id === stepId);
        if (target) {
          target.durationMs = Date.now() - stepStartTime;

          if (stepId === 'preflight' && json && typeof json.ok === 'boolean') {
            if (!json.ok || (Array.isArray(json.blockers) && json.blockers.length > 0)) {
              target.status = 'failed';
              target.detail =
                Array.isArray(json.blockers) && json.blockers.length > 0
                  ? sanitizeText(json.blockers[0])
                  : 'Pre-flight check blocked';
            } else if (Array.isArray(json.warnings) && json.warnings.length > 0) {
              target.status = 'warning';
              target.detail = sanitizeText(json.warnings[0]);
            } else {
              target.status = 'passed';
            }
            if (json.values && typeof json.values.rc_tag === 'string' && json.values.rc_tag) {
              state.rcTag = json.values.rc_tag;
              state.version = deriveVersionFromRcTag(json.values.rc_tag);
            }
          } else if (stepId === 'verdict' && json && ('overall' in json)) {
            if (json.overall === 'PASS') {
              target.status = 'passed';
            } else if (json.overall === 'PASS-WITH-WARNINGS') {
              target.status = 'warning';
            } else if (json.overall === 'FAIL') {
              target.status = 'failed';
              target.detail =
                Array.isArray(json.fail_steps) && json.fail_steps.length > 0
                  ? `Failed: ${json.fail_steps.join(', ')}`
                  : 'Verdict FAIL';
            } else {
              // overall is null (unresolved steps exist)
              target.status = 'running';
              target.detail =
                Array.isArray(json.unresolved) && json.unresolved.length > 0
                  ? `Unresolved: ${json.unresolved.join(', ')}`
                  : 'Pending step resolution';
            }

            // Reconcile individual step rows reported in step_summary (resolves REVIEW and redirected steps)
            if (Array.isArray(json.step_summary)) {
              for (const item of json.step_summary) {
                const stepKey = String(item.step || '');
                const matchedId: VerifyStepId | 'all' | null = isVerifyStepId(stepKey)
                  ? stepKey
                  : mapCliSubcommandToStepId(`release-verify ${stepKey}`);
                if (matchedId && matchedId !== 'all') {
                  const row = state.steps.find((s) => s.id === matchedId);
                  if (row && item.status) {
                    row.status = normalizeStepStatus(item.status);
                  }
                }
              }
            }
          } else if (stepId === 'reproducibility' && json) {
            if (json.skipped === true || json.status === 'SKIP') {
              target.status = 'skipped';
              target.detail = sanitizeText(json.skip_reason || 'Skipped');
            } else if (json.status !== null && json.status !== undefined) {
              target.status = normalizeStepStatus(json.status);
              target.detail = extractDetailFromPayload(json);
            } else if (isError || typeof json.error === 'string') {
              // verify-rc repro refuses bad input with {"ok": false, "error": ...} and exit 2.
              target.status = 'failed';
              target.detail = truncateText(
                sanitizeText(typeof json.error === 'string' ? json.error : 'Command failed'),
                60
              );
            } else {
              target.status = 'running';
              if (Array.isArray(json.pending) && json.pending.length > 0) {
                target.detail = `Pending: ${json.pending.join(', ')}`;
              }
            }
          } else if (json && json.status !== null && json.status !== undefined) {
            target.status = normalizeStepStatus(json.status);
            target.detail = extractDetailFromPayload(json);
          } else if (isError || (json && typeof json.error === 'string')) {
            // verify-rc report refuses while a step is still REVIEW: the verdict is pending, not failed.
            target.status = stepId === 'verdict' ? 'running' : 'failed';
            const rawErrMsg =
              json && typeof json.error === 'string'
                ? json.error
                : typeof rawOutput === 'string' && rawOutput.trim().length > 0
                  ? rawOutput
                  : exitCode
                    ? `Command failed (exit ${exitCode})`
                    : 'Command failed';
            target.detail = truncateText(sanitizeText(rawErrMsg), 60);
          } else {
            // Missing status, status: null, or pending output -> keep status as running
            target.status = 'running';
            if (json && Array.isArray(json.pending) && json.pending.length > 0) {
              target.detail = `Pending: ${json.pending.join(', ')}`;
            }
          }
        }

        if (stepId === 'inventory' && json) {
          applyJvmSkipRules(state.steps, json);
        }
      }

      if (stepId === 'verdict' && json && json.overall !== null && json.overall !== undefined) {
        if (json.overall === 'PASS') {
          state.overallStatus = 'passed';
        } else if (json.overall === 'PASS-WITH-WARNINGS') {
          state.overallStatus = 'passed-with-warnings';
        } else if (json.overall === 'FAIL') {
          state.overallStatus = 'failed';
        }
        state.completedAt = Date.now();
      } else {
        state.overallStatus = calculateOverallStatus(state.steps);
        if (state.steps.every((s) => s.status !== 'pending' && s.status !== 'running')) {
          state.completedAt = Date.now();
        }
      }

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
