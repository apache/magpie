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
  AttributionConfig,
  AttributionConvention,
  CommitCommandEvaluation,
  FsFileReader,
  ResolvedAttribution,
} from './types.js';

export const ATTRIBUTION_FILE = 'commit-attribution.toml';
export const OVERRIDES_DIR = '.apache-magpie-overrides';
export const LOCAL_DIR = '.apache-magpie-local';
export const DEFAULT_ATTRIBUTION: AttributionConvention = 'generated-by';
export const DEFAULT_AGENT = 'Claude Code';
export const DEFAULT_COAUTHOR_EMAIL = 'noreply@anthropic.com';

const VALID_CONVENTIONS: ReadonlySet<string> = new Set([
  'generated-by',
  'assisted-by',
  'co-authored-by',
  'none',
  'custom',
  'contributor-choice',
]);

/**
 * Normalizes and joins file path segments safely without relying on node:path.
 * Supports POSIX paths and Windows drive letters.
 */
export function joinPath(...segments: string[]): string {
  const nonEmpties = segments.filter((s) => s && s.trim().length > 0);
  if (nonEmpties.length === 0) return '.';

  const first = nonEmpties[0] || '';
  const isAbsolute =
    first.startsWith('/') || first.startsWith('\\') || /^[A-Za-z]:[/\\]/.test(first);

  const parts: string[] = [];

  for (const seg of nonEmpties) {
    const split = seg.split(/[/\\]+/);
    for (const p of split) {
      if (p === '..') {
        if (parts.length > 0 && parts[parts.length - 1] !== '..') {
          parts.pop();
        } else if (!isAbsolute) {
          parts.push('..');
        }
      } else if (p !== '.' && p !== '') {
        parts.push(p);
      }
    }
  }

  const result = parts.join('/');
  if (first.startsWith('/') || first.startsWith('\\')) {
    return '/' + result;
  }
  return result || '.';
}

/**
 * Strips ANSI escape sequences, Unicode BiDi overrides, control characters,
 * shell metacharacters, and line terminators to guarantee safe single-line Git trailer output.
 */
export function sanitizeTrailer(text: unknown): string {
  if (typeof text !== 'string') return '';
  return text
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069\u200E\u200F\u061C\u2028\u2029]/g, '')
    .replace(/[\u200B-\u200D\uFEFF\u2060\u00AD\uFE00-\uFE0F]/g, '')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .replace(/[`$\\"]/g, '')
    .trim();
}

/**
 * Strips comments from a TOML line respecting single and double quote boundaries.
 */
function stripTomlComment(line: string): string {
  let inDouble = false;
  let inSingle = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
    } else if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
    } else if (ch === '#' && !inDouble && !inSingle) {
      return line.slice(0, i);
    }
  }
  return line;
}

/**
 * Parses a simple subset of TOML used for commit-attribution.toml files.
 * Zero-dependency, fails safe on malformed lines.
 */
export function parseAttributionToml(content: unknown): AttributionConfig | null {
  if (typeof content !== 'string' || !content.trim()) return null;

  let conventionValue: string | undefined;
  let templateValue: string | undefined;

  const lines = content.split('\n');
  for (const rawLine of lines) {
    const cleanLine = stripTomlComment(rawLine);
    const trimmed = cleanLine.trim();
    if (!trimmed) continue;

    const eqIdx = trimmed.indexOf('=');
    if (eqIdx <= 0) continue;

    const key = trimmed.slice(0, eqIdx).trim().toLowerCase();
    const rawVal = trimmed.slice(eqIdx + 1).trim();

    // Parse quoted or unquoted string value
    let val = rawVal;
    if (
      (rawVal.startsWith('"') && rawVal.endsWith('"')) ||
      (rawVal.startsWith("'") && rawVal.endsWith("'"))
    ) {
      val = rawVal.slice(1, -1);
    }

    if (key === 'convention') {
      const normalized = val.trim().toLowerCase();
      if (VALID_CONVENTIONS.has(normalized)) {
        conventionValue = normalized;
      }
    } else if (key === 'template') {
      templateValue = val.trim();
    }
  }

  if (!conventionValue) {
    return null;
  }

  return {
    convention: conventionValue as AttributionConfig['convention'],
    template: templateValue,
  };
}

/**
 * Applies template replacements for {agent}, {email}, and {model}.
 */
function applyTemplate(
  template: string,
  agent: string,
  email: string,
  model?: string
): string {
  let result = template.replace(/\{agent\}/g, agent).replace(/\{email\}/g, email);
  if (model && model.trim()) {
    result = result.replace(/\{model\}/g, model.trim());
  } else {
    // If model is unsupplied, cleanly strip ({model}) or : {model} or {model}
    result = result
      .replace(/\s*\(\{model\}\)/g, '')
      .replace(/:\s*\{model\}/g, '')
      .replace(/\{model\}/g, '')
      .trim();
  }
  return result;
}

/**
 * Formats a single Git trailer line and components from an AttributionConfig.
 */
export function formatAttribution(
  config: AttributionConfig,
  agent: string = DEFAULT_AGENT,
  email: string = DEFAULT_COAUTHOR_EMAIL,
  model?: string
): ResolvedAttribution {
  const convention: AttributionConvention =
    config.convention === 'contributor-choice' ? DEFAULT_ATTRIBUTION : config.convention;

  if (convention === 'none') {
    return {
      convention: 'none',
      trailerText: null,
      trailerKey: null,
      trailerValue: null,
    };
  }

  if (convention === 'assisted-by') {
    const raw = config.template
      ? applyTemplate(config.template, agent, email, model)
      : model && model.trim()
        ? `Assisted-by: ${agent}:${model.trim()}`
        : `Assisted-by: ${agent}`;
    const sanitized = sanitizeTrailer(raw);
    const colonIdx = sanitized.indexOf(':');
    return {
      convention: 'assisted-by',
      trailerText: sanitized,
      trailerKey: colonIdx > 0 ? sanitized.slice(0, colonIdx).trim() : 'Assisted-by',
      trailerValue: colonIdx > 0 ? sanitized.slice(colonIdx + 1).trim() : agent,
    };
  }

  if (convention === 'co-authored-by') {
    const raw = config.template
      ? applyTemplate(config.template, agent, email, model)
      : `Co-authored-by: ${agent} <${email}>`;
    const sanitized = sanitizeTrailer(raw);
    const colonIdx = sanitized.indexOf(':');
    return {
      convention: 'co-authored-by',
      trailerText: sanitized,
      trailerKey: colonIdx > 0 ? sanitized.slice(0, colonIdx).trim() : 'Co-authored-by',
      trailerValue:
        colonIdx > 0 ? sanitized.slice(colonIdx + 1).trim() : `${agent} <${email}>`,
    };
  }

  if (convention === 'custom') {
    if (config.template) {
      const raw = applyTemplate(config.template, agent, email, model);
      const sanitized = sanitizeTrailer(raw);
      const colonIdx = sanitized.indexOf(':');
      if (colonIdx > 0) {
        const trailerKey = sanitized.slice(0, colonIdx).trim();
        // Validate trailer key conforms to Git/RFC token format
        if (/^[A-Za-z0-9-]+$/.test(trailerKey)) {
          return {
            convention: 'custom',
            trailerText: sanitized,
            trailerKey,
            trailerValue: sanitized.slice(colonIdx + 1).trim(),
          };
        }
      }
    }
    // Custom with missing or invalid template falls back to generated-by
    const fallbackText = `Generated-by: ${agent}`;
    return {
      convention: 'generated-by',
      trailerText: fallbackText,
      trailerKey: 'Generated-by',
      trailerValue: agent,
    };
  }

  // Default: generated-by
  const raw = config.template
    ? applyTemplate(config.template, agent, email, model)
    : `Generated-by: ${agent}`;
  const sanitized = sanitizeTrailer(raw);
  const colonIdx = sanitized.indexOf(':');
  return {
    convention: 'generated-by',
    trailerText: sanitized,
    trailerKey: colonIdx > 0 ? sanitized.slice(0, colonIdx).trim() : 'Generated-by',
    trailerValue: colonIdx > 0 ? sanitized.slice(colonIdx + 1).trim() : agent,
  };
}

/**
 * Resolves the active commit attribution policy following docs/setup/commit-attribution.md:
 * 1. Project layer (.apache-magpie-overrides/commit-attribution.toml) wins unless contributor-choice.
 * 2. Fail closed: If project layer is present but corrupted or invalid, strictly resolves to generated-by.
 * 3. Personal layer (.apache-magpie-local/ or .git/apache-magpie/) applies when project allows choice or is absent.
 * 4. Default fallback is generated-by.
 */
export function resolveAttribution(
  projectToml?: string | null,
  personalToml?: string | null,
  agent: string = DEFAULT_AGENT,
  email: string = DEFAULT_COAUTHOR_EMAIL,
  model?: string
): ResolvedAttribution {
  // 1. Project layer evaluation
  if (typeof projectToml === 'string' && projectToml.trim()) {
    const projectConfig = parseAttributionToml(projectToml);
    if (!projectConfig) {
      // Fail closed: a project file that cannot be parsed resolves to generated-by
      return formatAttribution({ convention: DEFAULT_ATTRIBUTION }, agent, email, model);
    }
    if (projectConfig.convention !== 'contributor-choice') {
      return formatAttribution(projectConfig, agent, email, model);
    }
    // contributor-choice falls through to personal layer below
  }

  // 2. Personal layer evaluation
  if (typeof personalToml === 'string' && personalToml.trim()) {
    const personalConfig = parseAttributionToml(personalToml);
    if (personalConfig && personalConfig.convention !== 'contributor-choice') {
      return formatAttribution(personalConfig, agent, email, model);
    }
  }

  // 3. Default fallback
  return formatAttribution({ convention: DEFAULT_ATTRIBUTION }, agent, email, model);
}

/**
 * Splits a compound bash command string into pipeline segments by &&, ||, ;, \n, and |.
 */
function splitCommandSegments(command: string): string[] {
  const segments: string[] = [];
  let current = '';
  let inDouble = false;
  let inSingle = false;

  for (let i = 0; i < command.length; i++) {
    const ch = command[i];
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
      current += ch;
    } else if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
      current += ch;
    } else if (!inDouble && !inSingle) {
      if (
        (ch === '&' && command[i + 1] === '&') ||
        (ch === '|' && command[i + 1] === '|')
      ) {
        segments.push(current);
        current = '';
        i++; // skip next char
      } else if (ch === ';' || ch === '\n' || ch === '|') {
        segments.push(current);
        current = '';
      } else {
        current += ch;
      }
    } else {
      current += ch;
    }
  }
  if (current.trim()) {
    segments.push(current);
  }
  return segments;
}

/**
 * Inspects a Bash tool command for git commit invocations carrying forbidden Co-Authored-By trailers.
 * Replicates agent-guard commit-trailer policy without mutating command pipelines.
 */
export function evaluateCommitCommand(
  command: string,
  resolved: ResolvedAttribution
): CommitCommandEvaluation {
  if (typeof command !== 'string' || !command.trim()) {
    return { blocked: false };
  }

  // Check documented overrides: MAGPIE_ALLOW_COAUTHOR=1 or MAGPIE_GUARD_OFF=1
  if (
    /(?:^|\s)MAGPIE_ALLOW_COAUTHOR=1\b/.test(command) ||
    /(?:^|\s)MAGPIE_GUARD_OFF=1\b/.test(command)
  ) {
    return { blocked: false };
  }

  // Check if Co-Authored-By is permitted by the resolved convention
  const isCoAuthorPermitted =
    resolved.convention === 'co-authored-by' ||
    resolved.trailerKey?.toLowerCase() === 'co-authored-by';

  if (isCoAuthorPermitted) {
    return { blocked: false };
  }

  // Segment command to isolate individual statements
  const segments = splitCommandSegments(command);

  for (const seg of segments) {
    const trimmed = seg.trim();
    if (!trimmed) continue;

    // Check if this segment executes git commit (ReDoS-safe regex: no nested overlapping quantifiers)
    const hasGitCommit = /(?:^|\s)git(?:\s+[^\s;|&]+)*\s+commit(?:\s|$)/i.test(trimmed);
    if (!hasGitCommit) continue;

    // Verify it is not a sub-command like commit-tree or commit-graph
    if (/(?:^|\s)git(?:\s+[^\s;|&]+)*\s+commit-(?:tree|graph)\b/i.test(trimmed)) {
      continue;
    }

    // Check if this specific commit segment carries a Co-Authored-By trailer
    const hasCoAuthor = /\bco-authored-by:\s*/i.test(trimmed);
    if (hasCoAuthor) {
      if (resolved.convention === 'none') {
        return {
          blocked: true,
          reason:
            `agent-guard[commit-trailer]: this commit command carries a 'Co-Authored-By:' trailer, ` +
            `but this repository's commit-attribution convention is 'none' (do not include attribution trailers). ` +
            `Override (not for AI co-authorship): MAGPIE_ALLOW_COAUTHOR=1.`,
        };
      }

      return {
        blocked: true,
        reason:
          `agent-guard[commit-trailer]: this commit command carries a 'Co-Authored-By:' trailer, ` +
          `but this repository's commit-attribution convention is '${resolved.convention}'. ` +
          `Agents are assistants, not authors: use '${resolved.trailerText || 'Generated-by: Claude Code'}' instead ` +
          `(see docs/setup/commit-attribution.md). Override (not for AI co-authorship): MAGPIE_ALLOW_COAUTHOR=1.`,
      };
    }
  }

  return { blocked: false };
}

/**
 * Event hook registration entry point for Claude Code.
 */
export function register(on: any): void {
  // Helper to read personal layer across adopted and unadopted repos
  const resolvePersonalToml = async (
    read: FsFileReader,
    workspaceDir: string
  ): Promise<string | null> => {
    // 1. Adopted repo: <workspace>/.apache-magpie-local/commit-attribution.toml
    const adoptedPath = joinPath(workspaceDir, LOCAL_DIR, ATTRIBUTION_FILE);
    const content = await read(adoptedPath);
    if (content) return content;

    // 2. Unadopted repo: <workspace>/.git/apache-magpie/commit-attribution.toml
    const unadoptedGitPath = joinPath(workspaceDir, '.git', 'apache-magpie', ATTRIBUTION_FILE);
    return await read(unadoptedGitPath);
  };

  // 1. Hook attribution.text to supply compliant attribution string directly to Claude Code
  on('attribution.text', async ($: any) => {
    try {
      const workspaceDir = await $.session.root();
      const read: FsFileReader = async (filePath: string): Promise<string | null> => {
        try {
          return await $.fs.read(filePath);
        } catch {
          return null;
        }
      };

      const projectPath = joinPath(workspaceDir, OVERRIDES_DIR, ATTRIBUTION_FILE);
      const projectToml = await read(projectPath);
      const personalToml = await resolvePersonalToml(read, workspaceDir);

      const resolved = resolveAttribution(projectToml, personalToml);
      return { text: resolved.trailerText ?? '' };
    } catch {
      // Fail-safe to ASF standard
      return { text: `Generated-by: ${DEFAULT_AGENT}` };
    }
  });

  // 2. Hook tool.call on Bash to warn before agent-guard blocks unauthorized co-authorship
  on('tool.call', { tool: 'Bash' }, async ($: any, e: any, next: any) => {
    const command = e?.command;

    if (typeof command === 'string') {
      try {
        const workspaceDir = await $.session.root();
        const read: FsFileReader = async (filePath: string): Promise<string | null> => {
          try {
            return await $.fs.read(filePath);
          } catch {
            return null;
          }
        };

        const projectPath = joinPath(workspaceDir, OVERRIDES_DIR, ATTRIBUTION_FILE);
        const projectToml = await read(projectPath);
        const personalToml = await resolvePersonalToml(read, workspaceDir);

        const resolved = resolveAttribution(projectToml, personalToml);
        const evaluation = evaluateCommitCommand(command, resolved);

        if (evaluation.blocked) {
          return {
            decision: 'deny',
            reason: evaluation.reason,
          };
        }
      } catch {
        // Fail-open: never block execution on hook error
      }
    }

    if (typeof next === 'function') {
      return next(e);
    }
  });
}

export default register;
