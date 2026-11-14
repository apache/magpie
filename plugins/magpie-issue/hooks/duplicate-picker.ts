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
} from './types.js';

export const duplicatePickerState = atom(
  { plugin: 'magpie-issue', key: 'duplicatePickerState' },
  null as DuplicatePickerState | null
);

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
 * Atomically updates the duplicatePickerState in the session store and invalidates the UI.
 */
export async function updateDuplicatePickerState(
  $: any,
  updater: (prev: DuplicatePickerState | null) => DuplicatePickerState | null
): Promise<void> {
  try {
    await update($, duplicatePickerState, (prev: any) => updater(prev ?? null));
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
  const targetAuthor = sanitizeText(obj.target_author) || undefined;
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
      const author = sanitizeText(c.author) || 'unknown';
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

/**
 * Derives the decision status dynamically from the current maintainer selection.
 * Single source of truth shared by the serializer, footer, and tests.
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
 */
export function serializeDecision(
  state: DuplicatePickerState,
  nowIso = new Date().toISOString()
): DuplicatePickerDecision {
  const status = deriveStatus(state);
  const kept = state.selectedKeptIssue ?? state.targetIssue;
  const pool = [state.targetIssue, ...state.candidates.map((c) => c.issue_number)];
  // Only drop candidates if the maintainer actually made a curated selection!
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

  // Header: Target issue with explicit canonical action
  const headerChildren: any[] = [
    Text({
      children: [`[Deduplication Target: #${state.targetIssue}]`],
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

  // Candidate list
  for (const c of state.candidates) {
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
                  dismissedIssues: prev.dismissedIssues.filter((id) => id !== c.issue_number),
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

  // Summary / Status footer
  const status = deriveStatus(state);
  const footerChildren: any[] = [
    Text({ children: ['Decision:'], bold: true }),
  ];

  if (status === 'curated') {
    const keptIssue = state.selectedKeptIssue ?? state.targetIssue;
    const pool = [state.targetIssue, ...state.candidates.map((c) => c.issue_number)];
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

  return Box({
    flexDirection: 'column',
    padding: 1,
    children: items,
  });
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
    if (typeof next === 'function') {
      return next(e);
    }
  });

  hooks('ui.render', { component: 'Pane' }, async ($: any, e: any, next: any) => {
    try {
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
}

export default register;
