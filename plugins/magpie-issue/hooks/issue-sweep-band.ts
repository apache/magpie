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
  IssueDispositionCounts,
  IssueSweepProgressState,
  ParseIssuePayloadResult,
} from './types.js';

/**
 * Sanitizes untrusted external issue titles or strings by stripping ANSI escapes,
 * Unicode bidirectional overrides, control characters, paragraph/line separators,
 * zero-width spaces, and markdown/HTML tags.
 */
export function sanitizeIssueTitle(text: unknown, maxLen: number = 40): string {
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
 * Calculates remaining issues clamping at 0 (prevents negative counts on over-evaluation).
 */
export function computeRemainingCount(total: number, evaluated: number): number {
  if (!Number.isFinite(total) || total < 0) return 0;
  if (!Number.isFinite(evaluated) || evaluated < 0) return Math.max(0, Math.floor(total));
  return Math.max(0, Math.floor(total) - Math.floor(evaluated));
}

/**
 * Extracts issue number from a command string accommodating options and flags
 * in arbitrary positions before or after the positional argument.
 */
export function extractIssueNumberFromCommand(command: string): number | null {
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

  // Find where 'gh', [optional global flags], 'issue', '<subcmd>' are located
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
    if (ghSeen && textLower === 'issue') {
      const nextToken = rawTokens[i + 1];
      if (!nextToken) continue;
      const nextLower = nextToken.text.toLowerCase();
      if (['view', 'edit', 'close', 'comment', 'reopen', 'develop', 'delete'].includes(nextLower)) {
        subcmdIndex = i + 1;
        subcmd = nextLower;
        break;
      }
    }
  }
  if (subcmdIndex === -1) return null;

  // Subcommand-specific flags that consume the next token as an argument
  const commonFlagsWithValue = new Set(['-r', '--repo']);
  const viewFlagsWithValue = new Set(['-q', '--jq', '-t', '--template', '--json']);
  const closeFlagsWithValue = new Set(['-c', '--comment', '--reason']);
  const editFlagsWithValue = new Set([
    '-t', '--title',
    '-b', '--body',
    '-f', '--body-file',
    '-m', '--milestone',
    '--add-label', '--remove-label',
    '--add-assignee', '--remove-assignee',
    '--add-project', '--remove-project',
  ]);
  const commentFlagsWithValue = new Set(['-b', '--body', '-f', '--body-file']);

  const args = rawTokens.slice(subcmdIndex + 1);
  for (let i = 0; i < args.length; i++) {
    const token = args[i];
    if (!token) continue;

    // If token is an option with value attached: e.g. --add-label="bug" or -c="stale"
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
        (subcmd === 'comment' && commentFlagsWithValue.has(flagLower));

      if (takesValue) {
        // Skip the next token as it's the flag's value
        i++;
      }
      continue;
    }

    // Check for issue number (#123 or 123) whether quoted or unquoted
    const issueMatch = token.text.match(/^#?([0-9]+)$/);
    if (issueMatch && issueMatch[1]) {
      const num = parseInt(issueMatch[1], 10);
      if (Number.isFinite(num) && num > 0) return num;
    }
    // Check for issue URL like https://github.com/owner/repo/issues/123 whether quoted or unquoted
    const urlMatch = token.text.match(/\/issues\/([0-9]+)\b/i);
    if (urlMatch && urlMatch[1]) {
      const num = parseInt(urlMatch[1], 10);
      if (Number.isFinite(num) && num > 0) return num;
    }
  }

  return null;
}

/**
 * Parses and validates an unknown raw payload into a strict IssueSweepProgressState.
 */
export function parseIssueProgressPayload(raw: unknown): ParseIssuePayloadResult {
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

  let skill: 'issue-triage' | 'issue-stale-sweep' | 'issue-backlog-stats' = 'issue-triage';
  if (obj.skill === 'issue-stale-sweep') {
    skill = 'issue-stale-sweep';
  } else if (obj.skill === 'issue-backlog-stats') {
    skill = 'issue-backlog-stats';
  }

  const total = Number.isFinite(Number(obj.total)) && Number(obj.total) >= 0 ? Math.floor(Number(obj.total)) : 0;
  const evaluated = Number.isFinite(Number(obj.evaluated)) && Number(obj.evaluated) >= 0 ? Math.floor(Number(obj.evaluated)) : 0;
  const remaining = computeRemainingCount(total, evaluated);

  const rawDisp = typeof obj.dispositions === 'object' && obj.dispositions !== null ? obj.dispositions : {};
  const dispositions: IssueDispositionCounts = {
    labeled: Number.isFinite(Number(rawDisp.labeled)) && Number(rawDisp.labeled) >= 0 ? Math.floor(Number(rawDisp.labeled)) : 0,
    nudged: Number.isFinite(Number(rawDisp.nudged)) && Number(rawDisp.nudged) >= 0 ? Math.floor(Number(rawDisp.nudged)) : 0,
    closed: Number.isFinite(Number(rawDisp.closed)) && Number(rawDisp.closed) >= 0 ? Math.floor(Number(rawDisp.closed)) : 0,
    duplicate: Number.isFinite(Number(rawDisp.duplicate)) && Number(rawDisp.duplicate) >= 0 ? Math.floor(Number(rawDisp.duplicate)) : 0,
    other: Number.isFinite(Number(rawDisp.other)) && Number(rawDisp.other) >= 0 ? Math.floor(Number(rawDisp.other)) : 0,
  };

  let currentIssue: { number: number; title?: string } | null = null;
  if (obj.currentIssue && typeof obj.currentIssue === 'object') {
    const num = Number(obj.currentIssue.number);
    if (Number.isFinite(num) && num > 0) {
      currentIssue = {
        number: Math.floor(num),
        title: sanitizeIssueTitle(obj.currentIssue.title, 40) || undefined,
      };
    }
  }

  const processedIssues: number[] = Array.isArray(obj.processedIssues)
    ? obj.processedIssues
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
      currentIssue,
      processedIssues,
      status,
      updatedAt: typeof obj.updatedAt === 'string' ? obj.updatedAt : new Date().toISOString(),
      renderCount: 0,
    },
  };
}

/**
 * Produces a human-readable summary of progress dispositions.
 */
export function formatIssueSweepSummary(state: IssueSweepProgressState): string {
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
  if (state.dispositions.duplicate > 0) {
    parts.push(`${state.dispositions.duplicate} duplicate`);
  }
  if (state.dispositions.other > 0) {
    parts.push(`${state.dispositions.other} other`);
  }
  parts.push(`${state.remaining} remaining`);
  return parts.join(' \u00B7 ');
}

/**
 * Builds the UI component tree for AbovePrompt rendering using resolved Box & Text.
 */
export function renderIssueSweepProgressBandComponent(
  state: IssueSweepProgressState,
  helpers: { Box: any; Text: any }
): any {
  const { Box, Text } = helpers;
  if (!Box || !Text) return null;

  const isComplete = state.status === 'completed' || (state.total > 0 && state.remaining === 0);
  let badgeLabel = '[Issue Triage]';
  if (state.skill === 'issue-stale-sweep') {
    badgeLabel = '[Issue Stale Sweep]';
  } else if (state.skill === 'issue-backlog-stats') {
    badgeLabel = '[Issue Backlog Stats]';
  }

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

  const summaryText = formatIssueSweepSummary(state);
  const currentIssueSuffix = state.currentIssue?.number
    ? ` (current: #${state.currentIssue.number}${state.currentIssue.title ? ` ${state.currentIssue.title}` : ''})`
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
      currentIssueSuffix
        ? Text({
            children: [currentIssueSuffix],
            dim: true,
          })
        : null,
    ].filter(Boolean),
  });
}

/**
 * Observes CLI commands dispatched via Bash to update issue sweep metrics deterministically
 * without inspecting untrusted stdout text or consuming tokens.
 */
export function processIssueCommand(
  command: string,
  current: IssueSweepProgressState | null
): IssueSweepProgressState | null | undefined {
  if (typeof command !== 'string' || !command.trim()) return undefined;

  // Initialize state on issue triage / stale-sweep skill invocation or candidate listing
  const isListCommand = /\bgh\s+issue\s+list\b/i.test(command);
  const isSweepInvocation = /\b(?:issue-triage|issue-stale-sweep|issue-backlog-stats|issue(?:\s+|-)triage)\b/i.test(command);

  if (isListCommand || (!current && isSweepInvocation)) {
    // Check if command specifies a limit flag (e.g. --limit 500, --limit=500, -L 50, -L=50)
    const limitMatch = command.match(/(?:--limit|-L)(?:=|\s+)([0-9]+)\b/i);
    const candidateLimit = limitMatch && limitMatch[1] ? parseInt(limitMatch[1], 10) : 10;
    const initialTotal = Math.max(1, candidateLimit);

    let detectedSkill: 'issue-triage' | 'issue-stale-sweep' | 'issue-backlog-stats' = 'issue-triage';
    if (/\bstale\b/i.test(command)) {
      detectedSkill = 'issue-stale-sweep';
    } else if (/\bbacklog-stats\b/i.test(command)) {
      detectedSkill = 'issue-backlog-stats';
    }

    if (!current) {
      return {
        skill: detectedSkill,
        total: initialTotal,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: initialTotal,
        currentIssue: null,
        processedIssues: [],
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

  const issueNum = extractIssueNumberFromCommand(command);
  const processedIssues: number[] = Array.isArray(current.processedIssues) ? [...current.processedIssues] : [];
  const updated: IssueSweepProgressState = {
    ...current,
    dispositions: { ...current.dispositions },
    processedIssues,
    updatedAt: new Date().toISOString(),
  };

  // gh issue view updates currentIssue focus
  if (/\bgh\s+issue\s+view\b/i.test(command) && issueNum) {
    if (!current.currentIssue || current.currentIssue.number !== issueNum) {
      updated.currentIssue = { number: issueNum };
      return updated;
    }
  }

  // Label disposition
  if (/\bgh\s+issue\s+edit\b/i.test(command) && /--add-label\b/i.test(command) && issueNum) {
    updated.dispositions.labeled += 1;
    if (!processedIssues.includes(issueNum)) {
      processedIssues.push(issueNum);
      updated.processedIssues = processedIssues;
      updated.evaluated = Math.max(updated.evaluated + 1, processedIssues.length);
      updated.remaining = computeRemainingCount(updated.total, updated.evaluated);
      if (updated.remaining === 0) updated.status = 'completed';
    }
    return updated;
  }

  // Close disposition
  if (/\bgh\s+issue\s+close\b/i.test(command) && issueNum) {
    updated.dispositions.closed += 1;
    if (!processedIssues.includes(issueNum)) {
      processedIssues.push(issueNum);
      updated.processedIssues = processedIssues;
      updated.evaluated = Math.max(updated.evaluated + 1, processedIssues.length);
      updated.remaining = computeRemainingCount(updated.total, updated.evaluated);
      if (updated.remaining === 0) updated.status = 'completed';
    }
    return updated;
  }

  // Comment (nudge / triage proposal) disposition
  if (/\bgh\s+issue\s+comment\b/i.test(command) && issueNum) {
    updated.dispositions.nudged += 1;
    if (!processedIssues.includes(issueNum)) {
      processedIssues.push(issueNum);
      updated.processedIssues = processedIssues;
      updated.evaluated = Math.max(updated.evaluated + 1, processedIssues.length);
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
  if (!/^\.magpie-issue-sweep-[a-zA-Z0-9_\-]+\.json$/.test(fileName)) {
    return false;
  }

  if (typeof cwd !== 'string' || !cwd.trim()) {
    return false; // Fail closed if base directory is unavailable
  }

  const normCwd = cwd.replace(/\\/g, '/');
  const prefix = normCwd.endsWith('/') ? normCwd : `${normCwd}/`;
  return normalized.startsWith(prefix);
}
