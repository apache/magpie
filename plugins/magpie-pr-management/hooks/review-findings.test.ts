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
  formatKeepAnswer,
  isAnchored,
  normalizeAction,
  normalizeFilePath,
  normalizeLine,
  normalizeSeverity,
  normalizeSource,
  parseFindings,
  register,
  serializeFindingsForRender,
} from './review-findings.ts';
import type { ReviewFinding } from './types.ts';

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

function assertDeepStrictEqual(actual: any, expected: any): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `Expected deep equality: ${JSON.stringify(expected)} !== ${JSON.stringify(actual)}`
    );
  }
}

describe('magpie-pr-management review findings mod (PR-1)', () => {
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
      const errors: string[] = [];
      assertStrictEqual(normalizeLine(12.5, errors), null);
      assertStrictEqual(normalizeLine(-3, errors), null);
      assertStrictEqual(normalizeLine(0, errors), null);
      assertStrictEqual(errors.length, 2);
      assert(errors[1].includes("Malformed line number '-3'"));

      const sevErrors: string[] = [];
      assertStrictEqual(normalizeSeverity(3, sevErrors), 'minor');
      assertStrictEqual(normalizeSeverity(undefined, sevErrors), 'minor');
      assertStrictEqual(sevErrors.length, 1);
      assert(sevErrors[0].includes("Invalid severity type 'number'"));
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
        file: './src/hook.py',
        line_number: '142',
        side: 'RIGHT',
        level: 'major',
        category: 'Code quality',
        rule_id: 'no in-function imports',
        quoted_rule: 'Flag any import inside a function body',
        excerpt: 'def f():\n    import boto3',
        explanation: 'The import runs on every call.',
        suggestion: 'Move the import to module level.',
        suggestion_block: '    import boto3',
        reviewers: ['codex', 'copilot'],
        comment: 'edited comment text',
        action: 'edit',
      };
      const decoded = JSON.parse(serializeFindingsForRender(parseFindings([step4]).findings))[0];
      assertStrictEqual(decoded.file, 'src/hook.py');
      assertStrictEqual(decoded.line, 142);
      assertStrictEqual(decoded.severity, 'major');
      for (const key of [
        'side',
        'category',
        'rule_id',
        'quoted_rule',
        'excerpt',
        'explanation',
        'suggestion',
        'suggestion_block',
        'comment',
      ]) {
        assertStrictEqual(decoded[key], (step4 as Record<string, unknown>)[key], `key ${key}`);
      }
      assertDeepStrictEqual(decoded.reviewers, ['codex', 'copilot']);
      for (const alias of ['line_number', 'level', 'action']) {
        assertStrictEqual(alias in decoded, false, `alias ${alias} dropped`);
      }
    });

    test('render numbering over the serialised file matches formatKeepAnswer', () => {
      // Inputs where the raw keys and render's rule diverge: aliases render
      // never reads, the string "0" (truthy in Python), a non-object item.
      const rawDataset: unknown[] = [
        { file: 'a.py', lineNumber: 12, body: 'alias lineNumber', action: 'accept' },
        { file: 'b.py', line: '0', body: 'string zero', action: 'accept' },
        'not an object',
        { file: 'c.py', line_number: 7, body: 'alias line_number', action: 'skip' },
        { file: 'd.py', line: 30, body: 'plain line', action: 'edit' },
        { file: 'e.py', line: null, body: 'unanchored', action: 'accept' },
      ];
      const parsed = parseFindings(rawDataset);
      const serialised = JSON.parse(serializeFindingsForRender(parsed.findings)) as Array<
        Record<string, unknown>
      >;
      // render: anchored = [f for f in findings if f.get("line")]
      const renderAnchored = serialised.filter((f) => Boolean(f.line));
      const actions = parsed.findings.filter(isAnchored).map((f) => f.action);
      assertStrictEqual(renderAnchored.length, actions.length);
      const renderKept = renderAnchored
        .map((_, i) => i + 1)
        .filter((i) => actions[i - 1] === 'accept' || actions[i - 1] === 'edit');
      assertStrictEqual(formatKeepAnswer(parsed.findings), renderKept.join(','));
      assertStrictEqual(formatKeepAnswer(parsed.findings), '1,3');
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

  describe('mod hook registration', () => {
    test('registers session.start lifecycle hook cleanly', async () => {
      const registered: Array<{ event: string; handler: Function }> = [];
      const fakeOn = (event: string, handler: Function) => {
        registered.push({ event, handler });
      };

      register(fakeOn);
      assertStrictEqual(registered.length, 1);
      assertStrictEqual(registered[0].event, 'session.start');

      let nextCalled = false;
      const fakeNext = (payload: any) => {
        nextCalled = true;
        return payload;
      };

      await registered[0].handler({}, { id: 'session-1' }, fakeNext);
      assert(nextCalled, 'Handler should chain to next(e)');
    });
  });
});
