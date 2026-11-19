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
  computePayloadHash,
  createStateFromPayload,
  deriveStatus,
  formatSimilarityBadge,
  getDuplicatePickerState,
  handleBashToolCall,
  handleWriteToolCall,
  hydrateCandidatesFromFile,
  invalidateDecisionFile,
  parseCandidatePayload,
  register,
  renderDuplicatePickerPane,
  safeWriteDecisionFile,
  sanitizeText,
  serializeDecision,
  setDuplicatePickerState,
  truncateText,
  updateDuplicatePickerState,
  MAX_VISIBLE_CANDIDATES,
} from './duplicate-picker.js';

function must<T>(v: T | null | undefined, what = 'value'): T {
  if (v === null || v === undefined) throw new Error(`missing ${what}`);
  return v;
}

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
  const defaultFs = {
    exists: async (p: string) => true,
    stat: async (p: string) => ({ kind: 'file', size: 0, mtimeMs: 0, isLink: false }),
    read: async (p: string) => '',
    write: async (p: string, content: string) => {},
  };
  const fs = overrides.fs ? { ...defaultFs, ...overrides.fs } : defaultFs;
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
      ...overrides.ui,
    },
    ...overrides,
    fs,
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
    if (must(parsed.candidates[0]).similarity_score !== 0.92) {
      throw new Error(`similarity score mismatch: ${must(parsed.candidates[0]).similarity_score}`);
    }
    if (must(parsed.candidates[0]).title !== 'Duplicate Bug in Map<String, Object>') {
      throw new Error(`title brackets altered: ${must(parsed.candidates[0]).title}`);
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
    if (parsed.candidates.length !== 1 || must(parsed.candidates[0]).issue_number !== 95) {
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
    if (parsed.candidates.length !== 1 || must(parsed.candidates[0]).title !== 'Duplicate Candidate First') {
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
    if (must(parsed.candidates[0]).similarity_score !== undefined) {
      throw new Error('NaN similarity_score should be dropped');
    }
    if (must(parsed.candidates[1]).similarity_score !== undefined) {
      throw new Error('>1 similarity_score should be dropped');
    }
    if (must(parsed.candidates[2]).similarity_score !== undefined) {
      throw new Error('<0 similarity_score should be dropped');
    }
    if (must(parsed.candidates[3]).similarity_score !== 0.85) {
      throw new Error(`valid score 0.85 should be retained, got ${must(parsed.candidates[3]).similarity_score}`);
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
    if (must(parsed.candidates[0]).author !== 'unknown' || must(parsed.candidates[1]).author !== 'unknown') {
      throw new Error(`failed safe author fallback: ${JSON.stringify(parsed.candidates)}`);
    }
  });

  test('normalizes author handles by stripping leading @ symbols', () => {
    const raw = {
      schema_version: 1,
      target_issue: 100,
      target_title: 'Bug',
      target_author: '@octocat',
      candidates: [
        { issue_number: 1, title: 'C1', author: '@@alice' },
        { issue_number: 2, title: 'C2', author: 'bob' },
      ],
    };
    const parsed = must(parseCandidatePayload(raw));
    if (parsed.target_author !== 'octocat') {
      throw new Error(`expected octocat without @, got ${parsed.target_author}`);
    }
    if (parsed.candidates[0]?.author !== 'alice') {
      throw new Error(`expected alice without @, got ${parsed.candidates[0]?.author}`);
    }
    if (parsed.candidates[1]?.author !== 'bob') {
      throw new Error(`expected bob, got ${parsed.candidates[1]?.author}`);
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
    const c = must(parsed.candidates[0]);
    if (!c.created_at || c.created_at.length > 25) {
      throw new Error(`created_at should be <= 25 chars, got length ${c.created_at?.length}: ${c.created_at}`);
    }
    if (!c.labels || c.labels.length > 4) {
      throw new Error(`labels should be at most 4 items, got ${c.labels?.length}`);
    }
    if (must(c.labels[0]).length > 20) {
      throw new Error(`label should be <= 20 chars, got length ${must(c.labels[0]).length}: ${must(c.labels[0])}`);
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

  test('returns dismissed when all visible candidates (up to MAX_VISIBLE_CANDIDATES) are dismissed, even if more than 10 candidates exist', () => {
    const candidates = Array.from({ length: 15 }, (_, i) => ({
      issue_number: 101 + i,
      title: `Candidate ${i + 1}`,
      author: `user${i}`,
    }));
    // Dismiss only the 10 rendered/visible candidates (101 through 110)
    const visibleDismissed = candidates.slice(0, 10).map((c) => c.issue_number);
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates,
      selectedKeptIssue: null,
      dismissedIssues: visibleDismissed,
    };
    if (deriveStatus(state) !== 'dismissed') {
      throw new Error(`expected dismissed when visible candidates are dismissed, got ${deriveStatus(state)}`);
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

  test('caps dropped_issues to rendered candidates (MAX_VISIBLE_CANDIDATES = 10) and does not stage unrendered candidates 11-15 for closure', () => {
    const candidates = Array.from({ length: 15 }, (_, i) => ({
      issue_number: 101 + i,
      title: `Candidate ${i + 1}`,
      author: `user${i}`,
    }));
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target Issue',
      candidates,
      selectedKeptIssue: 100,
      dismissedIssues: [],
    };

    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.status !== 'curated') {
      throw new Error(`expected curated status, got ${dec.status}`);
    }
    // Only candidates 101-110 (the 10 visible ones) should be in dropped_issues
    if (dec.dropped_issues.length !== 10) {
      throw new Error(`expected exactly 10 dropped issues, got ${dec.dropped_issues.length}: ${JSON.stringify(dec.dropped_issues)}`);
    }
    for (let i = 0; i < 10; i++) {
      if (!dec.dropped_issues.includes(101 + i)) {
        throw new Error(`expected visible candidate ${101 + i} in dropped_issues`);
      }
    }
    // Candidates 111-115 (11 to 15) must NEVER be dropped
    for (let i = 10; i < 15; i++) {
      if (dec.dropped_issues.includes(101 + i)) {
        throw new Error(`unrendered candidate ${101 + i} must NOT be in dropped_issues`);
      }
    }
  });

  test('embeds source_candidates_sha256 in serialized decision envelope', () => {
    const state: DuplicatePickerState = {
      targetIssue: 100,
      targetTitle: 'Target',
      candidates: [{ issue_number: 90, title: 'Candidate 1', author: 'a' }],
      selectedKeptIssue: 100,
      dismissedIssues: [],
      candidatesSha256: 'abc123hash',
    };
    const dec = serializeDecision(state, '2026-11-14T10:00:00Z');
    if (dec.source_candidates_sha256 !== 'abc123hash') {
      throw new Error(`expected source_candidates_sha256 abc123hash, got ${dec.source_candidates_sha256}`);
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

  test('renders targetAuthor in header when present', () => {
    const textNodes: string[] = [];
    const mockBox = (props: any) => ({ type: 'Box', ...props });
    const mockText = (props: any) => {
      if (Array.isArray(props?.children)) {
        textNodes.push(...props.children);
      }
      return { type: 'Text', ...props };
    };

    const test$ = createMockEngine({
      ui: {
        resolve: () => ({ Box: mockBox, Text: mockText, Button: () => ({ type: 'Button' }) }),
        invalidate: () => {},
      },
    });

    const stateWithAuthor: DuplicatePickerState = {
      targetIssue: 42,
      targetTitle: 'Issue with author',
      targetAuthor: 'octocat',
      candidates: [{ issue_number: 10, title: 'C', author: 'a' }],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };

    renderDuplicatePickerPane(test$, { component: 'Pane' }, stateWithAuthor);
    const targetHeader = textNodes.find((t) => t.includes('[Deduplication Target: #42 (@octocat)]'));
    if (!targetHeader) {
      throw new Error(`expected header to contain @octocat, got: ${JSON.stringify(textNodes)}`);
    }

    textNodes.length = 0;
    const stateWithoutAuthor: DuplicatePickerState = {
      targetIssue: 42,
      targetTitle: 'Issue without author',
      candidates: [{ issue_number: 10, title: 'C', author: 'a' }],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };
    renderDuplicatePickerPane(test$, { component: 'Pane' }, stateWithoutAuthor);
    const plainHeader = textNodes.find((t) => t.includes('[Deduplication Target: #42]'));
    if (!plainHeader) {
      throw new Error(`expected plain header without author, got: ${JSON.stringify(textNodes)}`);
    }
  });

  test('bounds candidate list to MAX_VISIBLE (10) and renders overflow box', () => {
    const textNodes: string[] = [];
    const mockBox = (props: any) => ({ type: 'Box', ...props });
    const mockText = (props: any) => {
      if (Array.isArray(props?.children)) {
        textNodes.push(...props.children);
      }
      return { type: 'Text', ...props };
    };

    const test$ = createMockEngine({
      ui: {
        resolve: () => ({ Box: mockBox, Text: mockText }),
        invalidate: () => {},
      },
    });

    const candidates = Array.from({ length: 15 }, (_, i) => ({
      issue_number: 100 + i,
      title: `Candidate ${i + 1}`,
      author: `user${i}`,
    }));

    const state: DuplicatePickerState = {
      targetIssue: 1,
      targetTitle: 'Target',
      candidates,
      selectedKeptIssue: null,
      dismissedIssues: [],
    };

    renderDuplicatePickerPane(test$, { component: 'Pane' }, state);
    const overflowNode = textNodes.find((t) => t.includes('... and 5 more candidate(s)'));
    if (!overflowNode) {
      throw new Error(`expected overflow notice for 5 excess candidates, got: ${JSON.stringify(textNodes)}`);
    }
  });

  test('renders warning footer when syncError is set on state', () => {
    const textNodes: string[] = [];
    const mockBox = (props: any) => ({ type: 'Box', ...props });
    const mockText = (props: any) => {
      if (Array.isArray(props?.children)) {
        textNodes.push(...props.children);
      }
      return { type: 'Text', ...props };
    };

    const test$ = createMockEngine({
      ui: {
        resolve: () => ({ Box: mockBox, Text: mockText }),
        invalidate: () => {},
      },
    });

    const state: DuplicatePickerState = {
      targetIssue: 1,
      targetTitle: 'Target',
      candidates: [{ issue_number: 2, title: 'C', author: 'a' }],
      selectedKeptIssue: 1,
      dismissedIssues: [],
      syncError: 'Refusing to write to symlink',
    };

    renderDuplicatePickerPane(test$, { component: 'Pane' }, state);
    const warningNode = textNodes.find((t) =>
      t.includes('[!] Warning: Curation sync failed (Refusing to write to symlink)')
    );
    if (!warningNode) {
      throw new Error(`expected sync error warning in pane footer, got: ${JSON.stringify(textNodes)}`);
    }
  });

  test('updateDuplicatePickerState stages decision file via $.fs.write on curate/dismiss and updates on toggle-off', async () => {
    const writtenFiles: Record<string, string> = {};
    const test$ = createMockEngine({
      fs: {
        write: async (path: string, content: string) => {
          writtenFiles[path] = content;
        },
      },
    });

    const state: DuplicatePickerState = {
      targetIssue: 77,
      targetTitle: 'Target 77',
      candidates: [{ issue_number: 78, title: 'Candidate 78', author: 'alice' }],
      selectedKeptIssue: null,
      dismissedIssues: [],
    };

    // 1. Initial atom set does not call updateDuplicatePickerState, so no file is written on unopened pane
    await setDuplicatePickerState(test$, state);
    if (Object.keys(writtenFiles).length > 0) {
      throw new Error(`expected no file written on initial load, got: ${JSON.stringify(writtenFiles)}`);
    }

    // 2. Select target as kept -> curated status -> writes .magpie-issue-decision-77.json
    await updateDuplicatePickerState(test$, (prev) => {
      if (!prev) return null;
      return { ...prev, selectedKeptIssue: 77 };
    });

    const expectedFile = '.magpie-issue-decision-77.json';
    if (!writtenFiles[expectedFile]) {
      throw new Error(`expected ${expectedFile} written on curated status`);
    }
    const parsed = JSON.parse(writtenFiles[expectedFile]);
    if (parsed.status !== 'curated' || parsed.kept_issue !== 77 || !parsed.dropped_issues.includes(78)) {
      throw new Error(`unexpected decision content: ${writtenFiles[expectedFile]}`);
    }

    // 3. Toggle off selection -> sets selectedKeptIssue back to null -> updates file with reviewing status and 0 dropped issues
    await updateDuplicatePickerState(test$, (prev) => {
      if (!prev) return null;
      return { ...prev, selectedKeptIssue: null };
    });
    const toggled = JSON.parse(writtenFiles[expectedFile]);
    if (toggled.status !== 'reviewing' || toggled.dropped_issues.length !== 0) {
      throw new Error(`expected reviewing status and 0 dropped issues on toggle off, got: ${writtenFiles[expectedFile]}`);
    }
  });
});

describe('register', () => {
  test('registers session.start, ui.render (Pane), and tool.call (Bash, Write) lifecycle hooks cleanly', () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    const fakeOn = (event: string, optsOrHandler: any, handler?: Function) => {
      if (typeof optsOrHandler === 'function') {
        registered.push({ event, handler: optsOrHandler });
      } else {
        registered.push({ event, opts: optsOrHandler, handler: handler! });
      }
    };

    register(fakeOn);
    if (registered.length < 4) {
      throw new Error(`expected at least 4 hooks, got ${registered.length}`);
    }
    const sessionHook = registered.find((r) => r.event === 'session.start');
    if (!sessionHook) {
      throw new Error('missing session.start hook');
    }
    const renderHook = registered.find((r) => r.event === 'ui.render');
    if (!renderHook || renderHook.opts?.component !== 'Pane') {
      throw new Error('ui.render hook missing or missing { component: "Pane" } matcher');
    }
    const bashToolHook = registered.find(
      (r) => r.event === 'tool.call' && r.opts?.tool === 'Bash'
    );
    if (!bashToolHook) {
      throw new Error('tool.call hook missing { tool: "Bash" } matcher');
    }
    const writeToolHook = registered.find(
      (r) => r.event === 'tool.call' && r.opts?.tool === 'Write'
    );
    if (!writeToolHook) {
      throw new Error('tool.call hook missing { tool: "Write" } matcher');
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

  test('ui.render lifecycle handler delegates to next(e) if requestId does not match duplicate-picker', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const renderHook = registered.find((r) => r.event === 'ui.render')!;

    const test$ = createMockEngine();
    await setDuplicatePickerState(test$, {
      targetIssue: 1,
      targetTitle: 'Target',
      candidates: [{ issue_number: 2, title: 'C', author: 'a' }],
      selectedKeptIssue: null,
      dismissedIssues: [],
    });

    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { skipped: true, e };
    };

    const result = await renderHook.handler(test$, { component: 'Pane', requestId: 'other-pane' }, nextSpy);
    if (!nextCalled || !result || !result.skipped) {
      throw new Error('ui.render should pass through when requestId does not match');
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

  test('session.start lifecycle handler strictly resets state and does not hydrate fixture payloads', async () => {
    const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
    register((event: string, optsOrHandler: any, handler?: Function) => {
      registered.push({ event, handler: typeof optsOrHandler === 'function' ? optsOrHandler : handler! });
    });
    const sessionHook = registered.find((r) => r.event === 'session.start')!;

    const openedPanes: any[] = [];
    const test$ = createMockEngine({
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          openedPanes.push(opts);
        },
      },
    });

    const fixturePayload = {
      schema_version: 1,
      target_issue: 200,
      target_title: 'Fixture Target',
      candidates: [{ issue_number: 199, title: 'Fixture C', author: 'tester' }],
    };

    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { e };
    };

    await sessionHook.handler(test$, { candidatesPayload: fixturePayload }, nextSpy);
    if (!nextCalled) throw new Error('session.start did not call next(e)');
    const state = await getDuplicatePickerState(test$);
    if (state !== null) {
      throw new Error(`expected state null after session.start, got: ${JSON.stringify(state)}`);
    }
    if (openedPanes.length !== 0) {
      throw new Error(`expected $.ui.open not called during session.start, got: ${JSON.stringify(openedPanes)}`);
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

describe('hydrateCandidatesFromFile', () => {
  test('reads JSON from disk via $.fs.read, updates atom state, and calls $.ui.open', async () => {
    const payload = {
      schema_version: 1,
      target_issue: 88,
      target_title: 'Hydrated Target',
      target_author: 'hydrator',
      candidates: [
        {
          issue_number: 87,
          title: 'Candidate 87',
          author: 'bob',
          similarity_score: 0.9,
        },
      ],
    };

    const opened: any[] = [];
    const test$ = createMockEngine({
      fs: {
        read: async (path: string) => {
          if (path === '.magpie-issue-candidates-88.json') {
            return JSON.stringify(payload);
          }
          throw new Error('file not found');
        },
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          opened.push(opts);
        },
      },
    });

    const ok = await hydrateCandidatesFromFile(test$, '.magpie-issue-candidates-88.json');
    if (!ok) {
      throw new Error('expected hydrateCandidatesFromFile to return true');
    }

    const state = await getDuplicatePickerState(test$);
    if (!state || state.targetIssue !== 88 || state.targetAuthor !== 'hydrator') {
      throw new Error(`state not hydrated properly: ${JSON.stringify(state)}`);
    }

    if (opened.length !== 1 || opened[0].id !== 'duplicate-picker') {
      throw new Error(`expected $.ui.open called, got: ${JSON.stringify(opened)}`);
    }
  });

  test('fails open and returns false on missing file, empty content, or invalid JSON', async () => {
    const test$ = createMockEngine({
      fs: {
        read: async (path: string) => {
          if (path === 'empty.json') return '   ';
          if (path === 'corrupt.json') return '{ invalid json';
          throw new Error('ENOENT');
        },
      },
    });

    if (await hydrateCandidatesFromFile(test$, 'nonexistent.json')) {
      throw new Error('expected false for missing file');
    }
    if (await hydrateCandidatesFromFile(test$, 'empty.json')) {
      throw new Error('expected false for empty file');
    }
    if (await hydrateCandidatesFromFile(test$, 'corrupt.json')) {
      throw new Error('expected false for corrupt file');
    }
  });
});

describe('handleBashToolCall', () => {
  test('intercepts command referencing candidate file, hydrates state, and calls next(e)', async () => {
    const payload = {
      schema_version: 1,
      target_issue: 55,
      target_title: 'Bash Target',
      candidates: [{ issue_number: 54, title: 'Bash C', author: 'user' }],
    };

    const opened: any[] = [];
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-candidates-55.json',
        read: async (p: string) => {
          if (p === '.magpie-issue-candidates-55.json') return JSON.stringify(payload);
          throw new Error('ENOENT');
        },
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          opened.push(opts);
        },
      },
    });

    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { toolResult: 'ok', e };
    };

    const cmd = 'cat .magpie-issue-candidates-55.json';
    const res = await handleBashToolCall(test$, { command: cmd }, nextSpy);

    if (!nextCalled || !res || res.toolResult !== 'ok') {
      throw new Error('handleBashToolCall failed to call next(e)');
    }
    const state = await getDuplicatePickerState(test$);
    if (!state || state.targetIssue !== 55) {
      throw new Error(`expected state hydrated with issue 55, got: ${JSON.stringify(state)}`);
    }
    if (opened.length !== 1 || opened[0].id !== 'duplicate-picker') {
      throw new Error(`expected $.ui.open called, got: ${JSON.stringify(opened)}`);
    }
  });

  test('passes non-matching commands directly to next(e) without error', async () => {
    const test$ = createMockEngine();
    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { done: true, e };
    };

    const res = await handleBashToolCall(test$, { command: 'git status' }, nextSpy);
    if (!nextCalled || !res || !res.done) {
      throw new Error('handleBashToolCall failed on regular bash command');
    }
  });

  test('does not hydrate or reset state when command references decision file, passing directly to next(e)', async () => {
    const payload = {
      schema_version: 1,
      target_issue: 60,
      target_title: 'Decision Check Target',
      candidates: [{ issue_number: 59, title: 'Decision C', author: 'tester' }],
    };

    const opened: any[] = [];
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-candidates-60.json',
        read: async (p: string) => {
          if (p === '.magpie-issue-candidates-60.json') return JSON.stringify(payload);
          throw new Error('ENOENT');
        },
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          opened.push(opts);
        },
      },
    });

    let nextCalled = false;
    const nextSpy = () => {
      nextCalled = true;
      return { checked: true };
    };

    const res = await handleBashToolCall(test$, { command: 'test -f .magpie-issue-decision-60.json' }, nextSpy);
    if (!nextCalled || !res || !res.checked) throw new Error('next not called or result missing');
    const state = await getDuplicatePickerState(test$);
    if (state !== null) {
      throw new Error(`expected state to remain null on decision check, got: ${JSON.stringify(state)}`);
    }
    if (opened.length !== 0) {
      throw new Error(`expected $.ui.open not called, got: ${JSON.stringify(opened)}`);
    }
  });

  test('skips re-hydration if atom already holds target issue with loaded candidates and identical hash', async () => {
    let readCount = 0;
    const payload = {
      schema_version: 1,
      target_issue: 60,
      target_title: 'Existing Target',
      candidates: [{ issue_number: 59, title: 'Existing C', author: 'tester' }],
    };

    const test$ = createMockEngine({
      fs: {
        exists: async () => true,
        read: async () => {
          readCount++;
          return JSON.stringify(payload);
        },
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async () => {},
      },
    });

    // Populate initial state with selections and matching hash
    await setDuplicatePickerState(test$, {
      targetIssue: 60,
      targetTitle: 'Existing Target',
      candidates: [{ issue_number: 59, title: 'Existing C', author: 'tester' }],
      candidatesSha256: computePayloadHash(JSON.stringify(payload)),
      selectedKeptIssue: 59,
      dismissedIssues: [],
    });

    const nextSpy = () => ({ checked: true });
    await handleBashToolCall(test$, { command: 'cat .magpie-issue-candidates-60.json' }, nextSpy);

    const state = await getDuplicatePickerState(test$);
    if (!state || state.selectedKeptIssue !== 59) {
      throw new Error(`selection was wiped: ${JSON.stringify(state)}`);
    }
  });

  test('re-hydrates and resets stale state when candidate file is rewritten with different content for same target', async () => {
    const payload1 = {
      schema_version: 1,
      target_issue: 60,
      target_title: 'Target 60',
      candidates: [{ issue_number: 59, title: 'Old Candidate', author: 'tester' }],
    };
    const payload2 = {
      schema_version: 1,
      target_issue: 60,
      target_title: 'Target 60',
      candidates: [{ issue_number: 58, title: 'New Candidate', author: 'tester2' }],
    };

    const opened: any[] = [];
    const test$ = createMockEngine({
      fs: {
        exists: async () => true,
        read: async () => JSON.stringify(payload2),
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          opened.push(opts);
        },
      },
    });

    // Populate initial state with payload1 and selection
    await setDuplicatePickerState(test$, {
      targetIssue: 60,
      targetTitle: 'Target 60',
      candidates: [{ issue_number: 59, title: 'Old Candidate', author: 'tester' }],
      candidatesSha256: computePayloadHash(JSON.stringify(payload1)),
      selectedKeptIssue: 59,
      dismissedIssues: [],
    });

    const nextSpy = () => ({ checked: true });
    await handleBashToolCall(test$, { command: 'cat .magpie-issue-candidates-60.json' }, nextSpy);

    const state = await getDuplicatePickerState(test$);
    if (!state || state.candidates[0]?.issue_number !== 58) {
      throw new Error(`expected re-hydrated candidates with issue 58, got: ${JSON.stringify(state?.candidates)}`);
    }
    if (state.selectedKeptIssue !== null) {
      throw new Error(`expected selection to be reset on candidate rewrite, got: ${state.selectedKeptIssue}`);
    }
    if (state.candidatesSha256 !== computePayloadHash(JSON.stringify(payload2))) {
      throw new Error(`expected updated candidatesSha256, got: ${state.candidatesSha256}`);
    }
    if (opened.length !== 1) {
      throw new Error(`expected $.ui.open to be called on re-hydration, got ${opened.length}`);
    }
  });
});

describe('handleWriteToolCall', () => {
  test('intercepts Write tool call on candidate file, hydrates state, and calls $.ui.open', async () => {
    const payload = {
      schema_version: 1,
      target_issue: 42,
      target_title: 'Write Target',
      candidates: [{ issue_number: 41, title: 'Write C', author: 'tester' }],
    };

    const opened: any[] = [];
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-candidates-42.json',
        read: async (p: string) => {
          if (p === '.magpie-issue-candidates-42.json') return JSON.stringify(payload);
          throw new Error('ENOENT');
        },
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          opened.push(opts);
        },
      },
    });

    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { toolResult: 'written', e };
    };

    const res = await handleWriteToolCall(
      test$,
      { file_path: '.magpie-issue-candidates-42.json', content: JSON.stringify(payload) },
      nextSpy
    );

    if (!nextCalled || !res || res.toolResult !== 'written') {
      throw new Error('handleWriteToolCall failed to call next(e)');
    }
    const state = await getDuplicatePickerState(test$);
    if (!state || state.targetIssue !== 42) {
      throw new Error(`expected state hydrated with issue 42, got: ${JSON.stringify(state)}`);
    }
    if (opened.length !== 1 || opened[0].id !== 'duplicate-picker') {
      throw new Error(`expected $.ui.open called, got: ${JSON.stringify(opened)}`);
    }
  });

  test('passes non-matching Write calls directly to next(e) without hydration', async () => {
    const test$ = createMockEngine();
    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { done: true, e };
    };

    const res = await handleWriteToolCall(test$, { path: 'src/index.ts' }, nextSpy);
    if (!nextCalled || !res || !res.done) {
      throw new Error('handleWriteToolCall failed on regular file write');
    }
    const state = await getDuplicatePickerState(test$);
    if (state !== null) {
      throw new Error('state was unexpectedly populated');
    }
  });

  test('ignores Write tool call when candidate file is outside workspace root', async () => {
    const payload = {
      schema_version: 1,
      target_issue: 42,
      target_title: 'Write Target',
      candidates: [{ issue_number: 41, title: 'Write C', author: 'tester' }],
    };

    const opened: any[] = [];
    const test$ = createMockEngine({
      fs: {
        exists: async () => true,
        read: async () => JSON.stringify(payload),
      },
      ui: {
        invalidate: () => {},
        resolve: () => ({}),
        open: async (opts: any) => {
          opened.push(opts);
        },
      },
    });

    let nextCalled = false;
    const nextSpy = (e: any) => {
      nextCalled = true;
      return { toolResult: 'written', e };
    };

    // Test with path traversal outside workspace
    await handleWriteToolCall(
      test$,
      { file_path: '../../.magpie-issue-candidates-42.json', content: JSON.stringify(payload) },
      nextSpy
    );

    let state = await getDuplicatePickerState(test$);
    if (state !== null || opened.length !== 0) {
      throw new Error(`expected write outside workspace to be ignored, got state: ${JSON.stringify(state)}`);
    }

    // Test with absolute path outside workspace
    await handleWriteToolCall(
      test$,
      { file_path: '/tmp/.magpie-issue-candidates-42.json', content: JSON.stringify(payload) },
      nextSpy
    );

    state = await getDuplicatePickerState(test$);
    if (state !== null || opened.length !== 0) {
      throw new Error(`expected write to /tmp to be ignored, got state: ${JSON.stringify(state)}`);
    }
  });
});

describe('safeWriteDecisionFile and invalidateDecisionFile', () => {
  test('safeWriteDecisionFile writes regular file when candidate file exists', async () => {
    const writtenFiles: Record<string, string> = {};
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-candidates-77.json',
        stat: async () => ({ kind: 'file', size: 0, mtimeMs: 0, isLink: false }),
        write: async (p: string, c: string) => {
          writtenFiles[p] = c;
        },
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (!res.success) {
      throw new Error(`expected success, got error: ${res.error}`);
    }
    if (writtenFiles['.magpie-issue-decision-77.json'] !== '{"status":"curated"}') {
      throw new Error(`file not written: ${JSON.stringify(writtenFiles)}`);
    }
  });

  test('safeWriteDecisionFile refuses to write when candidate file is missing', async () => {
    const test$ = createMockEngine({
      fs: {
        exists: async () => false,
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (res.success || !res.error?.includes('Candidate file missing')) {
      throw new Error(`expected refusal on missing candidate file, got: ${JSON.stringify(res)}`);
    }
  });

  test('safeWriteDecisionFile refuses to write through a symbolic link to a regular file', async () => {
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => true,
        stat: async (p: string) => ({ kind: 'file', size: 0, mtimeMs: 0, isLink: true }),
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (res.success || !res.error?.includes('Refusing to write to symlink')) {
      throw new Error(`expected refusal on symlink, got: ${JSON.stringify(res)}`);
    }
  });

  test('safeWriteDecisionFile refuses to write to non-regular files (e.g. FIFOs, devices, directories)', async () => {
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => true,
        stat: async (p: string) => ({ kind: 'dir', size: 0, mtimeMs: 0, isLink: false }),
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (res.success || !res.error?.includes('Refusing to write to symlink or non-regular file')) {
      throw new Error(`expected refusal on non-regular file, got: ${JSON.stringify(res)}`);
    }
  });

  test('invalidateDecisionFile stages invalidated decision on disk if file exists and is regular', async () => {
    const writtenFiles: Record<string, string> = {};
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-decision-77.json',
        stat: async () => ({ kind: 'file', size: 0, mtimeMs: 0, isLink: false }),
        write: async (p: string, c: string) => {
          writtenFiles[p] = c;
        },
      },
    });

    await invalidateDecisionFile(test$, 77);
    const written = writtenFiles['.magpie-issue-decision-77.json'];
    if (!written) {
      throw new Error('expected decision file invalidated on disk');
    }
    const parsed = JSON.parse(written);
    if (!parsed.invalidated || parsed.status !== 'reviewing' || parsed.dropped_issues.length !== 0) {
      throw new Error(`invalidated envelope incorrect: ${written}`);
    }
  });

  test('invalidateDecisionFile does not overwrite symlink files', async () => {
    let writeCalled = false;
    const test$ = createMockEngine({
      fs: {
        exists: async () => true,
        stat: async () => ({ kind: 'file', size: 0, mtimeMs: 0, isLink: true }),
        write: async () => {
          writeCalled = true;
        },
      },
    });

    await invalidateDecisionFile(test$, 77);
    if (writeCalled) {
      throw new Error('invalidateDecisionFile must not write to symlink');
    }
  });
  test('safeWriteDecisionFile writes a new file when the decision path is missing', async () => {
    const writtenFiles: Record<string, string> = {};
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-candidates-77.json',
        stat: async () => {
          throw Object.assign(new Error('ENOENT: no such file'), { code: 'ENOENT' });
        },
        write: async (p: string, c: string) => {
          writtenFiles[p] = c;
        },
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (!res.success || writtenFiles['.magpie-issue-decision-77.json'] !== '{"status":"curated"}') {
      throw new Error(`expected a new decision file, got: ${JSON.stringify(res)}`);
    }
  });

  test('safeWriteDecisionFile refuses a dangling symbolic link', async () => {
    let writeCalled = false;
    const test$ = createMockEngine({
      fs: {
        exists: async (p: string) => p === '.magpie-issue-candidates-77.json',
        stat: async () => ({ kind: 'other', size: 0, mtimeMs: 0, isLink: true }),
        write: async () => {
          writeCalled = true;
        },
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (res.success || writeCalled) {
      throw new Error(`expected refusal on a dangling link, got: ${JSON.stringify(res)}`);
    }
  });

  test('safeWriteDecisionFile fails closed when stat fails for another reason', async () => {
    let writeCalled = false;
    const test$ = createMockEngine({
      fs: {
        exists: async () => true,
        stat: async () => {
          throw Object.assign(new Error('EACCES: permission denied'), { code: 'EACCES' });
        },
        write: async () => {
          writeCalled = true;
        },
      },
    });

    const res = await safeWriteDecisionFile(test$, 77, '{"status":"curated"}');
    if (res.success || writeCalled) {
      throw new Error(`expected refusal when stat fails, got: ${JSON.stringify(res)}`);
    }
  });

  test('invalidateDecisionFile leaves a missing decision file alone', async () => {
    let writeCalled = false;
    const test$ = createMockEngine({
      fs: {
        stat: async () => {
          throw Object.assign(new Error('ENOENT: no such file'), { code: 'ENOENT' });
        },
        write: async () => {
          writeCalled = true;
        },
      },
    });

    await invalidateDecisionFile(test$, 77);
    if (writeCalled) {
      throw new Error('invalidateDecisionFile must not create a decision file');
    }
  });

});

describe('computePayloadHash', () => {
  test('computes deterministic pure-TS SHA-256 matching standard hash', () => {
    const emptyHash = computePayloadHash('');
    if (emptyHash !== 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855') {
      throw new Error(`empty hash mismatch: got ${emptyHash}`);
    }

    const testHash = computePayloadHash('{"target_issue":100}');
    if (typeof testHash !== 'string' || testHash.length !== 64) {
      throw new Error(`expected 64 char hex string, got ${testHash}`);
    }

    const unicodeHash = computePayloadHash('Café 🚀 汉字');
    if (unicodeHash !== '2e692bd39e25979b0fbdf6563bb8dfae8802f487990755478c69c9e6bc6cbf8c') {
      throw new Error(`unicode hash mismatch: got ${unicodeHash}`);
    }
  });
});
