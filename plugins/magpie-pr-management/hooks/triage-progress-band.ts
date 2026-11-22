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

import type {
  ParseTriagePayloadResult,
  TriageDispositionCounts,
  TriageProgressState,
} from './types.js';

/**
 * Sanitizes untrusted external PR titles or strings by stripping ANSI escapes,
 * Unicode bidirectional overrides, control characters, paragraph/line separators,
 * and markdown/HTML tags.
 */
export function sanitizePrTitle(text: unknown, maxLen: number = 40): string {
  if (typeof text !== 'string') return '';
  return text
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069\u200E\u200F\u061C\u2028\u2029]/g, '')
    .replace(/[\u200B-\u200D\uFEFF\u2060\u00AD\uFE00-\uFE0F]/g, '')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .replace(/[`<>"']/g, '')
    .trim()
    .slice(0, maxLen);
}

/**
 * Calculates remaining PRs clamping at 0 (prevents negative counts on over-eval).
 */
export function computeRemainingCount(total: number, evaluated: number): number {
  if (!Number.isFinite(total) || total < 0) return 0;
  if (!Number.isFinite(evaluated) || evaluated < 0) return Math.max(0, Math.floor(total));
  return Math.max(0, Math.floor(total) - Math.floor(evaluated));
}

/**
 * Extracts PR number from a gh command string accommodating options and flags
 * in arbitrary positions before or after the positional argument.
 */
export function extractPrNumberFromCommand(command: string): number | null {
  if (typeof command !== 'string' || !command.trim()) return null;

  // Split into tokens handling single and double quotes
  const tokenRegex = /[^\s"']+|"([^"]*)"|'([^']*)'/g;
  const rawTokens: { text: string; isQuoted: boolean }[] = [];
  let match: RegExpExecArray | null;
  while ((match = tokenRegex.exec(command)) !== null) {
    if (match[1] !== undefined) {
      rawTokens.push({ text: match[1], isQuoted: true });
    } else if (match[2] !== undefined) {
      rawTokens.push({ text: match[2], isQuoted: true });
    } else {
      rawTokens.push({ text: match[0], isQuoted: false });
    }
  }

  // Find where 'gh', [optional global flags], 'pr', '<subcmd>' are located
  let ghSeen = false;
  let subcmdIndex = -1;
  let subcmd = '';
  for (let i = 0; i < rawTokens.length - 1; i++) {
    const cur = rawTokens[i];
    if (!cur) continue;
    const textLower = cur.text.toLowerCase();
    if (textLower === 'gh') {
      ghSeen = true;
      continue;
    }
    if (ghSeen && textLower === 'pr') {
      const nextToken = rawTokens[i + 1];
      if (!nextToken) continue;
      const nextLower = nextToken.text.toLowerCase();
      if (['view', 'edit', 'close', 'comment', 'checkout', 'reopen', 'ready', 'diff'].includes(nextLower)) {
        subcmdIndex = i + 1;
        subcmd = nextLower;
        break;
      }
    }
  }
  if (subcmdIndex === -1) return null;

  // Subcommand-specific flags that consume the next token as an argument
  const commonFlagsWithValue = new Set(['-r', '--repo', '-b', '--base']);
  const viewFlagsWithValue = new Set(['-q', '--jq', '-t', '--template', '--json']);
  const closeFlagsWithValue = new Set(['-c', '--comment']);
  const editFlagsWithValue = new Set([
    '-t', '--title',
    '-b', '--body',
    '-f', '--body-file',
    '-m', '--milestone',
    '--add-label', '--remove-label',
    '--add-assignee', '--remove-assignee',
    '--add-reviewer', '--remove-reviewer',
  ]);
  const commentFlagsWithValue = new Set(['-b', '--body', '-f', '--body-file']);
  const checkoutFlagsWithValue = new Set(['-b', '--branch']);

  const args = rawTokens.slice(subcmdIndex + 1);
  for (let i = 0; i < args.length; i++) {
    const token = args[i];
    if (!token) continue;

    // If token is an option with value attached: e.g. --add-label="foo" or -c="stale"
    if (token.text.startsWith('-')) {
      if (token.text.includes('=')) {
        continue;
      }
      const flagLower = token.text.toLowerCase();
      const takesValue =
        commonFlagsWithValue.has(flagLower) ||
        (subcmd === 'view' && viewFlagsWithValue.has(flagLower)) ||
        (subcmd === 'close' && closeFlagsWithValue.has(flagLower)) ||
        (subcmd === 'edit' && editFlagsWithValue.has(flagLower)) ||
        (subcmd === 'comment' && commentFlagsWithValue.has(flagLower)) ||
        (subcmd === 'checkout' && checkoutFlagsWithValue.has(flagLower));

      if (takesValue) {
        // Skip the next token as it's the flag's value
        i++;
      }
      continue;
    }

    // Check for PR number (#123 or 123) whether quoted or unquoted
    const prMatch = token.text.match(/^#?([0-9]+)$/);
    if (prMatch && prMatch[1]) {
      const num = parseInt(prMatch[1], 10);
      if (Number.isFinite(num) && num > 0) return num;
    }
    // Check for PR URL like https://github.com/owner/repo/pull/123 whether quoted or unquoted
    const urlMatch = token.text.match(/\/pull\/([0-9]+)\b/i);
    if (urlMatch && urlMatch[1]) {
      const num = parseInt(urlMatch[1], 10);
      if (Number.isFinite(num) && num > 0) return num;
    }
  }

  return null;
}

/**
 * Parses and validates an unknown raw payload into a strict TriageProgressState.
 */
export function parseTriageProgressPayload(raw: unknown): ParseTriagePayloadResult {
  if (!raw) {
    return { state: null, error: 'Empty payload' };
  }

  let obj: any = raw;
  if (typeof raw === 'string') {
    try {
      obj = JSON.parse(raw);
    } catch {
      return { state: null, error: 'Malformed JSON payload' };
    }
  }

  if (typeof obj !== 'object' || obj === null) {
    return { state: null, error: 'Payload must be an object' };
  }

  const skill =
    obj.skill === 'pr-stale-sweep' ? 'pr-stale-sweep' : 'pr-triage';
  const total = Number.isFinite(Number(obj.total)) && Number(obj.total) >= 0 ? Math.floor(Number(obj.total)) : 0;
  const evaluated = Number.isFinite(Number(obj.evaluated)) && Number(obj.evaluated) >= 0 ? Math.floor(Number(obj.evaluated)) : 0;
  const remaining = computeRemainingCount(total, evaluated);

  const rawDisp = typeof obj.dispositions === 'object' && obj.dispositions !== null ? obj.dispositions : {};
  const dispositions: TriageDispositionCounts = {
    labeled: Number.isFinite(Number(rawDisp.labeled)) && Number(rawDisp.labeled) >= 0 ? Math.floor(Number(rawDisp.labeled)) : 0,
    nudged: Number.isFinite(Number(rawDisp.nudged)) && Number(rawDisp.nudged) >= 0 ? Math.floor(Number(rawDisp.nudged)) : 0,
    closed: Number.isFinite(Number(rawDisp.closed)) && Number(rawDisp.closed) >= 0 ? Math.floor(Number(rawDisp.closed)) : 0,
    drafted: Number.isFinite(Number(rawDisp.drafted)) && Number(rawDisp.drafted) >= 0 ? Math.floor(Number(rawDisp.drafted)) : 0,
    approved: Number.isFinite(Number(rawDisp.approved)) && Number(rawDisp.approved) >= 0 ? Math.floor(Number(rawDisp.approved)) : 0,
  };

  let currentPr: { number: number; title?: string } | null = null;
  if (obj.currentPr && typeof obj.currentPr === 'object') {
    const num = Number(obj.currentPr.number);
    if (Number.isFinite(num) && num > 0) {
      currentPr = {
        number: Math.floor(num),
        title: sanitizePrTitle(obj.currentPr.title, 40) || undefined,
      };
    }
  }

  const processedPrs: number[] = Array.isArray(obj.processedPrs)
    ? obj.processedPrs
        .filter((n: any) => typeof n === 'number' && Number.isFinite(n) && n > 0)
        .slice(0, 1000)
        .map(Math.floor)
    : [];

  let status: 'running' | 'paused' | 'completed' = 'running';
  if (obj.status === 'paused' || obj.status === 'completed') {
    status = obj.status;
  } else if (total > 0 && evaluated >= total) {
    status = 'completed';
  }

  return {
    state: {
      skill,
      total,
      evaluated,
      dispositions,
      remaining,
      currentPr,
      processedPrs,
      status,
      updatedAt: typeof obj.updatedAt === 'string' ? obj.updatedAt : new Date().toISOString(),
      renderCount: 0,
    },
  };
}

/**
 * Produces a human-readable summary of progress dispositions.
 */
export function formatTriageSummary(state: TriageProgressState): string {
  const parts: string[] = [`${state.evaluated}/${state.total} evaluated`];
  if (state.dispositions.labeled > 0) {
    parts.push(`${state.dispositions.labeled} labeled`);
  }
  if (state.dispositions.nudged > 0) {
    parts.push(`${state.dispositions.nudged} nudged`);
  }
  if (state.dispositions.closed > 0) {
    parts.push(`${state.dispositions.closed} closed`);
  }
  if (state.dispositions.drafted > 0) {
    parts.push(`${state.dispositions.drafted} drafted`);
  }
  if (state.dispositions.approved > 0) {
    parts.push(`${state.dispositions.approved} approved`);
  }
  parts.push(`${state.remaining} remaining`);
  return parts.join(' \u00B7 ');
}

/**
 * Builds the UI component tree for AbovePrompt rendering using resolved Box & Text.
 */
export function renderTriageProgressBandComponent(
  state: TriageProgressState,
  helpers: { Box: any; Text: any }
): any {
  const { Box, Text } = helpers;
  if (!Box || !Text) return null;

  const isComplete = state.status === 'completed' || (state.total > 0 && state.remaining === 0);
  const badgeLabel = state.skill === 'pr-stale-sweep' ? '[PR Stale Sweep]' : '[PR Triage]';

  if (isComplete) {
    return Box({
      padding: 0,
      children: [
        Text({
          children: [`${badgeLabel} `],
          color: 'cyan',
          bold: true,
        }),
        Text({
          children: [`\u2713 Sweep complete: ${state.evaluated}/${state.total} evaluated \u00B7 All candidates processed`],
          color: 'green',
          bold: true,
        }),
      ],
    });
  }

  const summaryText = formatTriageSummary(state);
  const currentPrSuffix = state.currentPr?.number
    ? ` (current: #${state.currentPr.number}${state.currentPr.title ? ` ${state.currentPr.title}` : ''})`
    : '';

  return Box({
    padding: 0,
    children: [
      Text({
        children: [`${badgeLabel} `],
        color: 'cyan',
        bold: true,
      }),
      Text({
        children: [summaryText],
        bold: true,
      }),
      currentPrSuffix
        ? Text({
            children: [currentPrSuffix],
            dim: true,
          })
        : null,
    ].filter(Boolean),
  });
}

/**
 * Observes CLI commands dispatched via Bash to update triage metrics deterministically
 * without inspecting untrusted stdout text.
 */
export function processTriageCommand(
  command: string,
  current: TriageProgressState | null
): TriageProgressState | null | undefined {
  if (typeof command !== 'string' || !command.trim()) return undefined;

  // Initialize state on triage skill invocation or candidate listing
  const isListCommand = /\bgh\s+pr\s+list\b/i.test(command);
  const isTriageInvocation = /\b(?:pr-triage|pr-stale-sweep|pr-management(?:\s+|-)triage)\b/i.test(command);

  if (isListCommand || (!current && isTriageInvocation)) {
    // Check if command specifies a limit flag (e.g. --limit 20, --limit=20, -L 20, -L=20)
    const limitMatch = command.match(/(?:--limit|-L)(?:=|\s+)([0-9]+)\b/i);
    const candidateLimit = limitMatch && limitMatch[1] ? parseInt(limitMatch[1], 10) : 10;
    const initialTotal = Math.max(1, candidateLimit);

    if (!current) {
      return {
        skill: /\bstale\b/i.test(command) ? 'pr-stale-sweep' : 'pr-triage',
        total: initialTotal,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: initialTotal,
        currentPr: null,
        processedPrs: [],
        status: 'running',
        updatedAt: new Date().toISOString(),
        renderCount: 0,
      };
    }

    // Re-anchor limit if list command is re-run during active sweep
    if (limitMatch && limitMatch[1]) {
      return {
        ...current,
        total: initialTotal,
        remaining: computeRemainingCount(initialTotal, current.evaluated),
        updatedAt: new Date().toISOString(),
      };
    }
  }

  if (!current) return undefined;

  const prNum = extractPrNumberFromCommand(command);
  const processedPrs: number[] = Array.isArray(current.processedPrs) ? [...current.processedPrs] : [];
  const updated: TriageProgressState = {
    ...current,
    dispositions: { ...current.dispositions },
    processedPrs,
    updatedAt: new Date().toISOString(),
  };

  // gh pr view / checkout updates currentPr focus
  if (/\bgh\s+pr\s+(?:view|checkout)\b/i.test(command) && prNum) {
    if (!current.currentPr || current.currentPr.number !== prNum) {
      updated.currentPr = { number: prNum };
      return updated;
    }
  }

  // Label disposition
  if (/\bgh\s+pr\s+edit\b/i.test(command) && /--add-label\b/i.test(command) && prNum) {
    updated.dispositions.labeled += 1;
    if (!processedPrs.includes(prNum)) {
      processedPrs.push(prNum);
      updated.processedPrs = processedPrs;
      updated.evaluated = Math.max(updated.evaluated + 1, processedPrs.length);
      updated.remaining = computeRemainingCount(updated.total, updated.evaluated);
      if (updated.remaining === 0) updated.status = 'completed';
    }
    return updated;
  }

  // Close disposition
  if (/\bgh\s+pr\s+close\b/i.test(command) && prNum) {
    updated.dispositions.closed += 1;
    if (!processedPrs.includes(prNum)) {
      processedPrs.push(prNum);
      updated.processedPrs = processedPrs;
      updated.evaluated = Math.max(updated.evaluated + 1, processedPrs.length);
      updated.remaining = computeRemainingCount(updated.total, updated.evaluated);
      if (updated.remaining === 0) updated.status = 'completed';
    }
    return updated;
  }

  // Comment (nudge) disposition
  if (/\bgh\s+pr\s+comment\b/i.test(command) && prNum) {
    updated.dispositions.nudged += 1;
    if (!processedPrs.includes(prNum)) {
      processedPrs.push(prNum);
      updated.processedPrs = processedPrs;
      updated.evaluated = Math.max(updated.evaluated + 1, processedPrs.length);
      updated.remaining = computeRemainingCount(updated.total, updated.evaluated);
      if (updated.remaining === 0) updated.status = 'completed';
    }
    return updated;
  }

  return undefined;
}

/**
 * Validates that a progress file path resides strictly inside session CWD or temp,
 * matches the naming pattern, and contains no relative path traversal.
 * Enforces trailing slash component boundary and fails closed if cwd is missing.
 */
export function isConfinedProgressPath(targetPath: string, cwd?: string | null): boolean {
  if (typeof targetPath !== 'string' || !targetPath.trim()) return false;
  if (targetPath.includes('..') || targetPath.includes('\x00')) return false;

  const normalized = targetPath.replace(/\\/g, '/');
  const fileName = normalized.split('/').pop() || '';
  if (!/^\.magpie-pr-triage-[a-zA-Z0-9_\-]+\.json$/.test(fileName)) {
    return false;
  }

  if (typeof cwd !== 'string' || !cwd.trim()) {
    return false; // Fail closed if base directory is unavailable
  }

  const normCwd = cwd.replace(/\\/g, '/');
  const prefix = normCwd.endsWith('/') ? normCwd : `${normCwd}/`;
  return normalized.startsWith(prefix);
}
