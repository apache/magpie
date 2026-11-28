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
  CandidateIssue,
  DuplicateCandidatePayload,
  DuplicatePickerDecision,
  DuplicatePickerState,
  IssueSweepProgressState,
} from './types.js';
import {
  processIssueCommand,
  renderIssueSweepProgressBandComponent,
} from './issue-sweep-band.js';

export const duplicatePickerState = atom(
  { plugin: 'magpie-issue', key: 'duplicatePickerState' },
  null as DuplicatePickerState | null
);

export const issueSweepProgressState = atom(
  { plugin: 'magpie-issue', key: 'issueSweepProgressState' },
  null as IssueSweepProgressState | null
);

/**
 * Retrieves the current issueSweepProgressState from the session store.
 */
export async function getIssueSweepProgressState(
  $: any
): Promise<IssueSweepProgressState | null> {
  try {
    return (await read($, issueSweepProgressState)) ?? null;
  } catch {
    return null;
  }
}

/**
 * Sets the issueSweepProgressState in the session store and invalidates the UI.
 */
export async function setIssueSweepProgressState(
  $: any,
  state: IssueSweepProgressState | null
): Promise<void> {
  try {
    await update($, issueSweepProgressState, () => state);
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in non-interactive/headless contexts
    }
  } catch {
    // Fail-open
  }
}

/**
 * Handles AbovePrompt rendering for the issue sweep progress band.
 */
export async function handleRenderAbovePrompt($: any, e: any, next: any): Promise<any> {
  try {
    const state = await getIssueSweepProgressState($);
    if (!state) {
      if (typeof next === 'function') return next(e);
      return;
    }

    // Auto-dismiss completed sweep after 1 render cycle
    if (state.status === 'completed') {
      const renderCount = (state.renderCount || 0) + 1;
      if (renderCount > 1) {
        await setIssueSweepProgressState($, null);
        if (typeof next === 'function') return next(e);
        return;
      }
      await update($, issueSweepProgressState, (prev: any) =>
        prev ? { ...prev, renderCount } : null
      );
    }

    const { Box, Text } = $.ui.resolve(e);
    if (Box && Text) {
      return renderIssueSweepProgressBandComponent(state, { Box, Text });
    }
  } catch {
    // Fail-open to next render handler on error
  }

  if (typeof next === 'function') {
    return next(e);
  }
}

/**
 * Intercepts Bash tool calls to observe issue commands and update sweep metrics.
 */
/**
 * Updates issue-sweep progress state on CLI issue commands before passing through.
 */
async function updateIssueSweepOnBash($: any, command: string): Promise<void> {
  try {
    const currentSweep = await getIssueSweepProgressState($);
    let sweepToProcess = currentSweep;
    if (currentSweep && (currentSweep.status === 'completed' || currentSweep.remaining === 0)) {
      const isSweepFollowup = /\bgh\s+issue\s+(?:view|edit|close|comment|reopen)\b/i.test(command);
      if (!isSweepFollowup) {
        await setIssueSweepProgressState($, null);
        sweepToProcess = null;
      }
    }
    const updatedSweep = processIssueCommand(command, sweepToProcess);
    if (updatedSweep !== undefined) {
      await setIssueSweepProgressState($, updatedSweep);
    }
  } catch {
    // Safe no-op on any error (fail-open)
  }
}

/**
 * Retrieves the current duplicatePickerState from the session store.
 */
export async function getDuplicatePickerState($: any): Promise<DuplicatePickerState | null> {
  try {
    return (await read($, duplicatePickerState)) ?? null;
  } catch {
    return null;
  }
}

/**
 * Sets the duplicatePickerState in the session store and invalidates the UI.
 */
export async function setDuplicatePickerState(
  $: any,
  state: DuplicatePickerState | null
): Promise<void> {
  try {
    await update($, duplicatePickerState, () => state);
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in non-interactive/headless contexts
    }
  } catch {
    // Fail-open
  }
}

/**
 * Computes deterministic SHA-256 hex digest of a UTF-8 string in pure TS
 * without external module imports, adhering to mod import boundaries.
 */
export function computePayloadHash(content: string): string {
  const ascii = unescape(encodeURIComponent(content));
  const mathPow = Math.pow;
  const maxWord = mathPow(2, 32);
  const words: number[] = [];
  const asciiBitLength = ascii.length * 8;
  const hash: number[] = [];
  const k: number[] = [];
  let primeCounter = 0;
  const isComposite: Record<number, number> = {};

  for (let candidate = 2; primeCounter < 64; candidate += 1) {
    if (!isComposite[candidate]) {
      for (let i = 0; i < 313; i += candidate) {
        isComposite[i] = candidate;
      }
      hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0;
      k[primeCounter] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
      primeCounter += 1;
    }
  }

  let padded = ascii + '\x80';
  while (padded.length % 64 !== 56) {
    padded += '\x00';
  }

  for (let i = 0; i < padded.length; i += 1) {
    const code = padded.charCodeAt(i);
    words[i >> 2] = (words[i >> 2] ?? 0) | (code << ((3 - (i % 4)) * 8));
  }

  words[words.length] = (asciiBitLength / maxWord) | 0;
  words[words.length] = asciiBitLength;

  for (let j = 0; j < words.length; ) {
    const w = words.slice(j, (j += 16));
    const oldHash = [...hash];
    for (let i = 0; i < 64; i += 1) {
      const w15 = w[i - 15] ?? 0;
      const w2 = w[i - 2] ?? 0;
      const a = hash[0] ?? 0;
      const e = hash[4] ?? 0;
      const h1 = hash[1] ?? 0;
      const h2 = hash[2] ?? 0;
      const s1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & (hash[5] ?? 0)) ^ (~e & (hash[6] ?? 0));
      const s0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const maj = (a & h1) ^ (a & h2) ^ (h1 & h2);

      const wi =
        i < 16
          ? (w[i] ?? 0)
          : (((w[i - 16] ?? 0) +
              (((w15 >>> 7) | (w15 << 25)) ^ ((w15 >>> 18) | (w15 << 14)) ^ (w15 >>> 3)) +
              (w[i - 7] ?? 0) +
              (((w2 >>> 17) | (w2 << 15)) ^ ((w2 >>> 19) | (w2 << 13)) ^ (w2 >>> 10))) |
              0);
      w[i] = wi;

      const temp1 = ((hash[7] ?? 0) + s1 + ch + (k[i] ?? 0) + wi) | 0;
      const temp2 = (s0 + maj) | 0;

      hash[7] = hash[6] ?? 0;
      hash[6] = hash[5] ?? 0;
      hash[5] = e;
      hash[4] = ((hash[3] ?? 0) + temp1) | 0;
      hash[3] = h2;
      hash[2] = h1;
      hash[1] = a;
      hash[0] = (temp1 + temp2) | 0;
    }
    for (let i = 0; i < 8; i += 1) {
      hash[i] = ((hash[i] ?? 0) + (oldHash[i] ?? 0)) | 0;
    }
  }

  let result = '';
  for (let i = 0; i < 8; i += 1) {
    for (let j = 3; j >= 0; j -= 1) {
      const b = ((hash[i] ?? 0) >>> (j * 8)) & 255;
      result += (b < 16 ? '0' : '') + b.toString(16);
    }
  }
  return result;
}

/**
 * What stands at a path the pane is about to write, judged on the shape
 * `$.fs.stat` resolves with in the mod harness: `{ kind, size, mtimeMs, isLink }`.
 * `isLink` describes the path itself and `kind` what it leads to, so a link to a
 * regular file and a link that leads nowhere are both `unsafe`. Only a missing
 * path (`ENOENT`) is `missing`; any other stat failure is `unsafe`, so the write
 * fails closed. `$.fs.exists` is not consulted: it answers for what the path
 * leads to, which says nothing about a link that leads nowhere.
 */
export type WriteTarget = 'missing' | 'regular' | 'unsafe';

function isNotFound(err: any): boolean {
  return err?.code === 'ENOENT' || /ENOENT/.test(String(err?.message ?? err));
}

export async function classifyWriteTarget($: any, path: string): Promise<WriteTarget> {
  let stat: any;
  try {
    stat = await $.fs.stat(path);
  } catch (err: any) {
    return isNotFound(err) ? 'missing' : 'unsafe';
  }
  if (!stat || stat.isLink !== false || stat.kind !== 'file') return 'unsafe';
  return 'regular';
}

/**
 * Derives the sibling decision file path from a candidates file path.
 */
export function getDecisionPath(candidatesPath: string, targetIssue: number): string {
  if (/\.magpie-issue-candidates-\d+\.json$/.test(candidatesPath)) {
    return candidatesPath.replace(
      /\.magpie-issue-candidates-\d+\.json$/,
      `.magpie-issue-decision-${targetIssue}.json`
    );
  }
  return `.magpie-issue-decision-${targetIssue}.json`;
}

/**
 * Safely writes a decision file to disk, refusing to follow symlinks or non-regular files,
 * and ensuring the source candidates file exists.
 */
export async function safeWriteDecisionFile(
  $: any,
  targetIssue: number,
  content: string,
  candidatesPath?: string
): Promise<{ success: boolean; error?: string }> {
  const candidatePath = candidatesPath || `.magpie-issue-candidates-${targetIssue}.json`;
  const decisionPath = getDecisionPath(candidatePath, targetIssue);

  try {
    let candidateExists = false;
    try {
      candidateExists = await $.fs.exists(candidatePath);
    } catch {
      candidateExists = false;
    }
    if (!candidateExists) {
      return {
        success: false,
        error: `Candidate file missing: ${candidatePath}`,
      };
    }

    if ((await classifyWriteTarget($, decisionPath)) === 'unsafe') {
      return {
        success: false,
        error: `Refusing to write to symlink or non-regular file: ${decisionPath}`,
      };
    }

    await $.fs.write(decisionPath, content);
    return { success: true };
  } catch (err: any) {
    return {
      success: false,
      error: err?.message || `Failed to write decision file: ${decisionPath}`,
    };
  }
}

/**
 * Invalidates any existing decision file on disk so downstream skills do not load stale choices.
 */
export async function invalidateDecisionFile(
  $: any,
  targetIssue: number,
  candidatesPath?: string
): Promise<void> {
  const decisionPath = candidatesPath
    ? getDecisionPath(candidatesPath, targetIssue)
    : `.magpie-issue-decision-${targetIssue}.json`;
  try {
    // Only an existing regular file is overwritten; a missing path needs no
    // invalidation, and a link or anything else is left alone.
    if ((await classifyWriteTarget($, decisionPath)) !== 'regular') return;

    const invalidEnvelope: DuplicatePickerDecision = {
      schema_version: 1,
      target_issue: targetIssue,
      status: 'reviewing',
      kept_issue: targetIssue,
      dropped_issues: [],
      dismissed_issues: [],
      invalidated: true,
      updated_at: new Date().toISOString(),
    };
    await $.fs.write(decisionPath, JSON.stringify(invalidEnvelope, null, 2));
  } catch {
    // Fail-open
  }
}

const decisionWriteQueues = new Map<number, Promise<void>>();

/**
 * Serializes decision file writes per target issue so rapid clicks cannot
 * finish out of order and overwrite newer pane state with an older snapshot.
 */
function enqueueDecisionSync(targetIssue: number, task: () => Promise<void>): Promise<void> {
  const prev = decisionWriteQueues.get(targetIssue) ?? Promise.resolve();
  const next = prev.then(task, task).finally(() => {
    if (decisionWriteQueues.get(targetIssue) === next) {
      decisionWriteQueues.delete(targetIssue);
    }
  });
  decisionWriteQueues.set(targetIssue, next);
  return next;
}

/**
 * Atomically updates the duplicatePickerState in the session store, stages
 * decisions to disk via $.fs.write when curated, and invalidates the UI.
 */
export async function updateDuplicatePickerState(
  $: any,
  updater: (prev: DuplicatePickerState | null) => DuplicatePickerState | null
): Promise<void> {
  try {
    let nextState: DuplicatePickerState | null = null;
    await update($, duplicatePickerState, (prev: any) => {
      nextState = updater(prev ?? null);
      return nextState;
    });

    if (nextState) {
      const targetIssue = (nextState as DuplicatePickerState).targetIssue;
      await enqueueDecisionSync(targetIssue, async () => {
        // Re-read the latest atom right before writing so rapid clicks write
        // only the newest state and never an older snapshot.
        const latest = await getDuplicatePickerState($);
        if (!latest || latest.targetIssue !== targetIssue) {
          return;
        }
        const decision = serializeDecision(latest);
        const syncResult = await safeWriteDecisionFile(
          $,
          latest.targetIssue,
          JSON.stringify(decision, null, 2),
          latest.candidatesPath
        );

        if (!syncResult.success) {
          // If write failed, record syncError on state and invalidate file on disk
          await invalidateDecisionFile($, latest.targetIssue, latest.candidatesPath);
          await update($, duplicatePickerState, (prev: any) => {
            if (!prev) return null;
            return {
              ...prev,
              syncError: syncResult.error || 'Failed to write decision file',
            };
          });
        } else if (latest.syncError) {
          // Clear syncError on successful write
          await update($, duplicatePickerState, (prev: any) => {
            if (!prev) return null;
            return {
              ...prev,
              syncError: null,
            };
          });
        }
      });
    }

    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in non-interactive/headless contexts
    }
  } catch {
    // Fail-open
  }
}

/**
 * Strips ANSI CSI and OSC sequences, zero-width characters, bidirectional overrides,
 * and C0/C1 control codes from untrusted external issue titles or excerpts.
 * Note: Legitimate syntax such as generic types (e.g. Map<String, Foo>) is preserved.
 */
export function sanitizeText(raw: unknown): string {
  if (typeof raw !== 'string') {
    return '';
  }
  return raw
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    // Zero-width (U+200B-U+200D, U+FEFF) and Bidirectional overrides (U+202A-U+202E, U+2066-U+2069)
    .replace(/[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]/g, '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .trim();
}

/**
 * Truncates text cleanly with an ellipsis.
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 1)).trimEnd()}\u2026`;
}

/**
 * Parses and validates an untrusted JSON candidate payload.
 */
export function parseCandidatePayload(raw: unknown): DuplicateCandidatePayload | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const obj = raw as Record<string, unknown>;
  if (obj.schema_version !== 1) {
    return null;
  }
  if (
    typeof obj.target_issue !== 'number' ||
    !Number.isInteger(obj.target_issue) ||
    obj.target_issue <= 0
  ) {
    return null;
  }
  const targetIssue = obj.target_issue;
  const targetTitle = sanitizeText(obj.target_title);
  if (!targetTitle) {
    return null;
  }
  const targetAuthor =
    sanitizeText(obj.target_author).replace(/^@+/, '') || undefined;
  const candidates: CandidateIssue[] = [];

  if (Array.isArray(obj.candidates)) {
    for (const item of obj.candidates) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        continue;
      }
      const c = item as Record<string, unknown>;
      if (
        typeof c.issue_number !== 'number' ||
        !Number.isInteger(c.issue_number) ||
        c.issue_number <= 0
      ) {
        continue;
      }
      const issueNum = c.issue_number;
      // Do not allow an issue to be a candidate duplicate of itself or duplicate existing candidates
      if (issueNum === targetIssue || candidates.some((existing) => existing.issue_number === issueNum)) {
        continue;
      }
      const title = sanitizeText(c.title);
      if (!title) {
        continue;
      }
      const author =
        sanitizeText(c.author).replace(/^@+/, '') || 'unknown';
      let score: number | undefined;
      if (
        typeof c.similarity_score === 'number' &&
        !Number.isNaN(c.similarity_score) &&
        c.similarity_score >= 0 &&
        c.similarity_score <= 1
      ) {
        score = c.similarity_score;
      }
      const createdAt = c.created_at
        ? truncateText(sanitizeText(c.created_at), 25)
        : undefined;
      const excerpt = c.excerpt ? sanitizeText(c.excerpt) : undefined;
      const labels = Array.isArray(c.labels)
        ? c.labels
            .map((l) => truncateText(sanitizeText(l), 20))
            .filter(Boolean)
            .slice(0, 4)
        : undefined;

      candidates.push({
        issue_number: issueNum,
        title,
        author,
        created_at: createdAt,
        similarity_score: score,
        labels: labels && labels.length > 0 ? labels : undefined,
        excerpt,
      });
    }
  }

  return {
    schema_version: 1,
    target_issue: targetIssue,
    target_title: targetTitle,
    target_author: targetAuthor,
    candidates,
  };
}

/**
 * Creates initial DuplicatePickerState from a validated payload.
 */
export function createStateFromPayload(payload: DuplicateCandidatePayload): DuplicatePickerState {
  return {
    targetIssue: payload.target_issue,
    targetTitle: payload.target_title,
    targetAuthor: payload.target_author,
    candidates: payload.candidates,
    selectedKeptIssue: null,
    dismissedIssues: [],
  };
}

export const MAX_VISIBLE_CANDIDATES = 10;

/**
 * Derives the decision status dynamically from the current maintainer selection.
 * Single source of truth shared by the serializer, footer, and tests.
 * Returns 'dismissed' only when every candidate (including overflow) is dismissed;
 * otherwise stays 'reviewing' so the skill falls back to CLI review for overflow.
 */
export function deriveStatus(
  state: DuplicatePickerState
): 'reviewing' | 'curated' | 'dismissed' {
  if (!state.candidates || state.candidates.length === 0) {
    return 'reviewing';
  }

  const allDismissed = state.candidates.every((c) =>
    state.dismissedIssues.includes(c.issue_number)
  );
  if (allDismissed) {
    return 'dismissed';
  }

  if (state.selectedKeptIssue !== null) {
    return 'curated';
  }

  return 'reviewing';
}

/**
 * Serializes the current maintainer selection into a standard DuplicatePickerDecision.
 * Restricts dropped candidates strictly to visible candidates that were rendered to the user.
 */
export function serializeDecision(
  state: DuplicatePickerState,
  nowIso = new Date().toISOString()
): DuplicatePickerDecision {
  const status = deriveStatus(state);
  const kept = state.selectedKeptIssue ?? state.targetIssue;
  const visible = (state.candidates || []).slice(0, MAX_VISIBLE_CANDIDATES);
  const pool = [state.targetIssue, ...visible.map((c) => c.issue_number)];
  // Only drop candidates that were rendered and not dismissed!
  const dropped =
    status === 'curated'
      ? Array.from(new Set(pool)).filter(
          (num) => num !== kept && !state.dismissedIssues.includes(num)
        )
      : [];

  return {
    schema_version: 1,
    target_issue: state.targetIssue,
    status,
    kept_issue: kept,
    dropped_issues: dropped,
    dismissed_issues: [...state.dismissedIssues],
    source_candidates_sha256: state.candidatesSha256 ?? null,
    updated_at: nowIso,
  };
}

/**
 * Formats a similarity score into a human-readable badge.
 */
export function formatSimilarityBadge(score?: number): {
  label: string;
  color: string;
} {
  if (score === undefined || score === null) {
    return { label: 'MATCH', color: 'dim' };
  }
  const pct = Math.round(score * 100);
  if (pct >= 85) {
    return { label: `${pct}% HIGH`, color: 'success' };
  }
  if (pct >= 65) {
    return { label: `${pct}% MED`, color: 'warning' };
  }
  return { label: `${pct}% LOW`, color: 'dim' };
}

/**
 * Renders the duplicate picker pane into Claude Code UI.
 */
export function renderDuplicatePickerPane(
  $: any,
  e: any,
  state: DuplicatePickerState | null
): any {
  if (!state || !state.candidates || state.candidates.length === 0) {
    return null;
  }

  let Box: any;
  let Text: any;
  let Button: any;

  try {
    const resolved = $.ui.resolve(e);
    Box = resolved.Box;
    Text = resolved.Text;
    Button = typeof resolved.Button === 'function' ? resolved.Button : undefined;
  } catch {
    return null;
  }

  if (!Box || !Text) {
    return null;
  }

  const items: any[] = [];
  const isTargetKept = state.selectedKeptIssue === state.targetIssue;

  // Header: Target issue with explicit canonical action and author
  const headerChildren: any[] = [
    Text({
      children: [
        state.targetAuthor
          ? `[Deduplication Target: #${state.targetIssue} (@${state.targetAuthor})]`
          : `[Deduplication Target: #${state.targetIssue}]`,
      ],
      bold: true,
      color: 'info',
    }),
    Text({
      children: [truncateText(state.targetTitle, 60)],
      color: 'dim',
    }),
  ];

  if (Button) {
    headerChildren.push(
      Box({
        flexDirection: 'row',
        marginTop: 1,
        children: [
          Button({
            key: `target-kept-${state.targetIssue}`,
            label: isTargetKept
              ? `Kept (Target #${state.targetIssue})`
              : `Keep Target #${state.targetIssue}`,
            onPress: async () => {
              await updateDuplicatePickerState($, (prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  selectedKeptIssue:
                    prev.selectedKeptIssue === prev.targetIssue ? null : prev.targetIssue,
                };
              });
            },
          }),
        ],
      })
    );
  }

  items.push(
    Box({
      flexDirection: 'column',
      marginBottom: 1,
      padding: 1,
      borderStyle: 'single',
      borderColor: isTargetKept ? 'green' : 'cyan',
      children: headerChildren,
    })
  );

  // Candidate list (capped at MAX_VISIBLE_CANDIDATES)
  const visibleCandidates = state.candidates.slice(0, MAX_VISIBLE_CANDIDATES);

  for (const c of visibleCandidates) {
    const isDismissed = state.dismissedIssues.includes(c.issue_number);
    const isKept = state.selectedKeptIssue === c.issue_number;
    const badge = formatSimilarityBadge(c.similarity_score);
    const authorTimestamp = c.created_at
      ? `(@${c.author} • ${c.created_at})`
      : `(@${c.author})`;

    const childElements: any[] = [
      Box({
        flexDirection: 'row',
        gap: 1,
        children: [
          Text({
            children: [`[${badge.label}]`],
            bold: true,
            color: badge.color,
          }),
          Text({
            children: [`#${c.issue_number}: ${truncateText(c.title, 40)}`],
            bold: true,
            strikethrough: isDismissed,
          }),
          Text({
            children: [authorTimestamp],
            color: 'dim',
          }),
        ],
      }),
    ];

    if (c.labels && c.labels.length > 0) {
      childElements.push(
        Text({
          children: [`  Labels: ${c.labels.join(', ')}`],
          color: 'dim',
        })
      );
    }

    if (c.excerpt) {
      childElements.push(
        Text({
          children: [`  ${truncateText(c.excerpt, 60)}`],
          color: 'dim',
        })
      );
    }

    // Interactive buttons if Button component exists
    if (Button) {
      const actions: any[] = [];
      if (isDismissed) {
        actions.push(
          Button({
            key: `restore-${c.issue_number}`,
            label: 'Restore',
            onPress: async () => {
              await updateDuplicatePickerState($, (prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  dismissedIssues: prev.dismissedIssues.filter(
                    (num) => num !== c.issue_number
                  ),
                };
              });
            },
          })
        );
      } else {
        actions.push(
          Button({
            key: `kept-${c.issue_number}`,
            label: isKept ? 'Kept (Canonical)' : 'Set as Kept',
            onPress: async () => {
              await updateDuplicatePickerState($, (prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  selectedKeptIssue:
                    prev.selectedKeptIssue === c.issue_number ? null : c.issue_number,
                };
              });
            },
          }),
          Button({
            key: `dismiss-${c.issue_number}`,
            label: 'Dismiss',
            onPress: async () => {
              await updateDuplicatePickerState($, (prev) => {
                if (!prev) return null;
                const nextDismissed = prev.dismissedIssues.includes(c.issue_number)
                  ? prev.dismissedIssues
                  : [...prev.dismissedIssues, c.issue_number];
                return {
                  ...prev,
                  dismissedIssues: nextDismissed,
                  selectedKeptIssue:
                    prev.selectedKeptIssue === c.issue_number ? null : prev.selectedKeptIssue,
                };
              });
            },
          })
        );
      }

      childElements.push(
        Box({
          flexDirection: 'row',
          gap: 1,
          marginTop: 1,
          children: actions,
        })
      );
    }

    items.push(
      Box({
        flexDirection: 'column',
        padding: 1,
        borderStyle: 'single',
        borderColor: isKept ? 'green' : isDismissed ? 'gray' : 'cyan',
        marginBottom: 1,
        children: childElements,
      })
    );
  }

  if (state.candidates.length > MAX_VISIBLE_CANDIDATES) {
    const remaining = state.candidates.length - MAX_VISIBLE_CANDIDATES;
    items.push(
      Box({
        flexDirection: 'row',
        padding: 1,
        marginBottom: 1,
        borderStyle: 'single',
        borderColor: 'gray',
        children: [
          Text({
            children: [
              `... and ${remaining} more candidate(s) (curate above or review via CLI)`,
            ],
            color: 'dim',
          }),
        ],
      })
    );
  }

  // Summary / Status footer
  const status = deriveStatus(state);
  const footerChildren: any[] = [
    Text({ children: ['Decision:'], bold: true }),
  ];

  if (status === 'curated') {
    const keptIssue = state.selectedKeptIssue ?? state.targetIssue;
    const pool = [state.targetIssue, ...visibleCandidates.map((c) => c.issue_number)];
    const dropped = Array.from(new Set(pool)).filter(
      (num) => num !== keptIssue && !state.dismissedIssues.includes(num)
    );
    footerChildren.push(
      Text({ children: [`Keep #${keptIssue} (Canonical)`], color: 'success' }),
      Text({
        children: [
          `(Drop ${dropped.length} ${dropped.length === 1 ? 'duplicate' : 'duplicates'}; ${state.dismissedIssues.length} dismissed)`,
        ],
        color: 'dim',
      })
    );
  } else if (status === 'dismissed') {
    footerChildren.push(
      Text({ children: ['All Candidates Dismissed (No duplicates)'], color: 'warning' })
    );
  } else {
    footerChildren.push(
      Text({ children: ['Reviewing (No selection yet - nothing will be dropped)'], color: 'dim' })
    );
  }

  items.push(
    Box({
      flexDirection: 'row',
      gap: 1,
      marginTop: 1,
      children: footerChildren,
    })
  );

  if (state.syncError) {
    items.push(
      Box({
        flexDirection: 'row',
        padding: 1,
        marginTop: 1,
        borderStyle: 'single',
        borderColor: 'yellow',
        children: [
          Text({
            children: [
              `[!] Warning: Curation sync failed (${state.syncError}). Staged decision invalidated; fall back to terminal prompt.`,
            ],
            color: 'warning',
            bold: true,
          }),
        ],
      })
    );
  }

  return Box({
    flexDirection: 'column',
    padding: 1,
    children: items,
  });
}

/**
 * Hydrates candidate state from disk and opens the interactive duplicate-picker pane.
 * If candidate content hash and target issue match active state, skips re-hydration
 * to preserve in-flight maintainer selections. Re-hydrates whenever the hash changes.
 */
export async function hydrateCandidatesFromFile($: any, filePath: string): Promise<boolean> {
  if (!filePath) {
    return false;
  }
  try {
    if ((await classifyWriteTarget($, filePath)) !== 'regular') {
      return false;
    }

    let content: string | null = null;
    try {
      content = await $.fs.read(filePath);
    } catch {
      return false;
    }

    if (!content || typeof content !== 'string' || content.trim().length === 0) {
      return false;
    }

    let parsedJson: unknown;
    try {
      parsedJson = JSON.parse(content);
    } catch {
      return false;
    }

    const payload = parseCandidatePayload(parsedJson);
    if (!payload) {
      return false;
    }

    const candidatesSha256 = computePayloadHash(content);
    const currentState = await getDuplicatePickerState($);
    if (
      currentState &&
      currentState.targetIssue === payload.target_issue &&
      currentState.candidatesSha256 === candidatesSha256 &&
      currentState.candidates &&
      currentState.candidates.length > 0
    ) {
      // Same-hash re-hydration still starts a new run: invalidate any leftover
      // decision file on disk so Step 2 cannot reuse it without a new click.
      await invalidateDecisionFile($, payload.target_issue, filePath);
      if (currentState.candidatesPath !== filePath) {
        await setDuplicatePickerState($, {
          ...currentState,
          candidatesPath: filePath,
        });
      }
      return true;
    }

    // Fresh hydration: invalidate any leftover decision file from a prior or cancelled run
    await invalidateDecisionFile($, payload.target_issue, filePath);

    const state: DuplicatePickerState = {
      ...createStateFromPayload(payload),
      candidatesSha256,
      candidatesPath: filePath,
    };
    await setDuplicatePickerState($, state);

    try {
      await $.ui.open({
        id: 'duplicate-picker',
        title: `Duplicate Candidates (#${payload.target_issue})`,
      });
    } catch {
      // Fail-open in non-interactive/headless contexts
    }

    return true;
  } catch {
    return false;
  }
}

/**
 * Validates that a candidate file path is strictly within the workspace directory
 * and does not attempt directory traversal or target external paths.
 */
export function isWorkspaceCandidatePath(filePath: string, targetIssue: number, wsRoot?: string): boolean {
  if (!filePath || typeof filePath !== 'string') return false;
  const expected = `.magpie-issue-candidates-${targetIssue}.json`;
  const normalized = filePath.replace(/\\/g, '/');

  const segments = normalized.split('/');
  if (segments.includes('..')) {
    return false;
  }

  if (
    normalized === expected ||
    normalized === `./${expected}` ||
    (!normalized.includes('/') && normalized === expected)
  ) {
    return true;
  }

  if (wsRoot && typeof wsRoot === 'string') {
    const cleanWs = wsRoot.replace(/\\/g, '/').replace(/\/+$/, '');
    if (cleanWs && normalized === `${cleanWs}/${expected}`) {
      return true;
    }
  }

  return false;
}

/**
 * Intercepts Bash tool calls that produce duplicate candidate session files.
 * Re-hydrates candidate state, letting hydrateCandidatesFromFile check content hashes.
 */
export async function handleBashToolCall($: any, e: any, next: any): Promise<any> {
  if (e && typeof e.command === 'string') {
    await updateIssueSweepOnBash($, e.command);
  }

  let result: any;
  if (typeof next === 'function') {
    result = await next(e);
  }

  if (e && typeof e.command === 'string') {
    try {
      const command = e.command;
      const match = /\.magpie-issue-candidates-(\d+)\.json/.exec(command);
      if (match && match[1]) {
        const targetIssue = parseInt(match[1], 10);
        const fileName = `.magpie-issue-candidates-${targetIssue}.json`;
        let targetPath = fileName;
        try {
          const cwd = await $.session.cwd();
          const cwdNorm = typeof cwd === 'string' ? normalizeAbsolutePath(cwd) : null;
          if (cwdNorm && cwdNorm !== '/') {
            const absPath = `${cwdNorm}/${fileName}`;
            if (await $.fs.exists(absPath)) {
              targetPath = absPath;
            }
          }
        } catch {
          // Fall back to relative path when $.session.cwd() is unavailable
        }
        let exists = false;
        try {
          exists = await $.fs.exists(targetPath);
        } catch {
          exists = false;
        }
        if (exists) {
          await hydrateCandidatesFromFile($, targetPath);
        }
      }
    } catch {
      // Fail-open
    }
  }

  return result;
}

/**
 * Normalizes an absolute POSIX or Windows drive path, refusing relative paths,
 * `..` segments, trailing slashes, and non-drive backslashes.
 */
export function normalizeAbsolutePath(path: string): string | null {
  if (path.endsWith('/') || path.endsWith('\\')) return null;
  if (path.includes('\\') && !/^[A-Za-z]:\\/.test(path)) return null;
  const p = path.replace(/\\/g, '/');
  const drive = /^[A-Za-z]:\//.exec(p);
  const prefix = drive ? drive[0].slice(0, 2) : '';
  const rest = drive ? p.slice(2) : p;
  if (!rest.startsWith('/')) return null;
  const parts = rest.split('/').filter((s) => s !== '' && s !== '.');
  if (parts.includes('..')) return null;
  return `${prefix}/${parts.join('/')}`;
}

/**
 * Returns the deepest normalized session root that `path` sits under, or null.
 */
export function allowedRootFor(
  path: string,
  sessionRoots: readonly (string | undefined)[]
): string | null {
  const target = normalizeAbsolutePath(path);
  if (!target) return null;
  const roots = sessionRoots
    .map((r) => (r ? normalizeAbsolutePath(r) : null))
    .filter((r): r is string => Boolean(r) && r !== '/')
    .filter((r) => target.startsWith(`${r}/`))
    .sort((a, b) => b.length - a.length);
  return roots[0] ?? null;
}

/**
 * Resolves the session working directory and root, each undefined when unavailable.
 */
async function sessionRootsOf($: any): Promise<(string | undefined)[]> {
  const roots: (string | undefined)[] = [];
  try {
    roots.push(await $.session.cwd());
  } catch {
    roots.push(undefined);
  }
  try {
    roots.push(await $.session.root());
  } catch {
    roots.push(undefined);
  }
  return roots;
}

/**
 * Intercepts Write tool calls that write duplicate candidate session files.
 * Ignores writes outside the session root and re-hydrates candidate state.
 */
export async function handleWriteToolCall($: any, e: any, next: any): Promise<any> {
  let result: any;
  if (typeof next === 'function') {
    result = await next(e);
  }

  if (e) {
    try {
      const filePath =
        typeof e.file_path === 'string'
          ? e.file_path
          : typeof e.path === 'string'
          ? e.path
          : typeof e.filePath === 'string'
          ? e.filePath
          : undefined;

      if (filePath) {
        const match = /\.magpie-issue-candidates-(\d+)\.json$/.exec(filePath);
        if (match && match[1]) {
          const targetIssue = parseInt(match[1], 10);
          const normalized = normalizeAbsolutePath(filePath);
          let targetPath: string | null = null;

          if (normalized !== null) {
            const roots = await sessionRootsOf($);
            const wsRoot = allowedRootFor(normalized, roots);
            if (wsRoot && isWorkspaceCandidatePath(normalized, targetIssue, wsRoot)) {
              targetPath = normalized;
            }
          } else if (isWorkspaceCandidatePath(filePath, targetIssue)) {
            targetPath = `.magpie-issue-candidates-${targetIssue}.json`;
          }

          if (targetPath) {
            let exists = false;
            try {
              exists = await $.fs.exists(targetPath);
            } catch {
              exists = false;
            }
            if (exists) {
              await hydrateCandidatesFromFile($, targetPath);
            }
          }
        }
      }
    } catch {
      // Fail-open
    }
  }

  return result;
}

/**
 * Registers the magpie-issue duplicate-picker mod hooks.
 */
export function register(hooks: any): void {
  hooks('session.start', async ($: any, e: any, next: any) => {
    try {
      await setDuplicatePickerState($, null);
    } catch {
      // Fail-open
    }
    try {
      await setIssueSweepProgressState($, null);
    } catch {
      // Fail-open
    }
    if (typeof next === 'function') {
      return next(e);
    }
  });

  hooks('ui.render', { component: 'Pane' }, async ($: any, e: any, next: any) => {
    try {
      if (e) {
        if (e.requestId && e.requestId !== 'duplicate-picker') {
          return typeof next === 'function' ? next(e) : undefined;
        }
        if (e.id && e.id !== 'duplicate-picker') {
          return typeof next === 'function' ? next(e) : undefined;
        }
      }
      const state = await getDuplicatePickerState($);
      const pane = renderDuplicatePickerPane($, e, state);
      if (pane) {
        return pane;
      }
    } catch {
      // Fail-open
    }
    if (typeof next === 'function') {
      return next(e);
    }
  });

  hooks('ui.render', { component: 'AbovePrompt' }, handleRenderAbovePrompt);
  hooks('tool.call', { tool: 'Bash' }, handleBashToolCall);
  hooks('tool.call', { tool: 'Write' }, handleWriteToolCall);
}

export default register;
