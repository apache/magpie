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
import type {
  VerifyRcState,
  VerifyRcStep,
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
 * Registers the magpie-release-management verify-rc checklist mod hooks.
 *
 * 1. session.start - Initializes or resets the verifyRcState atom to null
 * 2. ui.render (component=Pane) - Renders the verification checklist pane
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
}
