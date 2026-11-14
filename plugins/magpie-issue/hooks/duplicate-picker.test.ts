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

import { describe, test } from 'claude-code/testing';
import type {
  DuplicatePickerState,
} from './types.js';

import {
  createStateFromPayload,
  deriveStatus,
  formatSimilarityBadge,
  getDuplicatePickerState,
  parseCandidatePayload,
  register,
  renderDuplicatePickerPane,
  sanitizeText,
  serializeDecision,
  setDuplicatePickerState,
  truncateText,
  updateDuplicatePickerState,
} from './duplicate-picker.js';

function must<T>(v: T | null | undefined, what = 'value'): T {
  if (v === null || v === undefined) throw new Error(`missing ${what}`);
  return v;
}

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
  return {
    state: {
      get: (atom: any) => {
        return { isSet: store.has(atom.key), value: store.has(atom.key) ? store.get(atom.key) : null };
      },
      set: (atom: any, wrapped: any) => {
        const prev = store.has(atom.key) ? store.get(atom.key) : null;
        const nextVal =
          typeof wrapped === 'function'
            ? wrapped(prev)
            : wrapped && typeof wrapped === 'object' && 'value' in wrapped
              ? wrapped.value
              : wrapped;
        store.set(atom.key, nextVal);
        return { isSet: true, value: nextVal };
      },
    },
    ui: {
      invalidate: () => {},
      resolve: () => ({}),
    },
    ...overrides,
  };
}

describe('sanitizeText', () => {
  test('preserves generic types and HTML-like syntax without tag stripping', () => {
    const title = 'NullPointerException in Map<String, Foo<Bar>> parsing';
    const clean = sanitizeText(title);
    if (clean !== title) {
      throw new Error(`expected generic brackets preserved, got: ${clean}`);
    }
    const comparison = 'check if a < b and c > d';
    if (sanitizeText(comparison) !== comparison) {
      throw new Error(`comparison brackets broken: ${sanitizeText(comparison)}`);
    }
  });

  test('strips ANSI escape sequences and control characters', () => {
    const ansi = '\x1b[31mRed Alert\x1b[0m\x00\x1f';
    const clean = sanitizeText(ansi);
    if (clean !== 'Red Alert') {
      throw new Error(`failed to strip ANSI/control chars: ${JSON.stringify(clean)}`);
    }
  });

  test('strips zero-width characters and bidirectional overrides', () => {
    // U+200B (zero-width space), U+202E (right-to-left override), U+2066 (left-to-right isolate)
    const bidiAttack = 'Normal Title \u202E\u2066reordered\u200Btext';
    const clean = sanitizeText(bidiAttack);
    if (clean !== 'Normal Title reorderedtext') {
      throw new Error(`failed to strip bidi overrides/zero-width: ${JSON.stringify(clean)}`);
    }
  });

  test('normalizes whitespace and newlines cleanly', () => {
    const multiline = 'Title\nLine2\r\nLine3\tExtra';
    const clean = sanitizeText(multiline);
    if (clean !== 'Title Line2 Line3 Extra') {
      throw new Error(`failed newline normalization: ${JSON.stringify(clean)}`);
    }
  });

  test('handles non-string gracefully', () => {
    if (sanitizeText(null) !== '' || sanitizeText(undefined) !== '' || sanitizeText(123) !== '') {
      throw new Error('failed non-string handling');
    }
  });
});

describe('truncateText', () => {
  test('truncates strings longer than maxLength with ellipsis', () => {
    const res = truncateText('Hello World Long Text', 10);
    if (!res.endsWith('\u2026') || res.length > 10) {
      throw new Error(`truncateText failed: ${res}`);
    }
  });

  test('leaves short strings untouched', () => {
    const res = truncateText('Short', 10);
    if (res !== 'Short') {
      throw new Error(`truncateText altered short string: ${res}`);
    }
  });
});

describe('parseCandidatePayload', () => {
  test('accepts valid schema_version 1 payload', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Original Bug with Map<String, Object>',
      target_author: 'bob',
      candidates: [
        {
          issue_number: 99,
          title: 'Duplicate Bug in Map<String, Object>',
          author: 'alice',
          similarity_score: 0.92,
          labels: ['bug', 'triage'],
          excerpt: 'Fails with 500 error',
        },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    if (parsed.target_issue !== 100 || parsed.candidates.length !== 1) {
      throw new Error(`unexpected parsed payload: ${JSON.stringify(parsed)}`);
    }
    if (parsed.candidates[0].similarity_score !== 0.92) {
      throw new Error(`similarity score mismatch: ${parsed.candidates[0].similarity_score}`);
    }
    if (parsed.candidates[0].title !== 'Duplicate Bug in Map<String, Object>') {
      throw new Error(`title brackets altered: ${parsed.candidates[0].title}`);
    }
  });

  test('strictly validates integer issue numbers and rejects coercions', () => {
    if (parseCandidatePayload({ schema_version: 1, target_issue: true, target_title: 'Bug' }) !== null) {
      throw new Error('should reject boolean target_issue');
    }
    if (parseCandidatePayload({ schema_version: 1, target_issue: [100], target_title: 'Bug' }) !== null) {
      throw new Error('should reject array target_issue');
    }
    if (parseCandidatePayload({ schema_version: 1, target_issue: 1.5, target_title: 'Bug' }) !== null) {
      throw new Error('should reject float target_issue');
    }
    if (parseCandidatePayload({ schema_version: 1, target_issue: -1, target_title: 'Bug' }) !== null) {
      throw new Error('should reject negative issue numbers');
    }
    if (parseCandidatePayload({ schema_version: 2, target_issue: 100, target_title: 'Bug' }) !== null) {
      throw new Error('should reject schema_version != 1');
    }
  });

  test('filters out self-duplicate candidate (issue_number === target_issue)', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Target Bug',
      candidates: [
        { issue_number: 100, title: 'Self Duplicate Bug', author: 'attacker' },
        { issue_number: 95, title: 'Real Candidate', author: 'charlie' },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    if (parsed.candidates.length !== 1 || parsed.candidates[0].issue_number !== 95) {
      throw new Error(`failed to filter out self-duplicate candidate: ${JSON.stringify(parsed.candidates)}`);
    }
  });

  test('deduplicates candidate entries with identical issue_number', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Target Bug',
      candidates: [
        { issue_number: 95, title: 'Duplicate Candidate First', author: 'alice' },
        { issue_number: 95, title: 'Duplicate Candidate Second', author: 'alice' },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    if (parsed.candidates.length !== 1 || parsed.candidates[0].title !== 'Duplicate Candidate First') {
      throw new Error(`failed to deduplicate candidate issue numbers: ${JSON.stringify(parsed.candidates)}`);
    }
  });

  test('range-checks similarity_score to [0.0, 1.0] and drops invalid values', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Target Bug',
      candidates: [
        { issue_number: 1, title: 'C1', similarity_score: NaN },
        { issue_number: 2, title: 'C2', similarity_score: 5.0 },
        { issue_number: 3, title: 'C3', similarity_score: -0.5 },
        { issue_number: 4, title: 'C4', similarity_score: 0.85 },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    if (parsed.candidates[0].similarity_score !== undefined) {
      throw new Error('NaN similarity_score should be dropped');
    }
    if (parsed.candidates[1].similarity_score !== undefined) {
      throw new Error('>1 similarity_score should be dropped');
    }
    if (parsed.candidates[2].similarity_score !== undefined) {
      throw new Error('<0 similarity_score should be dropped');
    }
    if (parsed.candidates[3].similarity_score !== 0.85) {
      throw new Error(`valid score 0.85 should be retained, got ${parsed.candidates[3].similarity_score}`);
    }
  });

  test('handles non-string author safely', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Bug',
      candidates: [
        { issue_number: 1, title: 'C1', author: {} },
        { issue_number: 2, title: 'C2', author: '   ' },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    if (parsed.candidates[0].author !== 'unknown' || parsed.candidates[1].author !== 'unknown') {
      throw new Error(`failed safe author fallback: ${JSON.stringify(parsed.candidates)}`);
    }
  });

  test('truncates created_at to 25 chars and bounds labels to max 4 items and 20 chars each', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Bug',
      candidates: [
        {
          issue_number: 1,
          title: 'C1',
          created_at: '2026-11-14T06:29:33.123456789Z-EXTRA-PADDING',
          labels: [
            'label-one-very-long-name-exceeding-twenty-characters',
            'label-two',
            'label-three',
            'label-four',
            'label-five-should-be-dropped',
          ],
        },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    const c = parsed.candidates[0];
    if (!c.created_at || c.created_at.length > 25) {
      throw new Error(`created_at should be <= 25 chars, got length ${c.created_at?.length}: ${c.created_at}`);
    }
    if (!c.labels || c.labels.length > 4) {
      throw new Error(`labels should be at most 4 items, got ${c.labels?.length}`);
    }
    if (c.labels[0].length > 20) {
      throw new Error(`label should be <= 20 chars, got length ${c.labels[0].length}: ${c.labels[0]}`);
    }
    if (c.labels.includes('label-five-should-be-dropped')) {
      throw new Error('5th label should have been dropped');
    }
  });
});

describe('createStateFromPayload', () => {
  test('creates fresh DuplicatePickerState with empty selections', () => {
    const payload = {
      schema_version: 1 as const,
      target_issue: 200,
      target_title: 'Target Issue Title',
      target_author: 'reporter',
      candidates: [
        { issue_number: 199, title: 'Candidate 199', author: 'dev' },
      ],
    };
    const state = createStateFromPayload(payload);
    if (state.targetIssue !== 200 || state.targetTitle !== 'Target Issue Title') {
      throw new Error(`target mismatch: ${JSON.stringify(state)}`);
    }
    if (deriveStatus(state) !== 'reviewing') {
      throw new Error(`expected reviewing status from deriveStatus, got ${deriveStatus(state)}`);
    }
    if (state.selectedKeptIssue !== null) {
      throw new Error(`expected selectedKeptIssue null, got ${state.selectedKeptIssue}`);
    }
    if (state.dismissedIssues.length !== 0) {
      throw new Error(`expected empty dismissedIssues, got ${JSON.stringify(state.dismissedIssues)}`);
    }
  });
});

describe('deriveStatus', () => {
  test('returns reviewing when candidates list is empty regardless of selection', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [],
      selectedKeptIssue: 100,
      dismissedIssues: [],
    };
    if (deriveStatus(state) !== 'reviewing') {
      throw new Error(`expected reviewing for empty candidates, got ${deriveStatus(state)}`);
    }
  });

  test('returns reviewing when no selection has been made and candidates are not all dismissed', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'C1', author: 'a' },
        { issue_number: 91, title: 'C2', author: 'b' },
      ],
      selectedKeptIssue: null,
      dismissedIssues: [90],
    };
    if (deriveStatus(state) !== 'reviewing') {
      throw new Error(`expected reviewing, got ${deriveStatus(state)}`);
    }
  });

  test('returns curated when target or candidate is selected and un-dismissed candidates remain', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'C1', author: 'a' },
        { issue_number: 91, title: 'C2', author: 'b' },
      ],
      selectedKeptIssue: 100,
      dismissedIssues: [90],
    };
    if (deriveStatus(state) !== 'curated') {
      throw new Error(`expected curated, got ${deriveStatus(state)}`);
    }
  });

  test('returns dismissed when all candidates are dismissed even if target was kept', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'C1', author: 'a' },
      ],
      selectedKeptIssue: 100, // Target was kept, but the only candidate was dismissed!
      dismissedIssues: [90],
    };
    if (deriveStatus(state) !== 'dismissed') {
      throw new Error(`expected dismissed when all candidates dismissed, got ${deriveStatus(state)}`);
    }
  });
});

describe('serializeDecision', () => {
  test('untouched reviewing state serializes as reviewing with zero dropped issues', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'Candidate 1', author: 'a' },
        { issue_number: 91, title: 'Candidate 2', author: 'b' },
      ],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };
    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.status !== 'reviewing') {
      throw new Error(`expected reviewing status for untouched state, got ${dec.status}`);
    }
    if (dec.dropped_issues.length !== 0) {
      throw new Error(`expected dropped_issues empty for untouched state, got ${JSON.stringify(dec.dropped_issues)}`);
    }
  });

  test('serializes curated decision when target issue is explicitly kept', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'Candidate 1', author: 'a' },
        { issue_number: 91, title: 'Candidate 2', author: 'b' },
      ],
      selectedKeptIssue: 100,
      dismissedIssues: [91],
    };
    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.kept_issue !== 100) {
      throw new Error(`expected kept_issue 100, got ${dec.kept_issue}`);
    }
    if (dec.dropped_issues.length !== 1 || dec.dropped_issues[0] !== 90) {
      throw new Error(`expected dropped_issues [90], got ${JSON.stringify(dec.dropped_issues)}`);
    }
    if (dec.dismissed_issues.length !== 1 || dec.dismissed_issues[0] !== 91) {
      throw new Error(`expected dismissed_issues [91], got ${JSON.stringify(dec.dismissed_issues)}`);
    }
    if (dec.status !== 'curated') {
      throw new Error(`expected status curated, got ${dec.status}`);
    }
  });

  test('serializes custom candidate as kept issue and drops target', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [{ issue_number: 90, title: 'Candidate 1', author: 'a' }],
      selectedKeptIssue: 90,
      dismissedIssues: [],
    };
    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.kept_issue !== 90) {
      throw new Error(`expected kept_issue 90, got ${dec.kept_issue}`);
    }
    if (!dec.dropped_issues.includes(100) || dec.dropped_issues.includes(90)) {
      throw new Error(`expected dropped_issues to contain target 100 and not 90, got ${JSON.stringify(dec.dropped_issues)}`);
    }
    if (dec.status !== 'curated') {
      throw new Error(`expected status curated, got ${dec.status}`);
    }
  });

  test('serializes dismissed status with zero dropped issues when all candidates dismissed', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'Candidate 1', author: 'a' },
      ],
      selectedKeptIssue: 100,
      dismissedIssues: [90],
    };
    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.status !== 'dismissed') {
      throw new Error(`expected dismissed status, got ${dec.status}`);
    }
    if (dec.dropped_issues.length !== 0) {
      throw new Error(`expected no dropped issues on dismissed, got ${JSON.stringify(dec.dropped_issues)}`);
    }
  });

  test('does not serialize dismissed if dismissedIssues has extraneous IDs not matching candidates', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [
        { issue_number: 90, title: 'Candidate 1', author: 'a' },
      ],
      selectedKeptIssue: null,
      dismissedIssues: [999],
    };
    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.status !== 'reviewing') {
      throw new Error(`expected reviewing status when candidate 90 not dismissed, got ${dec.status}`);
    }
  });
});

describe('formatSimilarityBadge', () => {
  test('categorizes high, med, low scores correctly', () => {
    const high = formatSimilarityBadge(0.9);
    if (!high.label.includes('HIGH') || high.color !== 'success') {
      throw new Error(`expected HIGH badge: ${JSON.stringify(high)}`);
    }
    const med = formatSimilarityBadge(0.7);
    if (!med.label.includes('MED') || med.color !== 'warning') {
      throw new Error(`expected MED badge: ${JSON.stringify(med)}`);
    }
    const low = formatSimilarityBadge(0.4);
    if (!low.label.includes('LOW')) {
      throw new Error(`expected LOW badge: ${JSON.stringify(low)}`);
    }
    const none = formatSimilarityBadge(undefined);
    if (none.label !== 'MATCH' || none.color !== 'dim') {
      throw new Error(`expected default match badge: ${JSON.stringify(none)}`);
    }
  });
});

describe('renderDuplicatePickerPane', () => {
  test('returns null when state is absent or has zero candidates', () => {
    const mock$ = { ui: { resolve: () => ({ Box: () => {}, Text: () => {} }) } };
    if (renderDuplicatePickerPane(mock$, {}, null) !== null) {
      throw new Error('should return null for null state');
    }
    const emptyState: DuplicatePickerState = {
      targetIssue: 1,
      targetTitle: 'Empty',
      candidates: [],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };
    if (renderDuplicatePickerPane(mock$, {}, emptyState) !== null) {
      throw new Error('should return null for empty candidates');
    }
  });

  test('constructs structured Box tree with single-argument props and children', () => {
    let boxCalls = 0;
    let textCalls = 0;
    let buttonCalls = 0;

    const mockBox = (props: any) => {
      boxCalls += 1;
      return { type: 'Box', ...props };
    };

    const mockText = (props: any) => {
      textCalls += 1;
      return { type: 'Text', ...props };
    };

    const mockButton = (props: any) => {
      buttonCalls += 1;
      return { type: 'Button', ...props };
    };

    const mock$ = {
      ui: {
        resolve: () => ({
          Box: mockBox,
          Text: mockText,
          Button: mockButton,
        }),
      },
    };

    const state: DuplicatePickerState = {
      targetIssue: 50,
      targetTitle: 'Target Issue Title with Map<String, Object>',
      targetAuthor: 'alice',
      candidates: [
        {
          issue_number: 48,
          title: 'Candidate Duplicate Title',
          author: 'bob',
          created_at: '2026-11-14T06:29:33Z',
          labels: ['area:issue', 'bug'],
          similarity_score: 0.88,
          excerpt: 'Matches stack trace',
        },
      ],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };

    const pane = renderDuplicatePickerPane(mock$, { component: 'Pane' }, state);
    if (!pane || pane.type !== 'Box') {
      throw new Error(`expected rendered Box root, got ${JSON.stringify(pane)}`);
    }
    if (boxCalls === 0 || textCalls === 0 || buttonCalls === 0) {
      throw new Error(`expected all components invoked, got box=${boxCalls}, text=${textCalls}, button=${buttonCalls}`);
    }
    if (!Array.isArray(pane.children)) {
      throw new Error('pane should contain children array in props');
    }
  });

  test('button onPress handlers trigger atomic state updates, selection toggle, and restore', async () => {
    const buttons: Array<{ key: string; label: string; onPress: () => Promise<void> }> = [];

    const mockBox = (props: any) => ({ type: 'Box', ...props });
    const mockText = (props: any) => ({ type: 'Text', ...props });
    const mockButton = (props: any) => {
      buttons.push(props);
      return { type: 'Button', ...props };
    };

    const test$ = createMockEngine({
      ui: {
        resolve: () => ({
          Box: mockBox,
          Text: mockText,
          Button: mockButton,
        }),
        invalidate: () => {},
      },
    });

    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target Title',
      candidates: [
        { issue_number: 99, title: 'Candidate 99', author: 'alice' },
      ],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };

    await setDuplicatePickerState(test$, state);
    renderDuplicatePickerPane(test$, { component: 'Pane' }, state);

    // 1. Keep Target button onPress -> selects target 100
    const targetBtn = buttons.find((b) => b.key === 'target-kept-100');
    if (!targetBtn) throw new Error('Keep Target button missing');
    await targetBtn.onPress();
    let current = await getDuplicatePickerState(test$);
    if (!current || current.selectedKeptIssue !== 100 || deriveStatus(current) !== 'curated') {
      throw new Error(`Target button onPress failed: ${JSON.stringify(current)}`);
    }

    // 2. Toggle Target button onPress -> toggles selection back to null
    await targetBtn.onPress();
    current = await getDuplicatePickerState(test$);
    if (!current || current.selectedKeptIssue !== null || deriveStatus(current) !== 'reviewing') {
      throw new Error(`Target button toggle unselect failed: ${JSON.stringify(current)}`);
    }

    // 3. Set as Kept button onPress on candidate 99 -> selects candidate 99
    const keptBtn = buttons.find((b) => b.key === 'kept-99');
    if (!keptBtn) throw new Error('Set as Kept button missing');
    await keptBtn.onPress();
    current = await getDuplicatePickerState(test$);
    if (!current || current.selectedKeptIssue !== 99 || deriveStatus(current) !== 'curated') {
      throw new Error(`Candidate kept button onPress failed: ${JSON.stringify(current)}`);
    }

    // 4. Toggle Candidate button onPress -> toggles selection back to null
    await keptBtn.onPress();
    current = await getDuplicatePickerState(test$);
    if (!current || current.selectedKeptIssue !== null) {
      throw new Error(`Candidate kept button toggle unselect failed: ${JSON.stringify(current)}`);
    }

    // 5. Dismiss button onPress on candidate 99
    const dismissBtn = buttons.find((b) => b.key === 'dismiss-99');
    if (!dismissBtn) throw new Error('Dismiss button missing');
    await dismissBtn.onPress();
    current = await getDuplicatePickerState(test$);
    if (!current || !current.dismissedIssues.includes(99) || deriveStatus(current) !== 'dismissed') {
      throw new Error(`Dismiss button onPress failed: ${JSON.stringify(current)}`);
    }

    // 6. Render again with candidate 99 dismissed -> should render a Restore button!
    buttons.length = 0;
    renderDuplicatePickerPane(test$, { component: 'Pane' }, current);
    const restoreBtn = buttons.find((b) => b.key === 'restore-99');
    if (!restoreBtn) throw new Error('Restore button missing for dismissed candidate 99');
    await restoreBtn.onPress();
    current = await getDuplicatePickerState(test$);
    if (!current || current.dismissedIssues.includes(99) || deriveStatus(current) !== 'reviewing') {
      throw new Error(`Restore button onPress failed: ${JSON.stringify(current)}`);
    }
  });

  test('rapid sequential button presses in same render persist both updates without race conditions', async () => {
    const buttons: Array<{ key: string; label: string; onPress: () => Promise<void> }> = [];

    const mockBox = (props: any) => ({ type: 'Box', ...props });
    const mockText = (props: any) => ({ type: 'Text', ...props });
    const mockButton = (props: any) => {
      buttons.push(props);
      return { type: 'Button', ...props };
    };

    const test$ = createMockEngine({
      ui: {
        resolve: () => ({ Box: mockBox, Text: mockText, Button: mockButton }),
        invalidate: () => {},
      },
    });

    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target Title',
      candidates: [
        { issue_number: 98, title: 'Candidate 98', author: 'alice' },
        { issue_number: 99, title: 'Candidate 99', author: 'bob' },
      ],
      selectedKeptIssue: 100,
      dismissedIssues: [],
    };

    await setDuplicatePickerState(test$, state);
    renderDuplicatePickerPane(test$, { component: 'Pane' }, state);

    const dismiss98 = buttons.find((b) => b.key === 'dismiss-98');
    const dismiss99 = buttons.find((b) => b.key === 'dismiss-99');
    if (!dismiss98 || !dismiss99) throw new Error('Dismiss buttons missing');

    await dismiss98.onPress();
    await dismiss99.onPress();

    const current = await getDuplicatePickerState(test$);
    if (!current) throw new Error('state null after rapid presses');
    if (!current.dismissedIssues.includes(98) || !current.dismissedIssues.includes(99)) {
      throw new Error(`expected both 98 and 99 dismissed, got: ${JSON.stringify(current.dismissedIssues)}`);
    }
    if (deriveStatus(current) !== 'dismissed') {
      throw new Error(`expected dismissed status when all candidates dismissed, got: ${deriveStatus(current)}`);
    }
  });
});

describe('register', () => {
  test('registers session.start and ui.render (Pane) lifecycle hooks cleanly', () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    const fakeOn = (event: string, optsOrHandler: any, handler?: Function) => {
      if (typeof optsOrHandler === 'function') {
        registered.push({ event, handler: optsOrHandler });
      } else {
        registered.push({ event, opts: optsOrHandler, handler: handler! });
      }
    };

    register(fakeOn);
    if (registered.length < 2) {
      throw new Error(`expected at least 2 hooks, got ${registered.length}`);
    }
    const sessionHook = registered.find((r) => r.event === 'session.start');
    if (!sessionHook) {
      throw new Error('missing session.start hook');
    }
    const renderHook = registered.find((r) => r.event === 'ui.render');
    if (!renderHook || renderHook.opts?.component !== 'Pane') {
      throw new Error('ui.render hook missing or missing { component: "Pane" } matcher');
    }
  });

  test('ui.render lifecycle handler returns next(e) on empty atom state', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const renderHook = registered.find((r) => r.event === 'ui.render')!;

    const test$ = createMockEngine();
    let nextCalled = false;
    const testE = { component: 'Pane', id: 'main' };
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { passedThrough: true, e };
    };

    const result = await renderHook.handler(test$, testE, nextSpy);
    if (!nextCalled || !result || !result.passedThrough) {
      throw new Error('ui.render failed to call next(e) on empty state');
    }
  });

  test('ui.render lifecycle handler returns rendered Pane on populated atom state', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const renderHook = registered.find((r) => r.event === 'ui.render')!;

    const mockBox = (props: any) => ({ type: 'Box', ...props });
    const mockText = (props: any) => ({ type: 'Text', ...props });
    const mockButton = (props: any) => ({ type: 'Button', ...props });

    const test$ = createMockEngine({
      ui: {
        resolve: () => ({ Box: mockBox, Text: mockText, Button: mockButton }),
        invalidate: () => {},
      },
    });

    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target Title',
      candidates: [{ issue_number: 99, title: 'C99', author: 'alice' }],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };
    await setDuplicatePickerState(test$, state);

    let nextCalled = false;
    const nextSpy = () => {
      nextCalled = true;
      return { passedThrough: true };
    };

    const result = await renderHook.handler(test$, { component: 'Pane' }, nextSpy);
    if (nextCalled) {
      throw new Error('ui.render should not call next(e) when state is populated');
    }
    if (!result || result.type !== 'Box') {
      throw new Error(`expected Box pane returned, got: ${JSON.stringify(result)}`);
    }
  });

  test('ui.render lifecycle handler fails open and calls next(e) if reading state throws', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const renderHook = registered.find((r) => r.event === 'ui.render')!;

    const broken$ = {
      state: {
        get: () => {
          throw new Error('disk read fault');
        },
      },
    };

    let nextCalled = false;
    const nextSpy = () => {
      nextCalled = true;
      return { recovered: true };
    };

    const result = await renderHook.handler(broken$, { component: 'Pane' }, nextSpy);
    if (!nextCalled || !result || !result.recovered) {
      throw new Error('ui.render failed open error handling');
    }
  });

  test('session.start lifecycle handler clears populated atom state and calls next(e)', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const sessionHook = registered.find((r) => r.event === 'session.start')!;

    const test$ = createMockEngine();
    await setDuplicatePickerState(test$, {
      targetIssue: 50,
      targetTitle: 'Populated',
      candidates: [{ issue_number: 49, title: 'C', author: 'a' }],
      selectedKeptIssue: 50,
      dismissedIssues: [],
    });

    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { started: true, e };
    };

    const result = await sessionHook.handler(test$, { session: '123' }, nextSpy);
    if (!nextCalled || !result || !result.started) {
      throw new Error('session.start failed to call next(e)');
    }
    const state = await getDuplicatePickerState(test$);
    if (state !== null) {
      throw new Error(`expected session.start to reset atom state to null, got: ${JSON.stringify(state)}`);
    }
  });

  test('session.start lifecycle handler fails open and calls next(e) if resetting state throws', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const sessionHook = registered.find((r) => r.event === 'session.start')!;

    const broken$ = {
      state: {
        set: () => {
          throw new Error('store write fault');
        },
      },
    };

    let nextCalled = false;
    const nextSpy = () => {
      nextCalled = true;
      return { recovered: true };
    };

    const result = await sessionHook.handler(broken$, {}, nextSpy);
    if (!nextCalled || !result || !result.recovered) {
      throw new Error('session.start failed open error handling');
    }
  });
});
