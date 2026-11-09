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
import {
  calculateSummary,
  cleanCuratedFindingsFiles,
  computeFindingsHash,
  cycleFindingAction,
  findMatchingExistingFinding,
  formatActionIndicator,
  formatFindingDescription,
  formatKeepAnswer,
  getCuratedFindingsPaths,
  extractFindingsPathFromCommand,
  extractPrNumberFromCommand,
  formatSeverityBadge,
  getReviewFindingsState,
  handleBashToolCall,
  handleFindingsCommand,
  handleUiPress,
  isAnchored,
  isCuratedSidecarValid,
  normalizeAction,
  normalizeFilePath,
  normalizeLine,
  normalizeSeverity,
  normalizeSource,
  parseFindings,
  parseFindingTokens,
  resolveFindingIndex,
  resolveRelativePath,
  register,
  renderFindingsPane,
  reviewFindingsState,
  sanitizeFindingText,
  serializeFindingsForRender,
  setBulkActionInState,
  setReviewFindingsState,
  syncCuratedStateToDisk,
  toggleFindingActionInState,
  truncateFilePath,
  truncateText,
  updateAndSyncReviewFindingsState,
  updateFindingInState,
  updateSelectedIndexInState,
} from './review-findings.ts';
import type { ReviewFinding, ReviewFindingsState } from './types.ts';

function assert(condition: any, message?: string): void {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertStrictEqual(actual: any, expected: any, message?: string): void {
  if (actual !== expected) {
    throw new Error(
      message || `Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`
    );
  }
}

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
  const files = new Map<string, string>();
  const defaultFs = {
    read: async (path: string) => {
      if (files.has(path)) return files.get(path);
      throw new Error(`ENOENT: ${path}`);
    },
    write: async (path: string, content: string) => {
      files.set(path, content);
    },
    exists: async (path: string) => {
      return files.has(path);
    },
    _files: files,
  };
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
    },
    fs: {
      ...defaultFs,
      ...(overrides.fs || {}),
    },
    ...overrides,
  };
}

function assertDeepStrictEqual(actual: any, expected: any): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `Expected deep equality: ${JSON.stringify(expected)} !== ${JSON.stringify(actual)}`
    );
  }
}

describe('magpie-pr-management review findings mod (PR-1 & PR-2)', () => {
  describe('normalization helpers', () => {
    test('normalizeSeverity maps known severities and synonyms case-insensitively', () => {
      assertStrictEqual(normalizeSeverity('blocking'), 'blocking');
      assertStrictEqual(normalizeSeverity('BLOCKING'), 'blocking');
      assertStrictEqual(normalizeSeverity('critical'), 'blocking');
      assertStrictEqual(normalizeSeverity('blocker'), 'blocking');

      assertStrictEqual(normalizeSeverity('major'), 'major');
      assertStrictEqual(normalizeSeverity('Major'), 'major');
      assertStrictEqual(normalizeSeverity('high'), 'major');

      assertStrictEqual(normalizeSeverity('minor'), 'minor');
      assertStrictEqual(normalizeSeverity('low'), 'minor');

      assertStrictEqual(normalizeSeverity('nit'), 'nit');
      assertStrictEqual(normalizeSeverity('NIT'), 'nit');
      assertStrictEqual(normalizeSeverity('trivial'), 'nit');
      assertStrictEqual(normalizeSeverity('info'), 'nit');

      assertStrictEqual(normalizeSeverity(null), 'minor');
      assertStrictEqual(normalizeSeverity(123), 'minor');
    });

    test('normalizeSeverity logs an error when encountering an unmapped severity', () => {
      const errors: string[] = [];
      const result = normalizeSeverity('catastrophic', errors);
      assertStrictEqual(result, 'minor');
      assertStrictEqual(errors.length, 1);
      assert(errors[0].includes("Unrecognized severity 'catastrophic'"));
    });

    test('normalizeFilePath standardizes Windows backslashes and strips leading relative paths', () => {
      assertStrictEqual(
        normalizeFilePath('src\\pr_management\\code_review\\body.py'),
        'src/pr_management/code_review/body.py'
      );
      assertStrictEqual(normalizeFilePath('./providers/foo/hook.py'), 'providers/foo/hook.py');
      assertStrictEqual(normalizeFilePath('.\\providers\\foo\\hook.py'), 'providers/foo/hook.py');
      assertStrictEqual(normalizeFilePath(''), 'general');
      assertStrictEqual(normalizeFilePath(null), 'general');
    });

    test('normalizeLine validates integers and rejects malformed prefixes with error logging', () => {
      assertStrictEqual(normalizeLine(42), 42);
      assertStrictEqual(normalizeLine('142'), 142);
      assertStrictEqual(normalizeLine(0), null);
      assertStrictEqual(normalizeLine(-10), null);
      assertStrictEqual(normalizeLine(null), null);
      assertStrictEqual(normalizeLine(undefined), null);

      const errors: string[] = [];
      assertStrictEqual(normalizeLine('12.5', errors), null);
      assertStrictEqual(normalizeLine('12-20', errors), null);
      assertStrictEqual(normalizeLine('1e2', errors), null);
      assertStrictEqual(normalizeLine('invalid', errors), null);
      assertStrictEqual(errors.length, 4);
      assert(errors[0].includes("Malformed line number '12.5'"));
    });

    test('numeric non-integer or negative lines and non-string severities are recorded', () => {
      const lineErrors: string[] = [];
      assertStrictEqual(normalizeLine(12.5, lineErrors), null);
      assertStrictEqual(normalizeLine(-3, lineErrors), null);
      assertStrictEqual(lineErrors.length, 2);
      assert(lineErrors[0].includes("Malformed line number '12.5'"));
      assert(lineErrors[1].includes("Malformed line number '-3'"));

      const severityErrors: string[] = [];
      assertStrictEqual(normalizeSeverity(42, severityErrors), 'minor');
      assertStrictEqual(severityErrors.length, 1);
      assert(severityErrors[0].includes("Invalid severity type 'number'"));
    });

    test('normalizeSource validates reviewer source attributes', () => {
      assertStrictEqual(normalizeSource('primary'), 'primary');
      assertStrictEqual(normalizeSource('adversarial'), 'adversarial');
      assertStrictEqual(normalizeSource('both'), 'both');
      assertStrictEqual(normalizeSource('ADVERSARIAL'), 'adversarial');
      assertStrictEqual(normalizeSource('other'), 'primary');
      assertStrictEqual(normalizeSource(null), 'primary');
    });

    test('normalizeAction defaults missing to accept and treats unrecognized as skip with error', () => {
      assertStrictEqual(normalizeAction('accept'), 'accept');
      assertStrictEqual(normalizeAction('skip'), 'skip');
      assertStrictEqual(normalizeAction('edit'), 'edit');
      assertStrictEqual(normalizeAction('ACCEPT'), 'accept');
      assertStrictEqual(normalizeAction(undefined), 'accept');
      assertStrictEqual(normalizeAction(null), 'accept');

      const errors: string[] = [];
      assertStrictEqual(normalizeAction('reject', errors), 'skip');
      assertStrictEqual(normalizeAction('drop', errors), 'skip');
      assertStrictEqual(normalizeAction(123 as any, errors), 'skip');
      assertStrictEqual(errors.length, 3);
      assert(errors[0].includes("Unrecognized action 'reject'"));
    });

    test('sanitizeFindingText strips ANSI CSI, OSC sequences, and C0/C1 control characters', () => {
      // ANSI color / style CSI sequences
      assertStrictEqual(sanitizeFindingText('\u001b[31;1mSecurity alert\u001b[0m'), 'Security alert');
      // Cursor movements and screen clear
      assertStrictEqual(sanitizeFindingText('\u001b[2K\u001b[1Aclean text'), 'clean text');
      // OSC 8 hyperlinks (keeping visible text, dropping escape target)
      assertStrictEqual(
        sanitizeFindingText('\u001b]8;;https://example.com\u0007Click here\u001b]8;;\u0007'),
        'Click here'
      );
      // C0 and C1 control characters (null, bell, backspace, newlines, DEL)
      assertStrictEqual(sanitizeFindingText('Line1\r\nLine2\u0000\u0007\u007f'), 'Line1 Line2');
      // Empty input
      assertStrictEqual(sanitizeFindingText(''), '');
      assertStrictEqual(sanitizeFindingText(null as any), '');
    });

    test('formatFindingDescription harmonizes rule and body with length truncation', () => {
      // Both rule and body present
      assertStrictEqual(
        formatFindingDescription('security-rule', 'Check input buffer'),
        'security-rule \u2014 Check input buffer'
      );
      // Only body present
      assertStrictEqual(formatFindingDescription(undefined, 'Unanchored note'), 'Unanchored note');
      // Only rule present
      assertStrictEqual(formatFindingDescription('rule-only', ''), 'rule-only');
      // Truncation when exceeding maxLength
      const longBody = 'A'.repeat(100);
      const formatted = formatFindingDescription('rule', longBody, 30);
      assertStrictEqual(formatted.length, 30);
      assert(formatted.endsWith('...'));
      // Strips ANSI escapes from both rule and body
      assertStrictEqual(
        formatFindingDescription('\u001b[31mrule\u001b[0m', '\u001b[32mclean body\u001b[0m'),
        'rule \u2014 clean body'
      );
    });
  });

  describe('calculateSummary and isAnchored', () => {
    test('isAnchored matches render criteria where line is positive integer', () => {
      assertStrictEqual(isAnchored({ line: 1 }), true);
      assertStrictEqual(isAnchored({ line: 142 }), true);
      assertStrictEqual(isAnchored({ line: 0 }), false);
      assertStrictEqual(isAnchored({ line: -1 }), false);
      assertStrictEqual(isAnchored({ line: null }), false);
      assertStrictEqual(isAnchored({}), false);
    });

    test('accurately aggregates severity and anchoring statistics', () => {
      const findings: ReviewFinding[] = [
        {
          id: 'finding-1',
          file: 'a.py',
          line: 10,
          severity: 'blocking',
          body: 'Critical flaw',
          action: 'accept',
        },
        {
          id: 'finding-2',
          file: 'b.py',
          line: 20,
          severity: 'major',
          body: 'Security breach',
          action: 'accept',
        },
        {
          id: 'finding-3',
          file: 'c.py',
          line: null,
          severity: 'minor',
          body: 'Unanchored style',
          action: 'accept',
        },
        {
          id: 'finding-4',
          file: 'd.py',
          line: 30,
          severity: 'nit',
          body: 'Typo in comment',
          action: 'skip',
        },
      ];

      const summary = calculateSummary(findings);
      assertStrictEqual(summary.blockingCount, 1);
      assertStrictEqual(summary.majorCount, 1);
      assertStrictEqual(summary.minorCount, 1);
      assertStrictEqual(summary.nitCount, 1);
      assertStrictEqual(summary.total, 4);
      assertStrictEqual(summary.anchoredCount, 3);
      assertStrictEqual(summary.unanchoredCount, 1);
    });
  });

  describe('formatKeepAnswer', () => {
    test('returns ALL when all anchored findings are accepted or edited', () => {
      const allAccepted: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'Issue 1', action: 'accept' },
        { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'Issue 2', action: 'accept' },
      ];
      assertStrictEqual(formatKeepAnswer(allAccepted), 'ALL');

      const allEdited: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'Issue 1', action: 'edit' },
        { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'Issue 2', action: 'edit' },
      ];
      assertStrictEqual(formatKeepAnswer(allEdited), 'ALL');
    });

    test('returns NONE when all anchored findings are skipped or when no findings are anchored', () => {
      const skipped: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'Issue 1', action: 'skip' },
      ];
      assertStrictEqual(formatKeepAnswer(skipped), 'NONE');

      const unanchoredOnly: ReviewFinding[] = [
        { id: '2', file: 'b.py', line: null, severity: 'minor', body: 'Issue 2', action: 'accept' },
      ];
      assertStrictEqual(formatKeepAnswer(unanchoredOnly), 'NONE');
    });

    test('treats both accept and edit as kept in mixed lists', () => {
      const findings: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'First', action: 'accept' },
        { id: '2', file: 'b.py', line: 20, severity: 'major', body: 'Second', action: 'edit' },
        { id: '3', file: 'c.py', line: 30, severity: 'nit', body: 'Third', action: 'skip' },
        { id: '4', file: 'd.py', line: 40, severity: 'minor', body: 'Fourth', action: 'accept' },
      ];
      assertStrictEqual(formatKeepAnswer(findings), '1,2,4');
    });

    test('anchoring parity check with Python render rule', () => {
      const rawDataset = [
        { file: 'a.py', line: 12, body: 'Valid line 12', action: 'accept' },
        { file: 'b.py', line: null, body: 'Unanchored null', action: 'accept' },
        { file: 'c.py', line: 0, body: 'Zero line unanchored', action: 'accept' },
        { file: 'd.py', line: 55, body: 'Valid line 55', action: 'skip' },
        { file: 'e.py', line: 99, body: 'Valid line 99', action: 'edit' },
      ];

      const parsed = parseFindings(rawDataset);
      const pythonAnchoredIndices: number[] = [];
      const pythonAnchored = rawDataset.filter((item) => Boolean(item.line));

      for (let i = 0; i < pythonAnchored.length; i += 1) {
        const item = pythonAnchored[i];
        if (item.action === 'accept' || item.action === 'edit') {
          pythonAnchoredIndices.push(i + 1);
        }
      }

      const modAnswer = formatKeepAnswer(parsed.findings);
      assertStrictEqual(modAnswer, pythonAnchoredIndices.join(','));
      assertStrictEqual(modAnswer, '1,3');
    });
  });

  describe('serializeFindingsForRender', () => {
    test('produces clean JSON payload matching render parameter requirements', () => {
      const findings: ReviewFinding[] = [
        {
          id: 'finding-1',
          file: 'a.py',
          line: 142,
          severity: 'blocking',
          body: 'Syntax flaw',
          rule: 'syntax',
          action: 'accept',
        },
      ];
      const serialized = serializeFindingsForRender(findings);
      const decoded = JSON.parse(serialized);
      assertStrictEqual(Array.isArray(decoded), true);
      assertStrictEqual(decoded.length, 1);
      assertStrictEqual(decoded[0].file, 'a.py');
      assertStrictEqual(decoded[0].line, 142);
      assertStrictEqual(decoded[0].severity, 'blocking');
      assertStrictEqual(decoded[0].explanation, 'Syntax flaw');
      assertStrictEqual(decoded[0].rule_id, 'syntax');
    });

    test('round-trips a full Step-4 finding with every key render reads', () => {
      const step4 = {
        file: 'providers/foo/hook.py',
        line: 142,
        rule_source: '<project-config>/criteria.md',
        rule_section: '#code-quality-rules',
        rule_id: 'Flag imports inside a function body',
        quoted_rule: 'Never import inside a function.',
        excerpt: 'def get_client():\n    import boto3\n',
        severity: 'major',
        suggestion: 'Move import to file header.',
        suggestion_block: 'import boto3\n',
        side: 'RIGHT',
        reviewers: ['alice'],
      };

      const parsed = parseFindings([step4]);
      assertStrictEqual(parsed.errors.length, 0);
      assertStrictEqual(parsed.findings.length, 1);

      const serialized = serializeFindingsForRender(parsed.findings);
      const roundTripped = JSON.parse(serialized)[0];

      for (const [key, value] of Object.entries(step4)) {
        assertDeepStrictEqual(roundTripped[key], value);
      }
    });

    test('render numbering over the serialised file matches formatKeepAnswer', () => {
      const raw = [
        { file: 'a.py', lineNumber: '12', body: 'Valid line 12', action: 'accept' },
        { file: 'b.py', line_number: '14', body: 'Valid line 14', action: 'edit' },
        { file: 'c.py', line: '0', body: 'Zero string unanchored', action: 'accept' },
        'not an object',
        { file: 'd.py', line: 55, body: 'Valid line 55', action: 'skip' },
        { file: 'e.py', line: 99, body: 'Valid line 99', action: 'edit' },
      ];

      const parsed = parseFindings(raw);
      const serialized = serializeFindingsForRender(parsed.findings);
      const consumedByRender: Array<Record<string, unknown>> = JSON.parse(serialized);

      const renderAnchored = consumedByRender.filter((f) => Boolean(f.line));
      const actions = parsed.findings.filter(isAnchored).map((f) => f.action);
      assertStrictEqual(renderAnchored.length, actions.length);
      const renderKept = renderAnchored
        .map((_, i) => i + 1)
        .filter((i) => actions[i - 1] === 'accept' || actions[i - 1] === 'edit');
      assertStrictEqual(formatKeepAnswer(parsed.findings), renderKept.join(','));
      assertStrictEqual(formatKeepAnswer(parsed.findings), '1,2,4');
    });
  });

  describe('parseFindings', () => {
    test('preserves code suggestion leading indentation with trimEnd', () => {
      const raw = JSON.stringify([
        {
          file: 'src/main.py',
          line: 42,
          severity: 'major',
          body: 'Indented block suggestion',
          suggestion_block: '    def hello():\n        return 42\n',
        },
      ]);

      const result = parseFindings(raw);
      assertStrictEqual(result.errors.length, 0);
      assertStrictEqual(result.findings.length, 1);
      assertStrictEqual(
        result.findings[0].fixup,
        '    def hello():\n        return 42'
      );
    });

    test('extracts JSON payload from markdown code block fences even with surrounding prose', () => {
      const markdown = `
Here are the review findings from Step 4:
\`\`\`json
[
  {
    "file": "providers/foo.py",
    "line": 100,
    "severity": "major",
    "explanation": "Resource leak detected",
    "rule_id": "resource-leak",
    "suggestion_block": "    with acquire() as conn:"
  }
]
\`\`\`
End of observations.
`;
      const result = parseFindings(markdown);
      assertStrictEqual(result.errors.length, 0);
      assertStrictEqual(result.findings.length, 1);
      const f = result.findings[0];
      assertStrictEqual(f.id, 'finding-1');
      assertStrictEqual(f.file, 'providers/foo.py');
      assertStrictEqual(f.line, 100);
      assertStrictEqual(f.severity, 'major');
      assertStrictEqual(f.body, 'Resource leak detected');
      assertStrictEqual(f.rule, 'resource-leak');
      assertStrictEqual(f.fixup, '    with acquire() as conn:');
    });

    test('parses findings nested inside an object property', () => {
      const payload = {
        findings: [
          {
            file: 'test.py',
            line: 5,
            severity: 'nit',
            suggestion: 'Fix indentation',
          },
        ],
      };
      const result = parseFindings(payload);
      assertStrictEqual(result.errors.length, 0);
      assertStrictEqual(result.findings.length, 1);
      assertStrictEqual(result.findings[0].body, 'Fix indentation');
      assertStrictEqual(result.findings[0].severity, 'nit');
    });

    test('handles empty or malformed inputs without throwing exceptions', () => {
      const emptyResult = parseFindings('');
      assertStrictEqual(emptyResult.findings.length, 0);
      assertStrictEqual(emptyResult.errors.length, 0);

      const nullResult = parseFindings(null);
      assertStrictEqual(nullResult.findings.length, 0);

      const invalidJsonResult = parseFindings('invalid { json');
      assertStrictEqual(invalidJsonResult.findings.length, 0);
      assertStrictEqual(invalidJsonResult.errors.length, 1);
      assert(invalidJsonResult.errors[0].includes('JSON parse error'));

      const nonObjectArray = parseFindings(JSON.stringify(['string item', null]));
      assertStrictEqual(nonObjectArray.findings.length, 0);
      assertStrictEqual(nonObjectArray.errors.length, 2);
    });
  });

  describe('PR-2 UI formatters and helpers', () => {
    test('formatSeverityBadge maps severities to labels, colors, and emphasis', () => {
      const blocking = formatSeverityBadge('blocking');
      assertStrictEqual(blocking.label, '[BLOCKING]');
      assertStrictEqual(blocking.color, 'error');
      assertStrictEqual(blocking.bold, true);

      const major = formatSeverityBadge('major');
      assertStrictEqual(major.label, '[MAJOR]');
      assertStrictEqual(major.color, 'error');
      assertStrictEqual(major.bold, false);

      const minor = formatSeverityBadge('minor');
      assertStrictEqual(minor.label, '[MINOR]');
      assertStrictEqual(minor.color, 'warning');
      assertStrictEqual(minor.bold, false);

      const nit = formatSeverityBadge('nit');
      assertStrictEqual(nit.label, '[NIT]');
      assertStrictEqual(nit.color, 'dim');
      assertStrictEqual(nit.bold, false);
    });

    test('formatActionIndicator maps actions to indicator labels and styles', () => {
      const accept = formatActionIndicator('accept');
      assertStrictEqual(accept.label, '[x] Accept');
      assertStrictEqual(accept.color, 'success');
      assertStrictEqual(accept.bold, true);

      const skip = formatActionIndicator('skip');
      assertStrictEqual(skip.label, '[ ] Skip');
      assertStrictEqual(skip.color, 'dim');
      assertStrictEqual(skip.bold, false);

      const edit = formatActionIndicator('edit');
      assertStrictEqual(edit.label, '[E] Edit');
      assertStrictEqual(edit.color, 'info');
      assertStrictEqual(edit.bold, true);
    });

    test('truncateFilePath preserves short paths and abbreviates long deep paths', () => {
      assertStrictEqual(truncateFilePath('short/path.py', 36), 'short/path.py');
      assertStrictEqual(
        truncateFilePath(
          'plugins/magpie-security-tools/tools/security-management/src/state.py',
          30
        ),
        '.../src/state.py'
      );
    });

    test('renderFindingsPane returns null when findings are empty or ui resolution fails', () => {
      const state: ReviewFindingsState = {
        findings: [],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      assertStrictEqual(renderFindingsPane({}, {}, state), null);

      const populatedState: ReviewFindingsState = {
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'minor', body: 'Note', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      assertStrictEqual(renderFindingsPane({}, {}, populatedState), null);
    });

    test('renderFindingsPane builds UI Box tree using resolved components', () => {
      const findings: ReviewFinding[] = [
        {
          id: '1',
          file: 'src/a.py',
          line: 12,
          severity: 'blocking',
          body: 'Flaw',
          rule: 'security',
          action: 'accept',
        },
        {
          id: '2',
          file: 'docs/b.md',
          line: null,
          severity: 'nit',
          body: 'Grammar',
          action: 'skip',
        },
      ];
      const state: ReviewFindingsState = {
        prNumber: 42,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => ({ type: 'Text', ...props });
      const fake$ = {
        ui: {
          resolve: () => ({ Box: mockBox, Text: mockText }),
        },
      };

      const pane = renderFindingsPane(fake$, {}, state);
      assertStrictEqual(pane.type, 'Box');
      assertStrictEqual(Array.isArray(pane.children), true);
    });

    test('renderFindingsPane displays clean overflow indicator without roadmap text', () => {
      const findings: ReviewFinding[] = [];
      for (let i = 1; i <= 14; i += 1) {
        findings.push({
          id: String(i),
          file: `src/file${i}.py`,
          line: i,
          severity: 'minor',
          body: `Finding ${i}`,
          rule: 'style',
          action: 'accept',
        });
      }
      const state: ReviewFindingsState = {
        prNumber: 99,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const collectedTexts: string[] = [];
      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => {
        if (props.children) {
          collectedTexts.push(...props.children);
        }
        return { type: 'Text', ...props };
      };
      const fake$ = {
        ui: {
          resolve: () => ({ Box: mockBox, Text: mockText }),
        },
      };

      renderFindingsPane(fake$, {}, state);
      const overflowText = collectedTexts.find((t) => t.includes('showing'));
      assert(overflowText, 'Expected overflow indicator text');
      assertStrictEqual(overflowText, '... showing 10 of 14 findings');
      assert(!overflowText.includes('PR-3'), 'Must not contain PR-3 delivery plan text');
      assert(!overflowText.includes('scroll or select'), 'Must not contain scroll hint');
    });

    test('renderFindingsPane sanitizes ANSI and control characters in file, rule, and body', () => {
      const findings: ReviewFinding[] = [
        {
          id: '1',
          file: '\u001b[31msrc/dangerous.py\u001b[0m',
          line: 10,
          severity: 'blocking',
          body: '\u001b]8;;https://malicious.link\u0007Dangerous body\u001b]8;;\u0007',
          rule: '\u001b[1;33mrule-injection\u001b[0m',
          action: 'accept',
        },
      ];
      const state: ReviewFindingsState = {
        prNumber: 100,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const collectedTexts: string[] = [];
      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => {
        if (props.children) {
          collectedTexts.push(...props.children);
        }
        return { type: 'Text', ...props };
      };
      const fake$ = {
        ui: {
          resolve: () => ({ Box: mockBox, Text: mockText }),
        },
      };

      renderFindingsPane(fake$, {}, state);
      const combined = collectedTexts.join(' ');
      assert(!combined.includes('\u001b'), 'Rendered text must not contain ANSI escape bytes');
      assert(combined.includes('src/dangerous.py'), 'Expected clean file path');
      assert(combined.includes('rule-injection'), 'Expected clean rule');
      assert(combined.includes('Dangerous body'), 'Expected clean body');
    });
  });

  describe('mod hook registration and Pane UI mounting', () => {
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
      assertStrictEqual(registered.length, 5);
      assertStrictEqual(registered[0].event, 'session.start');
      assertStrictEqual(registered[1].event, 'ui.render');
      assertStrictEqual(registered[1].opts?.component, 'Pane');
      assertStrictEqual(registered[2].event, 'ui.press');
      assertStrictEqual(registered[3].event, 'tool.call');
      assertStrictEqual(registered[3].opts?.tool, 'Bash');
      assertStrictEqual(registered[4].event, 'command.run');
      assertStrictEqual(registered[4].opts?.command, 'magpie-findings');
    });

    test('session.start fixture hydration routes through setReviewFindingsState and invalidates UI', async () => {
      const registered: Array<{ event: string; handler: Function }> = [];
      const fakeOn = (event: string, optsOrHandler: any, handler?: Function) => {
        if (typeof optsOrHandler === 'function') {
          registered.push({ event, handler: optsOrHandler });
        }
      };
      register(fakeOn);

      let invalidatedSurface: string | null = null;
      let nextCalled = false;
      const test$ = createMockEngine({
        ui: {
          invalidate: (surface: string) => {
            invalidatedSurface = surface;
          },
        },
      });
      const fakePayload = {
        prNumber: 555,
        prTitle: 'Sample PR',
        findings: [
          {
            id: '1',
            file: 'src/app.py',
            line: 20,
            severity: 'major',
            body: 'Unused import',
            rule: 'lint',
            action: 'accept',
          },
        ],
      };
      const fakeNext = (payload: any) => {
        nextCalled = true;
        return payload;
      };

      await registered[0].handler(test$, fakePayload, fakeNext);
      assert(nextCalled, 'Handler should chain to next(e)');
      assertStrictEqual(invalidatedSurface, 'ui.render', 'Expected session.start to invalidate ui.render');

      const currentState = await getReviewFindingsState(test$);
      assert(currentState !== null, 'State should be populated from fixture payload');
      assertStrictEqual(currentState?.prNumber, 555);
      assertStrictEqual(currentState?.findings.length, 1);
    });

    test('session.start clears state when event has no findings', async () => {
      const registered: Array<{ event: string; handler: Function }> = [];
      const fakeOn = (event: string, optsOrHandler: any, handler?: Function) => {
        if (typeof optsOrHandler === 'function') {
          registered.push({ event, handler: optsOrHandler });
        }
      };
      register(fakeOn);

      const test$ = createMockEngine();
      await setReviewFindingsState(test$, {
        prNumber: 123,
        findings: [],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      let nextCalled = false;
      const fakeNext = (payload: any) => {
        nextCalled = true;
        return payload;
      };

      await registered[0].handler(test$, { surface: 'terminal' }, fakeNext);
      assert(nextCalled, 'Handler should chain to next(e)');

      const currentState = await getReviewFindingsState(test$);
      assertStrictEqual(currentState, null, 'State should be cleared to null when event has no findings');
    });

    test('ui.render mounts Pane on terminal and desktop surfaces when findings exist', async ($: any, on: any) => {
      on('ui.render', () => ({ type: 'Box', children: [] }));
      on('session.start', () => ({ cwd: '/work' }));

      const testFindings: ReviewFinding[] = [
        {
          id: '1',
          file: 'src/core.py',
          line: 42,
          severity: 'blocking',
          body: 'Security breach detected',
          rule: 'sec-rule',
          action: 'accept',
        },
        {
          id: '2',
          file: 'README.md',
          line: null,
          severity: 'nit',
          body: 'Typo in readme',
          action: 'skip',
        },
      ];

      await $.session.start({
        surface: 'terminal',
        isInteractive: true,
        cwd: '/work',
        prNumber: 1920,
        findings: testFindings,
      });

      for (const surface of ['terminal', 'desktop'] as const) {
        const ui = await $.ui.mount({
          plugin: 'magpie-pr-management',
          surface,
          component: 'Pane',
          props: {},
        });
        const header = await ui.find({ type: 'Text', text: /PR #1920: Review Findings/ });
        assert(header, "Expected header rendered on " + surface);

        const blockingBadge = await ui.find({ type: 'Text', text: /\[BLOCKING\]/ });
        assert(blockingBadge, "Expected blocking badge rendered on " + surface);

        const inlineSection = await ui.find({
          type: 'Text',
          text: /Proposed inline comments:/,
        });
        assert(inlineSection, "Expected inline comments section on " + surface);
      }
    });

    test('ui.render passes through unchanged when state is null or empty', async ($: any, on: any) => {
      on('ui.render', () => ({ type: 'Box', children: [] }));
      on('session.start', () => ({ cwd: '/work' }));

      await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' });

      for (const surface of ['terminal', 'desktop'] as const) {
        const ui = await $.ui.mount({
          plugin: 'magpie-pr-management',
          surface,
          component: 'Pane',
          props: {},
        });
        const found = await ui.find({ type: 'Text', text: /Review Findings/ });
        assertStrictEqual(
          found,
          undefined,
          "Pane should not render findings on " + surface + " when state is null"
        );
      }
    });
  });

  describe('PR-3 Phase 1 pure state mutators and edited findings bridge', () => {
    test('cycleFindingAction deterministically cycles accept -> skip -> edit -> accept', () => {
      assertStrictEqual(cycleFindingAction('accept'), 'skip');
      assertStrictEqual(cycleFindingAction('skip'), 'edit');
      assertStrictEqual(cycleFindingAction('edit'), 'accept');
    });

    test('resolveFindingIndex handles 1-based index, 0-based index, ID, and digit string', () => {
      const state: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          {
            id: 'finding-first',
            file: 'src/main.py',
            line: 10,
            severity: 'blocking',
            body: 'First finding',
            action: 'accept',
          },
          {
            id: 'finding-second',
            file: 'src/utils.py',
            line: 25,
            severity: 'minor',
            body: 'Second finding',
            action: 'skip',
          },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      // 1-based number
      assertStrictEqual(resolveFindingIndex(state, 1), 0);
      assertStrictEqual(resolveFindingIndex(state, 2), 1);
      assertStrictEqual(resolveFindingIndex(state, 3), -1);

      // 0-based or out-of-range returns -1 (1-based only)
      assertStrictEqual(resolveFindingIndex(state, 0), -1);
      assertStrictEqual(resolveFindingIndex(state, 3), -1);

      // String ID
      assertStrictEqual(resolveFindingIndex(state, 'finding-first'), 0);
      assertStrictEqual(resolveFindingIndex(state, 'finding-second'), 1);
      assertStrictEqual(resolveFindingIndex(state, 'nonexistent'), -1);

      // 1-based digit string
      assertStrictEqual(resolveFindingIndex(state, '1'), 0);
      assertStrictEqual(resolveFindingIndex(state, '2'), 1);
      assertStrictEqual(resolveFindingIndex(state, '99'), -1);
    });

    test('updateFindingInState updates finding immutably and recalculates summary', () => {
      const initial: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          {
            id: 'f-1',
            file: 'src/a.py',
            line: 15,
            severity: 'minor',
            body: 'Original note',
            action: 'accept',
            raw: { explanation: 'Original note', extra: 'kept' },
          },
          {
            id: 'f-2',
            file: 'src/b.py',
            line: 30,
            severity: 'nit',
            body: 'Nit note',
            action: 'accept',
          },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      initial.summary = calculateSummary(initial.findings);

      const updated = updateFindingInState(initial, 0, {
        severity: 'blocking',
        action: 'edit',
        body: 'Customized note',
      });

      // Original state untouched
      assertStrictEqual(initial.findings[0].severity, 'minor');
      assertStrictEqual(initial.findings[0].action, 'accept');

      // Updated state
      assertStrictEqual(updated.findings[0].severity, 'blocking');
      assertStrictEqual(updated.findings[0].action, 'edit');
      assertStrictEqual(updated.findings[0].body, 'Customized note');
      assertStrictEqual(updated.summary.blockingCount, 1);
      assertStrictEqual(updated.summary.minorCount, 0);

      // Preserves raw field
      assertDeepStrictEqual((updated.findings[0].raw as any).extra, 'kept');

      // Out of bounds index returns unmodified state
      const invalid = updateFindingInState(initial, 99, { action: 'skip' });
      assertStrictEqual(invalid, initial);
      const negative = updateFindingInState(initial, -1, { action: 'skip' });
      assertStrictEqual(negative, initial);
    });

    test('toggleFindingActionInState rotates action through cycle', () => {
      let state: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          {
            id: 'f-1',
            file: 'src/a.py',
            line: 10,
            severity: 'minor',
            body: 'Note',
            action: 'accept',
          },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      state = toggleFindingActionInState(state, 0);
      assertStrictEqual(state.findings[0].action, 'skip');

      state = toggleFindingActionInState(state, 0);
      assertStrictEqual(state.findings[0].action, 'edit');

      state = toggleFindingActionInState(state, 0);
      assertStrictEqual(state.findings[0].action, 'accept');

      // Invalid index is safe no-op
      const unchanged = toggleFindingActionInState(state, 5);
      assertStrictEqual(unchanged, state);
    });

    test('setBulkActionInState updates all findings or anchored findings only', () => {
      const state: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          {
            id: 'f-1',
            file: 'src/a.py',
            line: 10,
            severity: 'minor',
            body: 'Anchored 1',
            action: 'skip',
          },
          {
            id: 'f-2',
            file: 'src/b.py',
            line: null,
            severity: 'nit',
            body: 'Unanchored',
            action: 'skip',
          },
          {
            id: 'f-3',
            file: 'src/c.py',
            line: 20,
            severity: 'major',
            body: 'Anchored 2',
            action: 'skip',
          },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      // Bulk accept all
      const allAccepted = setBulkActionInState(state, 'accept');
      assertStrictEqual(allAccepted.findings[0].action, 'accept');
      assertStrictEqual(allAccepted.findings[1].action, 'accept');
      assertStrictEqual(allAccepted.findings[2].action, 'accept');

      // Bulk skip anchored only
      const anchoredSkipped = setBulkActionInState(allAccepted, 'skip', true);
      assertStrictEqual(anchoredSkipped.findings[0].action, 'skip');
      assertStrictEqual(anchoredSkipped.findings[1].action, 'accept'); // Unanchored left intact
      assertStrictEqual(anchoredSkipped.findings[2].action, 'skip');
    });

    test('updateSelectedIndexInState clamps index within boundaries', () => {
      const state: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'a.py', line: 1, severity: 'nit', body: 'A', action: 'accept' },
          { id: '2', file: 'b.py', line: 2, severity: 'nit', body: 'B', action: 'accept' },
          { id: '3', file: 'c.py', line: 3, severity: 'nit', body: 'C', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 1,
      };

      // Navigate down
      const down = updateSelectedIndexInState(state, 'down');
      assertStrictEqual(down.selectedIndex, 2);

      // Navigate down past end clamps to last
      const downEnd = updateSelectedIndexInState(down, 'down');
      assertStrictEqual(downEnd.selectedIndex, 2);

      // Navigate up
      const up = updateSelectedIndexInState(downEnd, 'up');
      assertStrictEqual(up.selectedIndex, 1);

      // Navigate up past 0 clamps to 0
      const upStart = updateSelectedIndexInState(updateSelectedIndexInState(up, 'up'), 'up');
      assertStrictEqual(upStart.selectedIndex, 0);

      // Absolute number clamps
      assertStrictEqual(updateSelectedIndexInState(state, 0).selectedIndex, 0);
      assertStrictEqual(updateSelectedIndexInState(state, 2).selectedIndex, 2);
      assertStrictEqual(updateSelectedIndexInState(state, 10).selectedIndex, 2);
      assertStrictEqual(updateSelectedIndexInState(state, -5).selectedIndex, 0);

      // Empty state
      const emptyState: ReviewFindingsState = {
        findings: [],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      assertStrictEqual(updateSelectedIndexInState(emptyState, 'down').selectedIndex, 0);
    });

    test('serializeFindingsForRender explicitly overrides explanation when finding is edited', () => {
      const findings: ReviewFinding[] = [
        {
          id: '1',
          file: 'src/auth.py',
          line: 42,
          severity: 'blocking',
          body: 'Customized explanation by maintainer',
          rule: 'sec-rule-1',
          action: 'edit',
          raw: {
            file: 'src/auth.py',
            line: 42,
            severity: 'blocking',
            explanation: 'Original unedited stale text',
            suggestion: '`python\n# Stale code suggestion\n`',
            rule_id: 'sec-rule-1',
            custom_metadata: 'preserved',
          },
        },
        {
          id: '2',
          file: 'src/db.py',
          line: 100,
          severity: 'minor',
          body: 'Unedited finding',
          rule: 'db-rule',
          action: 'accept',
          raw: {
            file: 'src/db.py',
            line: 100,
            severity: 'minor',
            explanation: 'Original text kept as is',
            rule_id: 'db-rule',
          },
        },
        {
          id: '3',
          file: 'src/lint.py',
          line: 5,
          severity: 'nit',
          body: 'Skipped finding',
          action: 'skip',
          raw: {
            file: 'src/lint.py',
            line: 5,
            severity: 'nit',
            explanation: 'Skipped note',
          },
        },
      ];

      const serializedJson = serializeFindingsForRender(findings);
      const parsed = JSON.parse(serializedJson);

      assertStrictEqual(parsed.length, 3);

      // Item 1 (edited): explanation MUST be updated, suggestion deleted
      assertStrictEqual(parsed[0].explanation, 'Customized explanation by maintainer');
      assertStrictEqual(parsed[0].suggestion, undefined);
      assertStrictEqual(parsed[0].custom_metadata, 'preserved');

      // Item 2 (accepted): explanation preserved from raw
      assertStrictEqual(parsed[1].explanation, 'Original text kept as is');

      // formatKeepAnswer on this mixed list keeps both accept and edit items (1 and 2)
      assertStrictEqual(formatKeepAnswer(findings), '1,2');
    });
  });

  describe('PR-3 Phase 2 interactive UI rendering and ui.press handling', () => {
    test('renderFindingsPane displays selection indicator > on selectedIndex', () => {
      const state: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'blocking', body: 'A', action: 'accept' },
          { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'B', action: 'skip' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 1, // Second finding selected
      };

      const collected: string[] = [];
      const fake$ = {
        ui: {
          resolve: () => ({
            Box: (props: any) => props,
            Text: (props: any) => {
              if (props.children) {
                collected.push(props.children.join(''));
              }
              return props;
            },
          }),
        },
      };

      renderFindingsPane(fake$, {}, state);

      // Verify that cursor '>' was rendered for selected finding and '  ' for unselected
      assert(collected.some((t) => t.includes('>')), 'Expected selection indicator > on selected row');
      assert(collected.some((t) => t.includes('  ')), 'Expected indent on unselected row');
    });

    test('renderFindingsPane resolves Button and provides interactive onPress handlers', async () => {
      let state: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'src/app.py', line: 10, severity: 'blocking', body: 'A', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      const createdButtons: Array<{ key: string; label: string; onPress: Function }> = [];
      const test$ = createMockEngine();
      await setReviewFindingsState(test$, state);

      test$.ui.resolve = () => ({
        Box: (props: any) => props,
        Text: (props: any) => props,
        Button: (props: any) => {
          createdButtons.push(props);
          return props;
        },
      });

      renderFindingsPane(test$, {}, state);

      // Verify toggle button and toolbar buttons were created
      const toggleBtn = createdButtons.find((b) => b.key === 'toggle-1');
      assert(toggleBtn !== undefined, 'Expected toggle-1 Button created');
      assertStrictEqual(toggleBtn?.label, '[x]');

      // Invoke onPress on toggle button
      await toggleBtn?.onPress();
      const updated = await getReviewFindingsState(test$);
      assertStrictEqual(updated?.findings[0].action, 'skip', 'Expected action toggled to skip');

      // Verify accept-all button
      const allBtn = createdButtons.find((b) => b.key === 'accept-all');
      assert(allBtn !== undefined, 'Expected accept-all Button created');
      await allBtn?.onPress();
      const afterAll = await getReviewFindingsState(test$);
      assertStrictEqual(afterAll?.findings[0].action, 'accept', 'Expected action set to accept');
    });

    test('handleUiPress toggles finding action on toggle-<N> element', async () => {
      const test$ = createMockEngine();
      await setReviewFindingsState(test$, {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'blocking', body: 'A', action: 'accept' },
          { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'B', action: 'skip' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      let nextCalled = false;
      const fakeNext = (e: any) => {
        nextCalled = true;
        return e;
      };

      // Press toggle-1: should toggle finding 1 from accept to skip
      const res = await handleUiPress(test$, { element: 'toggle-1' }, fakeNext);
      assertStrictEqual(res?.handled, true);
      assert(!nextCalled, 'next(e) should not be called when handled');

      const s1 = await getReviewFindingsState(test$);
      assertStrictEqual(s1?.findings[0].action, 'skip');

      // Press toggle-1 again: should toggle from skip to edit
      await handleUiPress(test$, { element: 'toggle-1' }, fakeNext);
      const s2 = await getReviewFindingsState(test$);
      assertStrictEqual(s2?.findings[0].action, 'edit');

      // Press toggle-1 again: should toggle from edit to accept
      await handleUiPress(test$, { element: 'toggle-1' }, fakeNext);
      const s3 = await getReviewFindingsState(test$);
      assertStrictEqual(s3?.findings[0].action, 'accept');
    });

    test('handleUiPress handles accept-all and skip-all toolbar elements', async () => {
      const test$ = createMockEngine();
      await setReviewFindingsState(test$, {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'blocking', body: 'A', action: 'skip' },
          { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'B', action: 'skip' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      // Press accept-all
      const resAll = await handleUiPress(test$, { element: 'accept-all' }, () => {});
      assertStrictEqual(resAll?.handled, true);
      const sAll = await getReviewFindingsState(test$);
      assertStrictEqual(sAll?.findings[0].action, 'accept');
      assertStrictEqual(sAll?.findings[1].action, 'accept');

      // Press skip-all
      const resSkip = await handleUiPress(test$, { element: 'skip-all' }, () => {});
      assertStrictEqual(resSkip?.handled, true);
      const sSkip = await getReviewFindingsState(test$);
      assertStrictEqual(sSkip?.findings[0].action, 'skip');
      assertStrictEqual(sSkip?.findings[1].action, 'skip');
    });

    test('handleUiPress handles prev-finding and next-finding navigation', async () => {
      const test$ = createMockEngine();
      await setReviewFindingsState(test$, {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'blocking', body: 'A', action: 'accept' },
          { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'B', action: 'accept' },
          { id: '3', file: 'c.py', line: 30, severity: 'nit', body: 'C', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      // Navigate down to next finding
      await handleUiPress(test$, { element: 'next-finding' }, () => {});
      let state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.selectedIndex, 1);

      await handleUiPress(test$, { element: 'next-finding' }, () => {});
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.selectedIndex, 2);

      // Navigate up to prev finding
      await handleUiPress(test$, { element: 'prev-finding' }, () => {});
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.selectedIndex, 1);
    });

    test('handleUiPress delegates to next when element is unrecognized or state empty', async () => {
      const test$ = createMockEngine();
      await setReviewFindingsState(test$, null);

      let nextCalled = false;
      const fakeNext = (payload: any) => {
        nextCalled = true;
        return { passThrough: true };
      };

      // State is null: should pass through
      const resNull = await handleUiPress(test$, { element: 'toggle-1' }, fakeNext);
      assert(nextCalled, 'Expected pass-through when state is null');
      assertStrictEqual(resNull?.passThrough, true);

      // State populated but element unrecognized: should pass through
      await setReviewFindingsState(test$, {
        prNumber: 1887,
        findings: [{ id: '1', file: 'a.py', line: 1, severity: 'nit', body: 'A', action: 'accept' }],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      nextCalled = false;
      const resUnknown = await handleUiPress(test$, { element: 'other-plugin-button' }, fakeNext);
      assert(nextCalled, 'Expected pass-through when element is unrecognized');
      assertStrictEqual(resUnknown?.passThrough, true);

      // Missing element property: should pass through safely
      nextCalled = false;
      await handleUiPress(test$, {}, fakeNext);
      assert(nextCalled, 'Expected pass-through when element is undefined');
    });
  });

  describe('PR-3 Phase 3 live session feed and zero-token command', () => {
    test('extractFindingsPathFromCommand extracts path across flag formats', () => {
      assertStrictEqual(
        extractFindingsPathFromCommand('uv run disposition --findings saved/findings.json'),
        'saved/findings.json'
      );
      assertStrictEqual(
        extractFindingsPathFromCommand('uv run disposition --findings="saved/findings.json"'),
        'saved/findings.json'
      );
      assertStrictEqual(
        extractFindingsPathFromCommand("uv run disposition --findings='saved/my findings.json'"),
        'saved/my findings.json'
      );
      assertStrictEqual(
        extractFindingsPathFromCommand('uv run disposition --findings=saved/findings.json'),
        'saved/findings.json'
      );
      assertStrictEqual(extractFindingsPathFromCommand('uv run disposition --other flag'), null);
    });

    test('extractPrNumberFromCommand extracts numeric PR number', () => {
      assertStrictEqual(extractPrNumberFromCommand('code-review disposition --pr 1887'), 1887);
      assertStrictEqual(extractPrNumberFromCommand('code-review disposition --pr=42'), 42);
      assertStrictEqual(extractPrNumberFromCommand('code-review disposition --pr -1'), undefined);
      assertStrictEqual(extractPrNumberFromCommand('code-review disposition'), undefined);
    });

    test('resolveRelativePath normalizes paths across base directories', () => {
      assertStrictEqual(resolveRelativePath('/repo', 'saved/findings.json'), '/repo/saved/findings.json');
      assertStrictEqual(resolveRelativePath('/repo/', './saved/findings.json'), '/repo/saved/findings.json');
      assertStrictEqual(resolveRelativePath('/repo', '/absolute/path.json'), '/absolute/path.json');
      assertStrictEqual(resolveRelativePath('/repo', 'C:/work/findings.json'), 'C:/work/findings.json');
    });

    test('handleBashToolCall intercepts disposition, reads findings, and populates atom', async () => {
      const mockFindings = [
        {
          id: '1',
          file: 'src/core.py',
          line: 25,
          severity: 'blocking',
          body: 'Critical security flaw',
          action: 'accept',
        },
      ];

      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
        fs: {
          read: async (path: string) => {
            if (path.includes('findings-1887.json')) {
              return JSON.stringify(mockFindings);
            }
            throw new Error('File not found: ' + path);
          },
        },
      });

      let nextCalled = false;
      const fakeNext = (payload: any) => {
        nextCalled = true;
        return payload;
      };

      const cmd =
        'uv run --project tools/pr-management pr-management code-review disposition --saved-dir saved --pr 1887 --viewer alice --findings saved/findings-1887.json';

      await handleBashToolCall(test$, { command: cmd }, fakeNext);
      assert(nextCalled, 'handleBashToolCall must invoke next(e)');

      const state = await getReviewFindingsState(test$);
      assert(state !== null, 'Expected reviewFindingsState populated from disposition feed');
      assertStrictEqual(state?.prNumber, 1887);
      assertStrictEqual(state?.findings.length, 1);
      assertStrictEqual(state?.findings[0].file, 'src/core.py');
    });

    test('handleBashToolCall fails open when read fails or command is unrelated', async () => {
      const test$ = createMockEngine({
        session: { root: async () => '/work' },
        fs: {
          read: async () => {
            throw new Error('EACCES: permission denied');
          },
        },
      });

      let nextCalled = false;
      const fakeNext = () => {
        nextCalled = true;
        return { executed: true };
      };

      // Disposition where read fails: should not throw, must call next(e)
      const res1 = await handleBashToolCall(
        test$,
        { command: 'code-review disposition --findings missing.json' },
        fakeNext
      );
      assert(nextCalled, 'Must call next(e) on failure');
      assertStrictEqual(res1?.executed, true);

      // Unrelated command: should pass through unchanged
      nextCalled = false;
      const res2 = await handleBashToolCall(test$, { command: 'git status' }, fakeNext);
      assert(nextCalled, 'Must call next(e) on unrelated command');
      assertStrictEqual(res2?.executed, true);
    });

    test('handleFindingsCommand handles status, all, none, keep, drop, and edit', async () => {
      const test$ = createMockEngine();
      await setReviewFindingsState(test$, {
        prNumber: 1887,
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'blocking', body: 'Auth bypass', action: 'accept' },
          { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'Lint issue', action: 'accept' },
          { id: '3', file: 'c.py', line: 30, severity: 'nit', body: 'Style nit', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      // 1. status
      const resStatus = await handleFindingsCommand(test$, { args: 'status' });
      assert(resStatus.text.includes('PR #1887: Review Findings Status'));
      assert(resStatus.text.includes('Keep parameter (--keep): ALL'));

      // 2. none
      const resNone = await handleFindingsCommand(test$, { args: 'none' });
      assert(resNone.text.includes('Keep parameter: NONE'));
      let state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings.every((f) => f.action === 'skip'), true);

      // 3. all
      const resAll = await handleFindingsCommand(test$, { args: 'all' });
      assert(resAll.text.includes('Keep parameter: ALL'));
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings.every((f) => f.action === 'accept'), true);

      // 4. keep 1,3
      const resKeep = await handleFindingsCommand(test$, { args: 'keep 1,3' });
      assert(resKeep.text.includes('Kept: 1,3'));
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings[0].action, 'accept');
      assertStrictEqual(state?.findings[1].action, 'skip');
      assertStrictEqual(state?.findings[2].action, 'accept');

      // 5. drop 3
      const resDrop = await handleFindingsCommand(test$, { args: 'drop 3' });
      assert(resDrop.text.includes('Dropped findings: 3'));
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings[2].action, 'skip');

      // 6. edit 1 New explanation note
      const resEdit = await handleFindingsCommand(test$, { args: 'edit 1 Custom explanation for auth' });
      assert(resEdit.text.includes('Updated finding #1 (marked edit with custom note)'));
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings[0].action, 'edit');
      assertStrictEqual(state?.findings[0].body, 'Custom explanation for auth');

      // 7. empty state
      await setReviewFindingsState(test$, null);
      const resEmpty = await handleFindingsCommand(test$, { args: 'status' });
      assert(resEmpty.text.includes('No active PR review findings'));
    });
  });

    test('resolveFindingIndex correctly maps 1-based index to anchored item in mixed findings', () => {
      const mixedState: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          { id: 'gen-1', file: 'README.md', line: null, severity: 'minor', body: 'Unanchored note', action: 'accept' },
          { id: 'inline-1', file: 'src/main.ts', line: 42, severity: 'blocking', body: 'First anchored finding', action: 'accept' },
          { id: 'inline-2', file: 'src/util.ts', line: 100, severity: 'major', body: 'Second anchored finding', action: 'skip' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      // In Step 7a, item 1 refers to inline-1 (index 1 in state.findings), not gen-1 (index 0)
      assertStrictEqual(resolveFindingIndex(mixedState, 1), 1);
      assertStrictEqual(resolveFindingIndex(mixedState, '1'), 1);
      assertStrictEqual(resolveFindingIndex(mixedState, 2), 2);
      assertStrictEqual(resolveFindingIndex(mixedState, '2'), 2);

      // Out-of-range inline numbers strictly return -1 without falling back to unanchored findings
      assertStrictEqual(resolveFindingIndex(mixedState, 3), -1);
      assertStrictEqual(resolveFindingIndex(mixedState, '3'), -1);

      // General observations addressed by g1, G1
      assertStrictEqual(resolveFindingIndex(mixedState, 'g1'), 0);
      assertStrictEqual(resolveFindingIndex(mixedState, 'G1'), 0);
      assertStrictEqual(resolveFindingIndex(mixedState, 'g2'), -1);

      // Resolving by string ID directly
      assertStrictEqual(resolveFindingIndex(mixedState, 'gen-1'), 0);
      assertStrictEqual(resolveFindingIndex(mixedState, 'inline-1'), 1);
    });

    test('renderFindingsPane generates toggle-general- key and correctly toggles unanchored finding', async () => {
      const test$ = createMockEngine();
      const mixedState: ReviewFindingsState = {
        prNumber: 1887,
        findings: [
          { id: 'gen-1', file: 'README.md', line: null, severity: 'minor', body: 'General note', action: 'accept' },
          { id: 'inline-1', file: 'src/main.ts', line: 42, severity: 'blocking', body: 'Inline note', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      await setReviewFindingsState(test$, mixedState);

      const mock$ = {
        ui: {
          resolve: () => ({
            Box: (props: any) => props,
            Text: (props: any) => props,
            Button: (props: any) => props,
          }),
        },
      };
      const tree = renderFindingsPane(mock$, {}, mixedState);
      assert(tree !== null, 'renderFindingsPane should render UI tree');

      // Simulate pressing toggle-general-1 via handleUiPress
      await handleUiPress(test$, { element: 'toggle-general-1' }, () => {});
      let cur = await getReviewFindingsState(test$);
      assert(cur !== null);
      assertStrictEqual(cur?.findings[0].action, 'skip');
      assertStrictEqual(cur?.findings[1].action, 'accept');

      // Now simulate pressing toggle-1 (the first anchored finding)
      await handleUiPress(test$, { element: 'toggle-1' }, () => {});
      cur = await getReviewFindingsState(test$);
      assert(cur?.findings[1].action === 'skip', `Expected skip but got ${cur?.findings[1].action}`);
    });

    test('extractFindingsPathFromCommand handles multiline escaped line breaks in bash commands', () => {
      const multiline = 'uv run disposition \\\n  --findings \\\n  saved/findings-1887.json \\\n  --pr 1887';
      const extracted = extractFindingsPathFromCommand(multiline);
      assertStrictEqual(extracted, 'saved/findings-1887.json');
    });

    test('handleBashToolCall resets atom to null when file read fails or content is empty', async () => {
      const failingTest$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
        fs: {
          read: async () => {
            throw new Error('ENOENT: file not found');
          },
        },
      });

      await setReviewFindingsState(failingTest$, {
        prNumber: 1887,
        findings: [{ id: 'old', file: 'a.py', line: 10, severity: 'minor', body: 'Old', action: 'accept' }],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      await handleBashToolCall(
        failingTest$,
        { command: 'uv run pr-management code-review disposition --findings saved/missing.json' },
        () => {}
      );
      assertStrictEqual(await getReviewFindingsState(failingTest$), null);

      // Empty string content
      const emptyContentTest$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
        fs: {
          read: async () => '',
        },
      });

      await setReviewFindingsState(emptyContentTest$, {
        prNumber: 1887,
        findings: [{ id: 'old', file: 'a.py', line: 10, severity: 'minor', body: 'Old', action: 'accept' }],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      await handleBashToolCall(
        emptyContentTest$,
        { command: 'uv run pr-management code-review disposition --findings saved/empty.json' },
        () => {}
      );
      assertStrictEqual(await getReviewFindingsState(emptyContentTest$), null);
    });

    test('handleBashToolCall resets atom to null when findings payload is empty', async () => {
      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
        fs: {
          read: async () => JSON.stringify([]), // Empty findings array
        },
      });

      await setReviewFindingsState(test$, {
        prNumber: 1887,
        findings: [{ id: 'old', file: 'a.py', line: 10, severity: 'minor', body: 'Old', action: 'accept' }],
        summary: calculateSummary([]),
        selectedIndex: 0,
      });

      let nextCalled = false;
      await handleBashToolCall(
        test$,
        { command: 'uv run code-review disposition --findings saved/clean.json --pr 1887' },
        async () => { nextCalled = true; }
      );

      assert(nextCalled, 'next must be called (fail-open)');
      const finalState = await getReviewFindingsState(test$);
      assertStrictEqual(finalState, null, 'State atom must be reset to null on empty findings');
    });


  describe('PR-3 End-to-End Simulation: Full Lifecycle from Step 6 to Step 7b', () => {
    test('simulates complete review lifecycle: disposition -> render pane -> toggle inline -> edit finding -> keep answer & render payload', async () => {
      // Step 4/6 payload with mixed findings: 1 general observation, 2 inline comments
      const rawFindings = [
        {
          id: 'gen-arch-1',
          file: 'docs/architecture.md',
          line: null,
          severity: 'minor',
          body: 'Architecture diagram should reflect new mod hook routing',
          explanation: 'Architecture diagram should reflect new mod hook routing',
          action: 'accept',
        },
        {
          id: 'inline-auth-1',
          file: 'src/auth/provider.ts',
          line: 42,
          severity: 'blocking',
          body: 'Potential null pointer dereference on user session token',
          explanation: 'Potential null pointer dereference on user session token',
          action: 'accept',
        },
        {
          id: 'inline-perf-2',
          file: 'src/utils/cache.ts',
          line: 128,
          severity: 'major',
          body: 'Unbounded map allocation without LRU eviction policy',
          explanation: 'Unbounded map allocation without LRU eviction policy',
          action: 'accept',
        },
      ];

      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
        fs: {
          read: async (path: string) => {
            if (path.includes('findings-1887.json')) {
              return JSON.stringify(rawFindings);
            }
            throw new Error('File not found: ' + path);
          },
        },
      });

      // 1. STEP 6 INTERCEPTION: Bash tool call executes disposition
      let toolNextCalled = false;
      await handleBashToolCall(
        test$,
        {
          command:
            'uv run --project tools/pr-management pr-management code-review disposition \
  --findings saved/findings-1887.json \
  --pr 1887',
        },
        async (e: any) => {
          toolNextCalled = true;
          return e;
        }
      );
      assert(toolNextCalled, 'tool.call must fail-open and call next(e)');

      // Verify atom is hydrated with parsed findings
      let state = await getReviewFindingsState(test$);
      assert(state !== null, 'Atom state must be populated after disposition');
      assertStrictEqual(state?.prNumber, 1887);
      assertStrictEqual(state?.findings.length, 3);
      assertStrictEqual(state?.summary.anchoredCount, 2);
      assertStrictEqual(state?.summary.unanchoredCount, 1);

      // 2. STEP 7a PRESENTATION: Pane renders with interactive buttons
      const mockUi$ = {
        ui: {
          resolve: () => ({
            Box: (props: any) => props,
            Text: (props: any) => props,
            Button: (props: any) => props,
          }),
        },
      };
      const renderedTree = renderFindingsPane(mockUi$, {}, state!);
      assert(renderedTree !== null, 'Pane tree must be rendered');

      // 3. INTERACTION A: Maintainer skips the second inline finding using UI press
      // In Step 7a, inline-perf-2 is inline comment #2
      await handleUiPress(test$, { element: 'toggle-2' }, () => {});
      state = await getReviewFindingsState(test$);
      assert(state !== null);
      // inline-perf-2 (index 2 in state.findings) is now skipped
      assertStrictEqual(state?.findings[2].action, 'skip');
      // inline-auth-1 (index 1 in state.findings) remains accepted
      assertStrictEqual(state?.findings[1].action, 'accept');

      // 4. INTERACTION B: Maintainer edits inline comment #1 via /magpie-findings
      const editResult = await handleFindingsCommand(test$, {
        args: 'edit 1 Explicitly guard user session token before verification',
      });
      assert(editResult.text.includes('Updated finding #1'));
      state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings[1].action, 'edit');
      assertStrictEqual(
        state?.findings[1].body,
        'Explicitly guard user session token before verification'
      );

      // 5. STEP 7b PREPARATION: Generate keep answer for `render --keep <answer>`
      const keepAnswer = formatKeepAnswer(state!.findings);
      // Only inline comment 1 is kept (edited counts as kept; comment 2 is skipped)
      assertStrictEqual(keepAnswer, '1');

      // 6. STEP 7b SERIALIZATION: Generate findings payload for `render --findings <file>`
      const serializedJson = serializeFindingsForRender(state!.findings);
      const parsedCurated = JSON.parse(serializedJson);
      assertStrictEqual(parsedCurated.length, 3);

      // Verify that the edited explanation reached the render payload
      assertStrictEqual(
        parsedCurated[1].explanation,
        'Explicitly guard user session token before verification'
      );
      assertStrictEqual(parsedCurated[1].file, 'src/auth/provider.ts');
      assertStrictEqual(parsedCurated[1].line, 42);

      // 7. STEP 8 CLEANUP: When a clean PR runs disposition with 0 findings, atom resets
      const clean$ = createMockEngine({
        session: { root: async () => '/work/repo', cwd: async () => '/work/repo' },
        fs: { read: async () => JSON.stringify([]) },
      });
      await setReviewFindingsState(clean$, state);
      await handleBashToolCall(
        clean$,
        { command: 'uv run code-review disposition --findings saved/clean.json --pr 1888' },
        async () => {}
      );
      const cleanState = await getReviewFindingsState(clean$);
      assertStrictEqual(cleanState, null, 'Clean PR review must reset the reviewFindingsState atom to null');
    });
  });

  describe('PR-3 Phase 4 type synchronization and ambient declaration parity', () => {
    test('ReviewFindingsState conforms to ambient PluginState magpie-pr-management declaration', () => {
      const sampleState: ReviewFindingsState = {
        prNumber: 1887,
        prTitle: 'Interactive findings pane',
        findings: [
          {
            id: 'finding-1',
            file: 'src/core.ts',
            line: 42,
            severity: 'blocking',
            body: 'Unchecked array index',
            rule: 'no-unchecked-index',
            source: 'primary',
            fixup: null,
            action: 'accept',
            raw: { original: true },
          },
        ],
        summary: {
          blockingCount: 1,
          majorCount: 0,
          minorCount: 0,
          nitCount: 0,
          total: 1,
          anchoredCount: 1,
          unanchoredCount: 0,
        },
        selectedIndex: 0,
      };

      type AmbientState = import('claude-code').PluginState['magpie-pr-management']['reviewFindingsState'];
      const ambientValue: AmbientState = sampleState;
      assert(ambientValue !== null);
      assertStrictEqual(ambientValue?.prNumber, 1887);
      assertStrictEqual(ambientValue?.findings[0].action, 'accept');
      assertStrictEqual(ambientValue?.summary.total, 1);
      assertStrictEqual(ambientValue?.selectedIndex, 0);

      const nullAmbient: AmbientState = null;
      assertStrictEqual(nullAmbient, null);
    });

    test('all FindingSeverity, FindingSource, and FindingAction variants are accepted in state', () => {
      const severities: Array<ReviewFinding['severity']> = ['blocking', 'major', 'minor', 'nit'];
      const sources: Array<NonNullable<ReviewFinding['source']>> = ['primary', 'adversarial', 'both'];
      const actions: Array<ReviewFinding['action']> = ['accept', 'skip', 'edit'];

      for (const sev of severities) {
        for (const src of sources) {
          for (const act of actions) {
            const f: ReviewFinding = {
              id: 'finding-' + sev + '-' + src + '-' + act,
              file: 'a.py',
              line: 10,
              severity: sev,
              body: 'Finding text',
              source: src,
              action: act,
            };
            assertStrictEqual(f.severity, sev);
            assertStrictEqual(f.source, src);
            assertStrictEqual(f.action, act);
          }
        }
      }
    });
  });

  describe('PR-4 Curated findings bridge and general observation filtering', () => {
    test('getCuratedFindingsPaths derives .curated.json and .curated.keep paths', () => {
      const pathsJson = getCuratedFindingsPaths('saved/findings-1887.json');
      assertStrictEqual(pathsJson.curatedJsonPath, 'saved/findings-1887.curated.json');
      assertStrictEqual(pathsJson.curatedKeepPath, 'saved/findings-1887.curated.keep');

      const pathsNoExt = getCuratedFindingsPaths('saved/findings-1887');
      assertStrictEqual(pathsNoExt.curatedJsonPath, 'saved/findings-1887.curated.json');
      assertStrictEqual(pathsNoExt.curatedKeepPath, 'saved/findings-1887.curated.keep');
    });

    test('serializeFindingsForRender omits skipped unanchored findings while preserving anchored findings', () => {
      const findings: ReviewFinding[] = [
        { id: 'inline-1', file: 'a.py', line: 10, severity: 'minor', body: 'Inline 1', action: 'accept' },
        { id: 'gen-1', file: 'README.md', line: null, severity: 'major', body: 'General 1', action: 'skip' },
        { id: 'inline-2', file: 'b.py', line: 20, severity: 'nit', body: 'Inline 2', action: 'skip' },
        { id: 'gen-2', file: 'CONTRIBUTING.md', line: null, severity: 'minor', body: 'General 2', action: 'accept' },
      ];

      const serialized = serializeFindingsForRender(findings);
      const parsed = JSON.parse(serialized);

      // Anchored findings: inline-1 (accept) and inline-2 (skip) are both in the file
      // (their posting/folding is controlled by render --keep)
      // Unanchored findings: gen-1 (skip) is omitted, gen-2 (accept) is preserved
      assertStrictEqual(parsed.length, 3);
      assertStrictEqual(parsed[0].file, 'a.py');
      assertStrictEqual(parsed[1].file, 'b.py');
      assertStrictEqual(parsed[2].file, 'CONTRIBUTING.md');
    });

    test('syncCuratedStateToDisk writes both curated JSON and keep answer to disk', async () => {
      const test$ = createMockEngine();
      const state: ReviewFindingsState = {
        prNumber: 1887,
        findingsPath: '/work/saved/findings-1887.json',
        findings: [
          { id: 'f1', file: 'a.py', line: 10, severity: 'minor', body: 'Note 1', action: 'accept' },
          { id: 'f2', file: 'b.py', line: 20, severity: 'nit', body: 'Note 2', action: 'edit' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      test$.fs._files.set('/work/saved/findings-1887.json', '[]');
      const result = await syncCuratedStateToDisk(test$, state);
      assert(result !== null);
      assertStrictEqual(result?.jsonPath, '/work/saved/findings-1887.curated.json');
      assertStrictEqual(result?.keepPath, '/work/saved/findings-1887.curated.keep');

      const writtenJson = await test$.fs.read('/work/saved/findings-1887.curated.json');
      const parsed = JSON.parse(writtenJson);
      assertStrictEqual(parsed.schema_version, 1);
      assertStrictEqual(parsed.pr, 1887);
      assertStrictEqual(parsed.findings.length, 2);

      const writtenKeep = await test$.fs.read('/work/saved/findings-1887.curated.keep');
      assertStrictEqual(writtenKeep, 'ALL');
    });

    test('handleBashToolCall sets findingsPath and hydrates state, but does NOT write curated files upon initial disposition', async () => {
      const sampleFindings = JSON.stringify([
        { file: 'main.py', line: 42, severity: 'minor', explanation: 'Needs fix' },
      ]);

      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
      });
      test$.fs._files.set('/work/repo/saved/findings-999.json', sampleFindings);

      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-999.json --pr 999' },
        () => {}
      );

      const state = await getReviewFindingsState(test$);
      assert(state !== null);
      assertStrictEqual(state?.findingsPath, '/work/repo/saved/findings-999.json');

      // Verify curated files were NOT written upfront on initial disposition
      assert(!test$.fs._files.has('/work/repo/saved/findings-999.curated.json'));
      assert(!test$.fs._files.has('/work/repo/saved/findings-999.curated.keep'));
    });

    test('renderFindingsPane button onPress callbacks update state and sync curated files to disk', async () => {
      const mockButtonCallbacks = new Map<string, () => Promise<void>>();
      const MockButton = (props: any) => {
        if (props?.key && typeof props?.onPress === 'function') {
          mockButtonCallbacks.set(props.key, props.onPress);
        }
        return { type: 'button', ...props };
      };

      const test$ = createMockEngine({
        ui: {
          resolve: () => ({
            Box: (props: any) => props,
            Text: (props: any) => props,
            Button: MockButton,
          }),
        },
      });

      const state: ReviewFindingsState = {
        prNumber: 1887,
        findingsPath: '/work/saved/findings-1887.json',
        findings: [
          { id: 'f1', file: 'a.py', line: 10, severity: 'minor', body: 'Inline 1', action: 'accept' },
          { id: 'f2', file: 'b.py', line: 20, severity: 'nit', body: 'Inline 2', action: 'accept' },
          { id: 'g1', file: 'README.md', line: null, severity: 'minor', body: 'General 1', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      test$.fs._files.set('/work/saved/findings-1887.json', '[]');
      await setReviewFindingsState(test$, state);

      renderFindingsPane(test$, {}, state);

      // Trigger [None] button onPress
      const skipAllCb = mockButtonCallbacks.get('skip-all');
      assert(typeof skipAllCb === 'function', 'skip-all button callback must be registered');
      await skipAllCb!();

      let curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[0].action, 'skip');
      assertStrictEqual(curState?.findings[1].action, 'skip');

      // Verify disk sync happened from button onPress
      const writtenKeep = await test$.fs.read('/work/saved/findings-1887.curated.keep');
      assertStrictEqual(writtenKeep, 'NONE');

      // Trigger row toggle onPress
      renderFindingsPane(test$, {}, curState!);
      const toggleCb = mockButtonCallbacks.get('toggle-1');
      assert(typeof toggleCb === 'function', 'toggle-1 button callback must be registered');
      await toggleCb!();

      curState = await getReviewFindingsState(test$);
      // 'skip' toggles to 'edit'
      assertStrictEqual(curState?.findings[0].action, 'edit');

      const updatedKeep = await test$.fs.read('/work/saved/findings-1887.curated.keep');
      assertStrictEqual(updatedKeep, '1');
    });

    test('handleBashToolCall preserves existing maintainer curation across disposition re-runs', async () => {
      const initialFindings = JSON.stringify([
        { file: 'auth.py', line: 15, severity: 'major', explanation: 'Original note 1', rule: 'sec-rule-1' },
        { file: 'auth.py', line: 55, severity: 'minor', explanation: 'Original note 2', rule: 'style-rule-2' },
      ]);

      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
      });
      test$.fs._files.set('/work/repo/saved/findings-123.json', initialFindings);

      // 1. Initial disposition runs
      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-123.json --pr 123' },
        () => {}
      );

      // 2. Maintainer curates: drops finding 1 and edits finding 2
      await handleFindingsCommand(test$, { args: 'drop 1' });
      await handleFindingsCommand(test$, { args: 'edit 2 Sanitized custom explanation' });

      let state = await getReviewFindingsState(test$);
      assertStrictEqual(state?.findings[0].action, 'skip');
      assertStrictEqual(state?.findings[1].action, 'edit');
      assertStrictEqual(state?.findings[1].body, 'Sanitized custom explanation');

      // 3. Disposition re-runs (e.g. after maintainer [E]dits or checks CI)
      const updatedFindings = JSON.stringify([
        { file: 'auth.py', line: 15, severity: 'major', explanation: 'Fresh parser note 1', rule: 'sec-rule-1' },
        { file: 'auth.py', line: 55, severity: 'minor', explanation: 'Fresh parser note 2', rule: 'style-rule-2' },
        { file: 'auth.py', line: 99, severity: 'nit', explanation: 'Brand new finding', rule: 'nit-rule-3' },
      ]);
      test$.fs._files.set('/work/repo/saved/findings-123.json', updatedFindings);

      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-123.json --pr 123' },
        () => {}
      );

      state = await getReviewFindingsState(test$);
      assert(state !== null);
      assertStrictEqual(state?.findings.length, 3);
      // Finding 1 preserved as 'skip'
      assertStrictEqual(state?.findings[0].action, 'skip');
      // Finding 2 preserved as 'edit' with custom body
      assertStrictEqual(state?.findings[1].action, 'edit');
      assertStrictEqual(state?.findings[1].body, 'Sanitized custom explanation');
      // Finding 3 is new, defaults to 'accept'
      assertStrictEqual(state?.findings[2].action, 'accept');
    });

    test('disposition cleans up orphaned curated files when findings become empty', async () => {
      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
      });
      test$.fs._files.set('/work/repo/saved/findings-empty.json', '[]');
      test$.fs._files.set('/work/repo/saved/findings-empty.curated.json', '[{"file":"old.py"}]');
      test$.fs._files.set('/work/repo/saved/findings-empty.curated.keep', '1');

      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-empty.json --pr 404' },
        () => {}
      );

      const state = await getReviewFindingsState(test$);
      assertStrictEqual(state, null);

      // Verify orphaned sidecars were marked as invalidated on disk
      const jsonContent = await test$.fs.read('/work/repo/saved/findings-empty.curated.json');
      const parsed = JSON.parse(jsonContent);
      assertStrictEqual(parsed.invalidated, true);
      assertStrictEqual(parsed.findings.length, 0);

      const keepContent = await test$.fs.read('/work/repo/saved/findings-empty.curated.keep');
      assertStrictEqual(keepContent, 'INVALIDATED');
    });

    test('strict token validation rejects letters and decouples gN in keep and drop commands', async () => {
      const test$ = createMockEngine();
      const state: ReviewFindingsState = {
        prNumber: 2005,
        findingsPath: '/work/saved/findings-2005.json',
        findings: [
          { id: 'f1', file: 'a.py', line: 10, severity: 'minor', body: 'Inline 1', action: 'accept' },
          { id: 'f2', file: 'b.py', line: 20, severity: 'major', body: 'Inline 2', action: 'accept' },
          { id: 'g1', file: 'README.md', line: null, severity: 'minor', body: 'General 1', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      test$.fs._files.set('/work/saved/findings-1887.json', '[]');
      await setReviewFindingsState(test$, state);

      // 1. keep abc must fail validation and NOT touch state
      const badKeepRes = await handleFindingsCommand(test$, { args: 'keep abc' });
      assert(badKeepRes.text.startsWith('Error: Invalid token "abc"'));
      let curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[0].action, 'accept');
      assertStrictEqual(curState?.findings[1].action, 'accept');

      // 2. drop abc must fail validation and NOT touch state
      const badDropRes = await handleFindingsCommand(test$, { args: 'drop abc' });
      assert(badDropRes.text.startsWith('Error: Invalid token "abc"'));

      // 3. keep g1 must ONLY modify general observations, leaving anchored findings untouched
      await handleFindingsCommand(test$, { args: 'keep g1' });
      curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[0].action, 'accept', 'Anchored 1 must remain accept');
      assertStrictEqual(curState?.findings[1].action, 'accept', 'Anchored 2 must remain accept');
      assertStrictEqual(curState?.findings[2].action, 'accept', 'General 1 must remain accept');

      // 4. keep 1 must ONLY modify anchored findings, leaving general observations untouched
      await handleFindingsCommand(test$, { args: 'keep 1' });
      curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[0].action, 'accept', 'Anchored 1 kept');
      assertStrictEqual(curState?.findings[1].action, 'skip', 'Anchored 2 skipped');
      assertStrictEqual(curState?.findings[2].action, 'accept', 'General 1 must remain accept');

      // 5. drop g1 must mark general observation as skip without touching anchored
      await handleFindingsCommand(test$, { args: 'drop g1' });
      curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[0].action, 'accept');
      assertStrictEqual(curState?.findings[1].action, 'skip');
      assertStrictEqual(curState?.findings[2].action, 'skip');

      // 6. keep 1, g1 updates both
      await handleFindingsCommand(test$, { args: 'keep 1, g1' });
      curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[0].action, 'accept');
      assertStrictEqual(curState?.findings[1].action, 'skip');
      assertStrictEqual(curState?.findings[2].action, 'accept');
    });

    test('sync error records syncError on state and displays warning in pane and status', async () => {
      const writtenFiles = new Set<string>();
      let warningNodeFound = false;
      const MockText = (props: any) => {
        if (props?.children && props.children[0]?.includes('Warning: Curation sync to disk failed')) {
          warningNodeFound = true;
        }
        return { type: 'text', ...props };
      };

      const writtenFileContents = new Map<string, string>();
      const failingTest$ = createMockEngine({
        fs: {
          exists: async () => true,
          read: async () => '[]',
          write: async (path: string, content: string) => {
            if (path.endsWith('.keep')) {
              throw new Error('EACCES: permission denied');
            }
            writtenFileContents.set(path, content);
          },
        },
        ui: {
          resolve: () => ({
            Box: (props: any) => props,
            Text: MockText,
          }),
        },
      });

      const state: ReviewFindingsState = {
        prNumber: 2005,
        findingsPath: '/work/readonly/findings.json',
        findings: [
          { id: 'f1', file: 'a.py', line: 10, severity: 'minor', body: 'Inline 1', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      await setReviewFindingsState(failingTest$, state);

      // Perform curation action that triggers write
      const res = await handleFindingsCommand(failingTest$, { args: 'none' });
      assert(res.text.includes('Warning: sync to disk failed: EACCES: permission denied'));

      const curState = await getReviewFindingsState(failingTest$);
      assert(curState?.syncError !== null && curState?.syncError !== undefined);
      assert(curState?.syncError.includes('EACCES: permission denied'));

      // Verify partial file was marked as invalidated on disk so Step 7b falls back to original findings
      const jsonContent = writtenFileContents.get('/work/readonly/findings.curated.json');
      assert(jsonContent !== undefined);
      const parsed = JSON.parse(jsonContent!);
      assertStrictEqual(parsed.invalidated, true);
      assertStrictEqual(parsed.findings.length, 0);

      // Verify warning renders in /magpie-findings status
      const statusRes = await handleFindingsCommand(failingTest$, { args: 'status' });
      assert(statusRes.text.includes('Warning: Curation sync to disk failed'));

      // Verify warning renders in pane Box
      renderFindingsPane(failingTest$, {}, curState!);
      assert(warningNodeFound, 'Warning node must be rendered in pane when syncError is set');
    });

    test('handleUiPress and handleFindingsCommand update curated files on disk', async () => {
      const test$ = createMockEngine();
      const state: ReviewFindingsState = {
        prNumber: 1887,
        findingsPath: '/work/saved/findings-1887.json',
        findings: [
          { id: 'f1', file: 'a.py', line: 10, severity: 'minor', body: 'Inline 1', action: 'accept' },
          { id: 'g1', file: 'README.md', line: null, severity: 'minor', body: 'General 1', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      test$.fs._files.set('/work/saved/findings-1887.json', '[]');
      await setReviewFindingsState(test$, state);
      await syncCuratedStateToDisk(test$, state);

      // Button click to toggle general finding to skip
      await handleUiPress(test$, { element: 'toggle-general-1' }, () => {});

      let curatedJson = await test$.fs.read('/work/saved/findings-1887.curated.json');
      let parsed = JSON.parse(curatedJson);
      // General finding g1 is skipped, so omitted from curated JSON
      assertStrictEqual(parsed.findings.length, 1);
      assertStrictEqual(parsed.findings[0].file, 'a.py');

      // Slash command to edit inline 1
      await handleFindingsCommand(test$, { args: 'edit 1 Maintainer customized review note' });

      curatedJson = await test$.fs.read('/work/saved/findings-1887.curated.json');
      parsed = JSON.parse(curatedJson);
      assertStrictEqual(parsed.findings[0].explanation, 'Maintainer customized review note');

      // Drop command with general identifier
      await handleFindingsCommand(test$, { args: 'drop g1' });
      const curState = await getReviewFindingsState(test$);
      assertStrictEqual(curState?.findings[1].action, 'skip');

      // Keep command with general identifier
      await handleFindingsCommand(test$, { args: 'keep 1, g1' });
      const keptState = await getReviewFindingsState(test$);
      assertStrictEqual(keptState?.findings[0].action, 'accept');
      assertStrictEqual(keptState?.findings[1].action, 'accept');
    });

    test('serializeFindingsForRender on edit deletes base.comment and overrides explanation', () => {
      const rawFindingWithComment = {
        file: 'api.py',
        line: 42,
        severity: 'minor',
        comment: 'Raw unedited inline comment from detector',
        explanation: 'Raw explanation',
        suggestion: '-foo()\n+bar()',
      };

      const findings: ReviewFinding[] = [
        {
          id: 'f1',
          file: 'api.py',
          line: 42,
          severity: 'minor',
          body: 'Maintainer revised human comment',
          action: 'edit',
          raw: rawFindingWithComment,
        },
      ];

      const serialized = serializeFindingsForRender(findings);
      const parsed = JSON.parse(serialized);
      assertStrictEqual(parsed.length, 1);
      // base.comment must be deleted on edit so render does not fall back to unedited raw comment
      assertStrictEqual(parsed[0].comment, undefined);
      assertStrictEqual(parsed[0].suggestion, undefined);
      assertStrictEqual(parsed[0].explanation, 'Maintainer revised human comment');

      // Envelope mode
      const envelopeSerialized = serializeFindingsForRender(findings, {
        pr: 2005,
        sourceHash: 'testhash123',
      });
      const envelopeParsed = JSON.parse(envelopeSerialized);
      assertStrictEqual(envelopeParsed.schema_version, 1);
      assertStrictEqual(envelopeParsed.pr, 2005);
      assertStrictEqual(envelopeParsed.source_sha256, 'testhash123');
      assertStrictEqual(envelopeParsed.findings[0].comment, undefined);
      assertStrictEqual(envelopeParsed.findings[0].explanation, 'Maintainer revised human comment');
    });

    test('isCuratedSidecarValid verifies schema, PR number, hash, and invalidation marker', () => {
      const sourceContent = JSON.stringify([{ file: 'main.py', line: 1 }]);
      const sourceHash = computeFindingsHash(sourceContent);

      const validPayload = JSON.stringify({
        schema_version: 1,
        pr: 2005,
        source_sha256: sourceHash,
        findings: [{ file: 'main.py', line: 1 }],
      });
      assert(isCuratedSidecarValid(validPayload, 2005, sourceContent));

      // Mismatched PR number
      assert(!isCuratedSidecarValid(validPayload, 999, sourceContent));

      // Mismatched source content / hash
      assert(!isCuratedSidecarValid(validPayload, 2005, 'different source content'));

      // Explicitly invalidated marker
      const invalidatedPayload = JSON.stringify({
        schema_version: 1,
        pr: null,
        source_sha256: null,
        invalidated: true,
        findings: [],
      });
      assert(!isCuratedSidecarValid(invalidatedPayload, 2005, sourceContent));

      // Null, empty, or malformed JSON
      assert(!isCuratedSidecarValid(null, 2005, sourceContent));
      assert(!isCuratedSidecarValid('', 2005, sourceContent));
      assert(!isCuratedSidecarValid('not json', 2005, sourceContent));
    });

    test('cleanCuratedFindingsFiles does not create sidecar files when none exist on disk', async () => {
      const test$ = createMockEngine();
      // Neither findings file nor curated sidecars exist in test$.fs._files
      await cleanCuratedFindingsFiles(test$, '/work/nonexistent/findings.json');
      assert(!test$.fs._files.has('/work/nonexistent/findings.curated.json'));
      assert(!test$.fs._files.has('/work/nonexistent/findings.curated.keep'));
    });

    test('handleBashToolCall re-syncs curated sidecars on disposition re-run after edit', async () => {
      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
      });

      const initialSource = JSON.stringify([
        { file: 'app.py', line: 10, severity: 'minor', explanation: 'Initial note 1' },
        { file: 'app.py', line: 20, severity: 'minor', explanation: 'Initial note 2' },
      ]);
      test$.fs._files.set('/work/repo/saved/findings-run.json', initialSource);

      // 1. Initial disposition (does NOT write sidecars)
      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-run.json --pr 100' },
        () => {}
      );
      assert(!test$.fs._files.has('/work/repo/saved/findings-run.curated.json'));

      // 2. Maintainer curates (which writes sidecars to disk)
      await handleFindingsCommand(test$, { args: 'drop 1' });
      assert(test$.fs._files.has('/work/repo/saved/findings-run.curated.json'));
      let curatedOnDisk = JSON.parse(await test$.fs.read('/work/repo/saved/findings-run.curated.json'));
      assertStrictEqual(curatedOnDisk.source_sha256, computeFindingsHash(initialSource));

      // 3. Maintainer edits raw findings file (e.g. via [E]dit) and re-runs disposition
      const editedSource = JSON.stringify([
        { file: 'app.py', line: 10, severity: 'minor', explanation: 'Rewritten note 1' },
        { file: 'app.py', line: 20, severity: 'minor', explanation: 'Rewritten note 2' },
      ]);
      test$.fs._files.set('/work/repo/saved/findings-run.json', editedSource);

      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-run.json --pr 100' },
        () => {}
      );

      // Verify sidecars on disk were re-synced with editedSource's new hash and curation preserved
      curatedOnDisk = JSON.parse(await test$.fs.read('/work/repo/saved/findings-run.curated.json'));
      assertStrictEqual(curatedOnDisk.pr, 100);
      assertStrictEqual(curatedOnDisk.source_sha256, computeFindingsHash(editedSource));
      assertStrictEqual(curatedOnDisk.findings.length, 2);
    });

    test('handleBashToolCall invalidates curated sidecars on PR mismatch when path is reused', async () => {
      const test$ = createMockEngine({
        session: {
          root: async () => '/work/repo',
          cwd: async () => '/work/repo',
        },
      });

      // Sidecars pre-exist for PR 100
      test$.fs._files.set(
        '/work/repo/saved/findings-shared.json',
        JSON.stringify([{ file: 'a.py', line: 5, severity: 'minor', explanation: 'A' }])
      );
      test$.fs._files.set(
        '/work/repo/saved/findings-shared.curated.json',
        JSON.stringify({ schema_version: 1, pr: 100, source_sha256: 'old', findings: [] })
      );
      test$.fs._files.set('/work/repo/saved/findings-shared.curated.keep', '1');

      // Re-running disposition on a different PR (PR 200) with the same shared findings path
      await handleBashToolCall(
        test$,
        { command: 'uv run pr-management code-review disposition --findings saved/findings-shared.json --pr 200' },
        () => {}
      );

      // Existing sidecar on disk must be marked as invalidated
      const jsonContent = await test$.fs.read('/work/repo/saved/findings-shared.curated.json');
      const parsed = JSON.parse(jsonContent);
      assertStrictEqual(parsed.invalidated, true);

      const keepContent = await test$.fs.read('/work/repo/saved/findings-shared.curated.keep');
      assertStrictEqual(keepContent, 'INVALIDATED');
    });

    test('syncCuratedStateToDisk refuses to write sidecars when source file does not exist', async () => {
      const test$ = createMockEngine();
      const state: ReviewFindingsState = {
        prNumber: 300,
        findingsPath: '/work/nonexistent/findings.json',
        findings: [{ id: 'f1', file: 'a.py', line: 1, severity: 'minor', body: 'A', action: 'accept' }],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };

      const result = await syncCuratedStateToDisk(test$, state);
      assertStrictEqual(result.success, false);
      assert(result.error?.includes('Source findings file does not exist'));
    });
  });
});
