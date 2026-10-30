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

import { CANONICAL_FORBIDDEN_TERMS, type CanonicalForbiddenTerm } from './forbidden-terms.ts';

/**
 * Single canonical forbidden-term regexes for public surfaces, derived directly
 * from DEFAULT_TERMS in tools/vcs/src/magpie_vcs/publication.py.
 */
export const FORBIDDEN_TERM_RULES: ReadonlyArray<{ name: string; pattern: RegExp }> =
  CANONICAL_FORBIDDEN_TERMS.map((term: CanonicalForbiddenTerm) => ({
    name: term.name,
    pattern: new RegExp(term.pattern, term.flags),
  }));

/**
 * Finds all unique forbidden embargo terms that appear in the candidate text.
 */
export function findForbiddenTerms(text: string): string[] {
  if (!text || typeof text !== 'string') {
    return [];
  }

  const matched: string[] = [];
  for (const rule of FORBIDDEN_TERM_RULES) {
    if (rule.pattern.test(text)) {
      matched.push(rule.name);
    }
  }

  return matched;
}

export type FileReader = (filePath: string) => Promise<string | null | undefined>;

export interface ProjectRepos {
  trackerRepo?: string;
  upstreamRepo?: string;
  upstreamClonePath?: string;
  isTrackerCheckout?: boolean;
}

/**
 * Cleans and validates a repository slug (owner/repo).
 * Filters out placeholders, TODOs, comments, and non-slug text like "not used".
 */
export function cleanRepoSlug(raw: string | undefined): string | undefined {
  if (!raw || typeof raw !== 'string') {
    return undefined;
  }
  const trimmed = raw.trim().replace(/^[`'"]+|[`'"]+$/g, '').trim().toLowerCase();
  if (
    trimmed.startsWith('todo') ||
    trimmed.startsWith('<') ||
    trimmed.startsWith('not used') ||
    trimmed.startsWith('not_used') ||
    trimmed === 'none' ||
    trimmed === 'n/a' ||
    trimmed === '-' ||
    !trimmed.includes('/')
  ) {
    return undefined;
  }
  const match = trimmed.match(/^([a-z0-9_.-]+\/[a-z0-9_.-]+)/);
  return match ? match[1] : undefined;
}

/**
 * Parses project manifest or user config content (Markdown table or YAML syntax)
 * to extract tracker_repo, upstream_repo, and environment.upstream_clone.
 */
export function parseProjectManifest(content: string): ProjectRepos {
  const result: ProjectRepos = {};
  if (!content || typeof content !== 'string') {
    return result;
  }

  // Markdown table row: | `?tracker_repo`? | `?<slug>`? |
  const trackerMatch =
    content.match(/\|\s*`?tracker_repo`?\s*\|\s*`?([^`|\r\n]+)`?/i) ??
    content.match(/^\s*tracker_repo:\s*`?([^`\r\n#]+)`?/im);
  const trackerSlug = cleanRepoSlug(trackerMatch?.[1]);
  if (trackerSlug) {
    result.trackerRepo = trackerSlug;
  }

  // Markdown table row: | `?upstream_repo`? | `?<slug>`? |
  const upstreamMatch =
    content.match(/\|\s*`?upstream_repo`?\s*\|\s*`?([^`|\r\n]+)`?/i) ??
    content.match(/^\s*upstream_repo:\s*`?([^`\r\n#]+)`?/im);
  const upstreamSlug = cleanRepoSlug(upstreamMatch?.[1]);
  if (upstreamSlug) {
    result.upstreamRepo = upstreamSlug;
  }

  // user.md declares environment.upstream_clone or upstream_clone as a filesystem path
  const upstreamCloneMatch =
    content.match(/\|\s*`?(?:environment\.)?upstream_clone`?\s*\|\s*`?([^`|\r\n]+)`?/i) ??
    content.match(/^\s*(?:environment\.)?upstream_clone:\s*`?([^`\r\n#]+)`?/im) ??
    content.match(/^\s*upstream_clone:\s*`?([^`\r\n#]+)`?/im);
  if (upstreamCloneMatch?.[1]) {
    const rawPath = upstreamCloneMatch[1].trim().replace(/^[`'"]+|[`'"]+$/g, '').trim();
    if (rawPath && !rawPath.startsWith('TODO') && !rawPath.startsWith('<')) {
      result.upstreamClonePath = rawPath;
    }
  }

  return result;
}

/**
 * Resolves repository identity from <project-config>/project.md and user.md in precedence order:
 * 1. .apache-magpie-local/project.md
 * 2. .git/apache-magpie/project.md (and worktree common dir)
 * 3. .apache-magpie-overrides/project.md
 * 4. ../.apache-magpie-overrides/project.md (if in sibling directory)
 * 5. user.md layers (including ~/.config/apache-magpie/user.md with $HOME expanded)
 */
export async function resolveProjectConfig(
  readFile?: FileReader,
  cwd?: string,
  env?: { [key: string]: string | undefined }
): Promise<ProjectRepos> {
  if (!readFile) {
    return {};
  }

  const prefix = cwd ? `${cwd.replace(/[\\/]+$/, '')}/` : '';
  const procEnv = typeof process !== 'undefined' ? process.env : undefined;
  const homeDir = (env?.HOME || procEnv?.HOME || procEnv?.USERPROFILE || '').replace(/[\\/]+$/, '');

  const candidatePaths = [
    `${prefix}.apache-magpie-local/project.md`,
    `${prefix}.git/apache-magpie/project.md`,
    `${prefix}.apache-magpie-overrides/project.md`,
    '.apache-magpie-local/project.md',
    '.git/apache-magpie/project.md',
    '.apache-magpie-overrides/project.md',
    '../.apache-magpie-local/project.md',
    '../.apache-magpie-overrides/project.md',
    `${prefix}.apache-magpie-local/user.md`,
    `${prefix}.apache-magpie-overrides/user.md`,
    '.apache-magpie-local/user.md',
    '.apache-magpie-overrides/user.md',
  ];

  if (homeDir) {
    candidatePaths.push(`${homeDir}/.config/apache-magpie/user.md`);
  }
  candidatePaths.push('~/.config/apache-magpie/user.md');

  // Check git worktree gitdir pointer
  try {
    const gitFilePath = `${prefix}.git`;
    const gitFileContent = await readFile(gitFilePath);
    if (gitFileContent && typeof gitFileContent === 'string') {
      const gitDirMatch = gitFileContent.match(/gitdir:\s*([^\r\n]+)/i);
      if (gitDirMatch) {
        const resolvedGitDir = resolvePath(cwd, gitDirMatch[1].trim());
        // In a worktree, gitdir is <commondir>/worktrees/<name>; the common dir is two levels up
        const commonDir = resolvedGitDir.replace(/[\\/]worktrees[\\/][^\\/]+$/, '');
        candidatePaths.unshift(`${commonDir}/apache-magpie/project.md`);
      }
    }
  } catch {
    // Continue
  }

  let merged: ProjectRepos = {};

  for (const path of candidatePaths) {
    try {
      const content = await readFile(path);
      if (content && typeof content === 'string') {
        const repos = parseProjectManifest(content);
        if (repos.trackerRepo && !merged.trackerRepo) {
          merged.trackerRepo = repos.trackerRepo;
          merged.isTrackerCheckout = !path.startsWith('..') && !path.includes('/..');
        }
        if (repos.upstreamRepo && !merged.upstreamRepo) {
          merged.upstreamRepo = repos.upstreamRepo;
        }
        if (repos.upstreamClonePath && !merged.upstreamClonePath) {
          // Expand ~ in upstreamClonePath if needed
          let clonePath = repos.upstreamClonePath;
          if (clonePath.startsWith('~/') && homeDir) {
            clonePath = `${homeDir}/${clonePath.slice(2)}`;
          }
          merged.upstreamClonePath = clonePath;
        }
        if (merged.trackerRepo && merged.upstreamRepo && merged.upstreamClonePath) {
          return merged;
        }
      }
    } catch {
      // Continue to next candidate
    }
  }

  return merged;
}

export interface ShellSubcommand {
  raw: string;
  separatorAfter?: string;
  subshellDepthDeltaBefore?: number;
  subshellDepthDeltaAfter?: number;
  hasUnclosedQuoteWithBinary?: boolean;
  // Inside a group that is piped or backgrounded (`{ cd x; true; } | cat`): it runs in a subshell.
  inPipedOrBackgroundGroup?: boolean;
}

/**
 * Helper to check if a string is completely enclosed in a matching pair of
 * outer parentheses (...) or braces {...}.
 */
function isEnclosedInMatchingGroup(str: string): boolean {
  const trimmed = str.trim();
  if (
    (!trimmed.startsWith('(') || !trimmed.endsWith(')')) &&
    (!trimmed.startsWith('{') || !trimmed.endsWith('}'))
  ) {
    return false;
  }
  const openChar = trimmed[0];
  const closeChar = openChar === '(' ? ')' : '}';
  let depth = 0;
  let inS = false;
  let inD = false;
  let isEsc = false;

  for (let i = 0; i < trimmed.length; i++) {
    const ch = trimmed[i];
    if (isEsc) {
      isEsc = false;
      continue;
    }
    if (ch === '\\' && !inS) {
      isEsc = true;
      continue;
    }
    if (ch === "'" && !inD) {
      inS = !inS;
      continue;
    }
    if (ch === '"' && !inS) {
      inD = !inD;
      continue;
    }
    if (!inS && !inD) {
      if (ch === openChar) {
        depth++;
      } else if (ch === closeChar) {
        depth--;
        if (depth === 0 && i < trimmed.length - 1) {
          return false;
        }
      }
    }
  }
  return depth === 0;
}

/**
 * Checks if a string has unbalanced parentheses or braces.
 */
function hasUnbalancedGroupDelimiters(str: string): boolean {
  let p = 0;
  let b = 0;
  let inS = false;
  let inD = false;
  let isEsc = false;

  for (let i = 0; i < str.length; i++) {
    const ch = str[i];
    if (isEsc) {
      isEsc = false;
      continue;
    }
    if (ch === '\\' && !inS) {
      isEsc = true;
      continue;
    }
    if (ch === "'" && !inD) {
      inS = !inS;
      continue;
    }
    if (ch === '"' && !inS) {
      inD = !inD;
      continue;
    }
    if (!inS && !inD) {
      if (ch === '(') p++;
      else if (ch === ')') {
        p--;
        if (p < 0) return true;
      } else if (ch === '{') b++;
      else if (ch === '}') {
        b--;
        if (b < 0) return true;
      }
    }
  }
  return p !== 0 || b !== 0;
}

/**
 * Splits a composite shell command line into individual subcommands along with
 * the trailing separator (&&, ;, \n, |, ||, &), respecting quoting rules and
 * subshell grouping parentheses and braces.
 */
export function splitShellSubcommands(commandLine: string): ShellSubcommand[] {
  const result: ShellSubcommand[] = [];
  if (!commandLine || typeof commandLine !== 'string') {
    return result;
  }

  let current = '';
  let inSingle = false;
  let inDouble = false;
  let isEscaped = false;
  let parenDepth = 0;
  let braceDepth = 0;
  const pendingHeredocs: { delim: string; stripTabs: boolean }[] = [];

  const pushCurrent = (sep?: string) => {
    const trimmed = current.trim();
    if (trimmed) {
      if (isEnclosedInMatchingGroup(trimmed)) {
        const isSubshell = trimmed.startsWith('(') && trimmed.endsWith(')');
        // Strip outer group delimiters and recursively split subcommands inside the group
        const inner = trimmed.slice(1, -1).trim();
        const innerSubs = splitShellSubcommands(inner);
        if (innerSubs.length > 0) {
          if (isSubshell) {
            innerSubs[0].subshellDepthDeltaBefore = (innerSubs[0].subshellDepthDeltaBefore || 0) + 1;
            innerSubs[innerSubs.length - 1].subshellDepthDeltaAfter =
              (innerSubs[innerSubs.length - 1].subshellDepthDeltaAfter || 0) + 1;
          }
          innerSubs[innerSubs.length - 1].separatorAfter = sep;
          if (sep === '|' || sep === '&') {
            for (const sub of innerSubs) sub.inPipedOrBackgroundGroup = true;
          }
          result.push(...innerSubs);
        }
      } else {
        result.push({ raw: trimmed, separatorAfter: sep });
      }
    }
    current = '';
  };

  for (let i = 0; i < commandLine.length; i++) {
    const char = commandLine[i];
    const next = commandLine[i + 1];

    if (isEscaped) {
      current += char;
      isEscaped = false;
      continue;
    }

    if (char === '\\' && !inSingle) {
      isEscaped = true;
      current += char;
      continue;
    }

    if (char === "'" && !inDouble) {
      inSingle = !inSingle;
      current += char;
      continue;
    }

    if (char === '"' && !inSingle) {
      inDouble = !inDouble;
      current += char;
      continue;
    }

    if (!inSingle && !inDouble) {
      // Check for heredoc operator << or <<- (excluding <<< herestring)
      if (char === '<' && next === '<' && commandLine[i + 2] !== '<') {
        let pos = i + 2;
        let stripTabs = false;
        if (commandLine[pos] === '-') {
          stripTabs = true;
          pos++;
        }
        while (pos < commandLine.length && (commandLine[pos] === ' ' || commandLine[pos] === '\t')) {
          pos++;
        }
        let delim = '';
        if (pos < commandLine.length) {
          const q = commandLine[pos];
          if (q === "'" || q === '"') {
            pos++;
            while (pos < commandLine.length && commandLine[pos] !== q) {
              delim += commandLine[pos];
              pos++;
            }
            if (pos < commandLine.length && commandLine[pos] === q) {
              pos++;
            }
          } else {
            while (
              pos < commandLine.length &&
              !/[\s;&|()<>]/.test(commandLine[pos])
            ) {
              delim += commandLine[pos];
              pos++;
            }
          }
        }
        if (delim) {
          if (delim.startsWith('\\')) {
            delim = delim.slice(1);
          }
          pendingHeredocs.push({ delim, stripTabs });
        }
        current += commandLine.slice(i, pos);
        i = pos - 1;
        continue;
      }

      if (char === '(') {
        parenDepth++;
        current += char;
        continue;
      }
      if (char === ')') {
        if (parenDepth > 0) parenDepth--;
        current += char;
        continue;
      }
      if (char === '{') {
        braceDepth++;
        current += char;
        continue;
      }
      if (char === '}') {
        if (braceDepth > 0) braceDepth--;
        current += char;
        continue;
      }

      // Only split on operators when NOT inside parentheses or braces
      if (parenDepth === 0 && braceDepth === 0) {
        if (char === '\n' || char === '\r') {
          // If there is a pending heredoc, consume its body line by line
          if (pendingHeredocs.length > 0) {
            current += char;
            if (char === '\r' && next === '\n') {
              current += next;
              i++;
            }
            while (pendingHeredocs.length > 0 && i + 1 < commandLine.length) {
              const target = pendingHeredocs[0];
              const lineStart = i + 1;
              let lineEnd = commandLine.indexOf('\n', lineStart);
              let hasCr = false;
              if (lineEnd === -1) {
                lineEnd = commandLine.length;
              } else if (lineEnd > lineStart && commandLine[lineEnd - 1] === '\r') {
                hasCr = true;
              }
              const rawLine = commandLine.slice(lineStart, hasCr ? lineEnd - 1 : lineEnd);
              const checkLine = target.stripTabs ? rawLine.replace(/^\t+/, '') : rawLine.trim();

              current += commandLine.slice(lineStart, lineEnd === commandLine.length ? lineEnd : lineEnd + 1);
              i = lineEnd === commandLine.length ? lineEnd - 1 : lineEnd;

              if (checkLine === target.delim) {
                pendingHeredocs.shift();
              }
            }
            pushCurrent('\n');
            continue;
          }

          pushCurrent('\n');
          continue;
        }
        if (char === ';') {
          pushCurrent(';');
          continue;
        }
        if (char === '&') {
          if (next === '&') {
            pushCurrent('&&');
            i++; // skip second &
            continue;
          }
          // Single & is background separator unless part of >& redirection
          const prev = i > 0 ? commandLine[i - 1] : '';
          if (prev !== '>') {
            pushCurrent('&');
            continue;
          }
        }
        if (char === '|' && next === '|') {
          pushCurrent('||');
          i++; // skip second |
          continue;
        }
        if (char === '|') {
          pushCurrent('|');
          continue;
        }
      }
    }

    current += char;
  }

  pushCurrent(undefined);

  // Fail closed if a quote is still open at the end and commandLine contains git or gh
  if ((inSingle || inDouble) && /\b(?:git|gh)\b/i.test(commandLine)) {
    if (result.length > 0) {
      result[result.length - 1].hasUnclosedQuoteWithBinary = true;
    } else {
      result.push({ raw: commandLine, hasUnclosedQuoteWithBinary: true });
    }
  }

  return result;
}

/**
 * Splits a composite shell command line into individual subcommand strings.
 */
export function splitShellCommands(commandLine: string): string[] {
  return splitShellSubcommands(commandLine).map((s) => s.raw);
}

/**
 * Tokenizes a single subcommand line into an argv array according to POSIX shell
 * quoting and escaping rules.
 */
export function tokenizeShellWords(subcommand: string): string[] {
  const tokens: string[] = [];
  if (!subcommand || typeof subcommand !== 'string') {
    return tokens;
  }

  let current = '';
  let inSingle = false;
  let inDouble = false;
  let isEscaped = false;
  let hasToken = false;

  for (let i = 0; i < subcommand.length; i++) {
    const char = subcommand[i];

    if (isEscaped) {
      current += char;
      hasToken = true;
      isEscaped = false;
      continue;
    }

    if (char === '\\' && !inSingle) {
      if (inDouble) {
        const next = subcommand[i + 1];
        if (next === '"' || next === '\\' || next === '$' || next === '`' || next === '\n') {
          isEscaped = true;
          continue;
        }
        current += char;
        hasToken = true;
      } else {
        isEscaped = true;
      }
      continue;
    }

    if (char === "'" && !inDouble) {
      inSingle = !inSingle;
      hasToken = true;
      continue;
    }

    if (char === '"' && !inSingle) {
      inDouble = !inDouble;
      hasToken = true;
      continue;
    }

    if (/\s/.test(char) && !inSingle && !inDouble) {
      if (hasToken || current.length > 0) {
        tokens.push(current);
        current = '';
        hasToken = false;
      }
      continue;
    }

    current += char;
    hasToken = true;
  }

  if (hasToken || current.length > 0) {
    tokens.push(current);
  }

  return tokens;
}

/**
 * Normalizes path segments (collapsing . and ..) without requiring node:path.
 */
export function normalizePathSegments(p: string): string {
  if (!p) return '';
  const isAbsSlash = p.startsWith('/') || p.startsWith('\\');
  const driveMatch = p.match(/^([a-zA-Z]:)[\\/]/);
  const prefix = driveMatch ? `${driveMatch[1]}/` : isAbsSlash ? '/' : '';
  const rest = driveMatch ? p.slice(driveMatch[0].length) : isAbsSlash ? p.slice(1) : p;

  const parts = rest.split(/[\\/]+/);
  const stack: string[] = [];
  for (const part of parts) {
    if (!part || part === '.') continue;
    if (part === '..') {
      if (stack.length > 0 && stack[stack.length - 1] !== '..') {
        stack.pop();
      } else if (!prefix) {
        stack.push('..');
      }
    } else {
      stack.push(part);
    }
  }
  return prefix + stack.join('/');
}

/**
 * Resolves a file path relative to an optional directory without requiring node:path.
 */
export function resolvePath(dir: string | undefined, filePath: string): string {
  if (!filePath) return '';
  const trimmed = filePath.trim().replace(/^['"]|['"]$/g, '');
  if (!dir || trimmed.startsWith('/') || trimmed.startsWith('\\') || /^[a-zA-Z]:/.test(trimmed)) {
    return normalizePathSegments(trimmed);
  }
  const cleanDir = dir.trim().replace(/[\\/]+$/, '');
  const cleanPath = trimmed.replace(/^\.[\\/]+/, '').replace(/^[\\/]+/, '');
  return normalizePathSegments(`${cleanDir}/${cleanPath}`);
}

export interface ParsedSubcommand {
  raw: string;
  isPublicSurfaceCommand: boolean;
  commandType: string;
  targetRepo?: string;
  gitCwd?: string;
  cdDir?: string;
  extractedTexts: string[];
  referencedFiles: string[];
  redirectedFiles: string[];
  hasDynamicInput: boolean;
  isGraphqlMutation?: boolean;
  isLiteralUnknownEndpoint?: boolean;
  hasGitDirOrWorkTree?: boolean;
  /** The command runs with environment set for it: a leading `NAME=value` or an `env` wrapper, after any prefix. */
  setsOwnEnvironment?: boolean;
}

/**
 * Detects dynamic shell constructs that cannot be statically inspected:
 * command substitution ($(...) or `...`), parameter expansion ($VAR or ${VAR}),
 * process substitution (<(...)), and heredocs (<<).
 * Correctly ignores literal $VAR inside single quotes (e.g. -m 'costs $HOME').
 */
export function hasDynamicShellConstructs(subcommand: string): boolean {
  let inSingle = false;
  let inDouble = false;
  let isEscaped = false;

  for (let i = 0; i < subcommand.length; i++) {
    const char = subcommand[i];
    if (isEscaped) {
      isEscaped = false;
      continue;
    }
    if (char === '\\' && !inSingle) {
      isEscaped = true;
      continue;
    }
    if (char === "'" && !inDouble) {
      inSingle = !inSingle;
      continue;
    }
    if (char === '"' && !inSingle) {
      inDouble = !inDouble;
      continue;
    }
    if (!inSingle) {
      if (char === '`') return true;
      if (char === '$' && i + 1 < subcommand.length) {
        const next = subcommand[i + 1];
        if (next === '(' || next === '{' || /[a-zA-Z_]/.test(next)) {
          return true;
        }
      }
      if (!inDouble) {
        if (char === '<' && i + 1 < subcommand.length) {
          const next = subcommand[i + 1];
          if (next === '<' || next === '(') {
            return true;
          }
        }
      }
    }
  }
  return false;
}

/**
 * Extracts a target repository slug from positional PR or issue URLs:
 * https://github.com/<owner>/<repo>/pull/<id> or /issues/<id>
 * Ignores URLs that appear inside flag values or body arguments.
 */
function extractPositionalUrlRepo(tokens: string[], startIndex: number): string | undefined {
  const urlRegex = /^https?:\/\/github\.com\/([a-z0-9_.-]+\/[a-z0-9_.-]+)\/(?:pull|issues)\/\d+$/i;
  for (let i = startIndex; i < tokens.length; i++) {
    const token = tokens[i];
    // Skip flags that take an argument
    if (
      (token === '-b' ||
        token === '--body' ||
        token === '-t' ||
        token === '--title' ||
        token === '-F' ||
        token === '--body-file' ||
        token === '-R' ||
        token === '--repo' ||
        token === '-c' ||
        token === '--comment' ||
        token === '-a' ||
        token === '--assignee' ||
        token === '-B' ||
        token === '--base' ||
        token === '-H' ||
        token === '--head' ||
        token === '-l' ||
        token === '--label' ||
        token === '-m' ||
        token === '--milestone' ||
        token === '-p' ||
        token === '--project' ||
        token === '-r' ||
        token === '--reviewer') &&
      i + 1 < tokens.length
    ) {
      i++; // Skip the flag argument
      continue;
    }
    if (token.startsWith('-')) {
      continue;
    }
    const match = token.match(urlRegex);
    if (match) {
      return match[1].toLowerCase();
    }
  }
  return undefined;
}

/**
 * Checks if tokens array contains an explicit message or file flag.
 * Handles -m, -F, --message, --file, and clustered short flags like -am, -sam.
 */
export function hasMessageOrFileFlag(tokens: string[]): boolean {
  return tokens.some((t) =>
    t === '-m' ||
    t === '-F' ||
    t.startsWith('--message') ||
    t.startsWith('--file') ||
    (t.startsWith('-') && !t.startsWith('--') && (t.includes('m') || t.includes('F')))
  );
}

/**
 * Parses message and file options (-m, -F, --message, --file, clustered -am)
 * for git commit, git tag, git merge.
 * Returns the updated index i.
 */
export function parseMessageAndFileFlags(
  tokens: string[],
  i: number,
  result: ParsedSubcommand
): number {
  const token = tokens[i];

  // -F <file>, -F<file>, --file <file>, --file=<file>
  if (token === '-F' || token === '--file') {
    if (i + 1 < tokens.length) {
      const file = tokens[i + 1];
      if (file === '-') {
        result.hasDynamicInput = true;
      } else {
        result.referencedFiles.push(file);
      }
      return i + 1;
    }
    return i;
  }
  if (token.startsWith('--file=')) {
    const file = token.slice('--file='.length);
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i;
  }
  if (token.startsWith('-F') && token.length > 2) {
    const file = token.slice(2);
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i;
  }

  // -m <msg>, -m<msg>, --message <msg>, --message=<msg>
  if (token === '-m' || token === '--message') {
    if (i + 1 < tokens.length) {
      result.extractedTexts.push(tokens[i + 1]);
      return i + 1;
    }
    return i;
  }
  if (token.startsWith('--message=')) {
    result.extractedTexts.push(token.slice('--message='.length));
    return i;
  }
  if (token.startsWith('-m') && token.length > 2) {
    result.extractedTexts.push(token.slice(2));
    return i;
  }

  // Clustered short flags ending in m or F: e.g. -am"msg", -am msg, -sam msg
  if (token.startsWith('-') && !token.startsWith('--') && (token.includes('m') || token.includes('F'))) {
    const mIdx = token.indexOf('m');
    const fIdx = token.indexOf('F');
    if (mIdx !== -1) {
      if (mIdx < token.length - 1) {
        result.extractedTexts.push(token.slice(mIdx + 1));
      } else if (i + 1 < tokens.length) {
        result.extractedTexts.push(tokens[i + 1]);
        return i + 1;
      }
    } else if (fIdx !== -1) {
      if (fIdx < token.length - 1) {
        const file = token.slice(fIdx + 1);
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
      } else if (i + 1 < tokens.length) {
        const file = tokens[i + 1];
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
        return i + 1;
      }
    }
    return i;
  }

  return i;
}

/**
 * Parses body and body-file options (-b, --body, -F, --body-file)
 * for gh commands (pr create/edit/review/comment/merge, issue create/edit/comment).
 * Returns the updated index i.
 */
export function parseBodyFlags(
  tokens: string[],
  i: number,
  result: ParsedSubcommand,
  bodyFileFlag: string = '--body-file'
): number {
  const token = tokens[i];

  if ((token === '-b' || token === '--body') && i + 1 < tokens.length) {
    result.extractedTexts.push(tokens[i + 1]);
    return i + 1;
  }
  if (token.startsWith('-b') && token.length > 2) {
    result.extractedTexts.push(token.slice(2));
    return i;
  }
  if (token.startsWith('--body=')) {
    result.extractedTexts.push(token.slice('--body='.length));
    return i;
  }
  if ((token === '-F' || token === bodyFileFlag) && i + 1 < tokens.length) {
    const file = tokens[i + 1];
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i + 1;
  }
  if (token.startsWith('-F') && token.length > 2) {
    const file = token.slice(2);
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i;
  }
  if (token.startsWith(`${bodyFileFlag}=`)) {
    const file = token.slice(`${bodyFileFlag}=`.length);
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i;
  }

  return i;
}

/**
 * Parses title options (-t, --title) for gh commands.
 * Returns the updated index i.
 */
export function parseTitleFlags(
  tokens: string[],
  i: number,
  result: ParsedSubcommand
): number {
  const token = tokens[i];
  if ((token === '-t' || token === '--title') && i + 1 < tokens.length) {
    result.extractedTexts.push(tokens[i + 1]);
    return i + 1;
  }
  if (token.startsWith('-t') && token.length > 2) {
    result.extractedTexts.push(token.slice(2));
    return i;
  }
  if (token.startsWith('--title=')) {
    result.extractedTexts.push(token.slice('--title='.length));
    return i;
  }
  return i;
}

/**
 * Parses comment options (-c, --comment) for gh pr/issue close commands.
 * Returns the updated index i.
 */
export function parseCommentFlags(
  tokens: string[],
  i: number,
  result: ParsedSubcommand
): number {
  const token = tokens[i];
  if ((token === '-c' || token === '--comment') && i + 1 < tokens.length) {
    result.extractedTexts.push(tokens[i + 1]);
    return i + 1;
  }
  if (token.startsWith('-c') && token.length > 2) {
    result.extractedTexts.push(token.slice(2));
    return i;
  }
  if (token.startsWith('--comment=')) {
    result.extractedTexts.push(token.slice('--comment='.length));
    return i;
  }
  return i;
}

/**
 * Parses release notes options (-n, --notes, -F, --notes-file) for gh release create.
 * Returns the updated index i.
 */
export function parseReleaseNotesFlags(
  tokens: string[],
  i: number,
  result: ParsedSubcommand
): number {
  const token = tokens[i];
  if ((token === '-n' || token === '--notes') && i + 1 < tokens.length) {
    result.extractedTexts.push(tokens[i + 1]);
    return i + 1;
  }
  if (token.startsWith('-n') && token.length > 2) {
    result.extractedTexts.push(token.slice(2));
    return i;
  }
  if (token.startsWith('--notes=')) {
    result.extractedTexts.push(token.slice('--notes='.length));
    return i;
  }
  if ((token === '-F' || token === '--notes-file') && i + 1 < tokens.length) {
    const file = tokens[i + 1];
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i + 1;
  }
  if (token.startsWith('-F') && token.length > 2) {
    const file = token.slice(2);
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i;
  }
  if (token.startsWith('--notes-file=')) {
    const file = token.slice('--notes-file='.length);
    if (file === '-') {
      result.hasDynamicInput = true;
    } else {
      result.referencedFiles.push(file);
    }
    return i;
  }
  return i;
}

export function parseSubcommand(subcommand: string): ParsedSubcommand {
  const result: ParsedSubcommand = {
    raw: subcommand,
    isPublicSurfaceCommand: false,
    commandType: '',
    extractedTexts: [],
    referencedFiles: [],
    redirectedFiles: [],
    hasDynamicInput: false,
  };

  let trimmed = subcommand.trim();
  if (!trimmed) {
    return result;
  }

  // Strip subshell parentheses: ( cmd ) or (( cmd ))
  while (trimmed.startsWith('(') && trimmed.endsWith(')')) {
    trimmed = trimmed.slice(1, -1).trim();
  }
  while (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    trimmed = trimmed.slice(1, -1).trim();
  }
  if (!trimmed) {
    return result;
  }

  // Fail closed if group delimiters are unbalanced (opens a group it does not close, or closes without open)
  if (hasUnbalancedGroupDelimiters(trimmed)) {
    result.isPublicSurfaceCommand = true;
    result.hasDynamicInput = true;
    result.commandType = 'unresolvable subshell';
    return result;
  }

  if (hasDynamicShellConstructs(trimmed)) {
    result.hasDynamicInput = true;
  }

  const rawTokens = tokenizeShellWords(trimmed);
  if (rawTokens.length === 0) {
    return result;
  }

  // Detect file redirection operators in subcommand (> or >>)
  for (let i = 0; i < rawTokens.length; i++) {
    const t = rawTokens[i];
    if ((t === '>' || t === '>>' || t === '1>' || t === '1>>') && i + 1 < rawTokens.length) {
      result.redirectedFiles.push(rawTokens[i + 1]);
      i++;
    } else if (t.startsWith('>') || t.startsWith('>>') || t.startsWith('1>') || t.startsWith('1>>')) {
      const target = t.replace(/^(?:1?>{1,2})/, '');
      if (target) {
        result.redirectedFiles.push(target);
      }
    }
  }

  // Transparent shell control prefixes that precede command invocations
  const TRANSPARENT_SHELL_PREFIXES = new Set([
    'then',
    'do',
    'else',
    'elif',
    '!',
    'if',
    'while',
    'until',
    '{',
    '}',
    'builtin',
  ]);

  // Unwrap common command wrappers (command, env) and environment variable assignments
  let tokens = rawTokens;
  const leadingEnv: Record<string, string> = {};
  let cmdIdx = 0;
  while (cmdIdx < tokens.length) {
    const t = tokens[cmdIdx];
    if (TRANSPARENT_SHELL_PREFIXES.has(t)) {
      cmdIdx++;
    } else if (t === 'command') {
      cmdIdx++;
      if (cmdIdx < tokens.length && tokens[cmdIdx] === '-p') {
        cmdIdx++;
      }
    } else if (t === 'env') {
      result.setsOwnEnvironment = true;
      cmdIdx++;
      while (cmdIdx < tokens.length && tokens[cmdIdx].startsWith('-')) {
        const envTok = tokens[cmdIdx];
        if ((envTok === '-C' || envTok === '--chdir') && cmdIdx + 1 < tokens.length) {
          result.gitCwd = result.gitCwd ? resolvePath(result.gitCwd, tokens[cmdIdx + 1]) : tokens[cmdIdx + 1];
          cmdIdx += 2;
        } else if (envTok.startsWith('--chdir=')) {
          const dir = envTok.slice('--chdir='.length);
          result.gitCwd = result.gitCwd ? resolvePath(result.gitCwd, dir) : dir;
          cmdIdx++;
        } else if (envTok.startsWith('-C') && envTok.length > 2) {
          const dir = envTok.slice(2);
          result.gitCwd = result.gitCwd ? resolvePath(result.gitCwd, dir) : dir;
          cmdIdx++;
        } else if (envTok === '-u' && cmdIdx + 1 < tokens.length) {
          cmdIdx += 2;
        } else {
          cmdIdx++;
        }
      }
    } else if (/^[a-zA-Z_][a-zA-Z0-9_]*=/.test(t)) {
      const eq = t.indexOf('=');
      leadingEnv[t.slice(0, eq)] = t.slice(eq + 1);
      result.setsOwnEnvironment = true;
      cmdIdx++;
    } else {
      break;
    }
  }

  tokens = tokens.slice(cmdIdx);
  cmdIdx = 0;

  if (tokens.length === 0) {
    return result;
  }

  const getCommandBasename = (cmd: string): string => {
    return cmd.split(/[/\\]/).pop()?.toLowerCase().replace(/\.exe$/, '') ?? cmd.toLowerCase();
  };

  const binary = getCommandBasename(tokens[0]);

  // Check for eval and sh/bash/zsh -c executing git or gh
  if (binary === 'eval') {
    const evalStr = tokens.slice(1).join(' ');
    if (/\b(?:git|gh)\b/i.test(evalStr)) {
      result.isPublicSurfaceCommand = true;
      result.hasDynamicInput = true;
      result.commandType = 'eval (invoking git/gh)';
      return result;
    }
  }

  if (binary === 'sh' || binary === 'bash' || binary === 'zsh') {
    const cIndex = tokens.findIndex((tok, idx) => idx > 0 && /-[a-zA-Z]*c/.test(tok));
    if (cIndex !== -1) {
      const cmdStr = tokens.slice(cIndex + 1).join(' ');
      if (/\b(?:git|gh)\b/i.test(cmdStr)) {
        result.isPublicSurfaceCommand = true;
        result.hasDynamicInput = true;
        result.commandType = `${binary} -c (invoking git/gh)`;
        return result;
      }
    }
  }

  // Known command wrappers that might invoke git or gh
  const KNOWN_WRAPPERS = new Set([
    'sudo',
    'nohup',
    'time',
    'nice',
    'timeout',
    'exec',
    'xargs',
    'builtin',
    'strace',
    'ltrace',
    'watch',
    'setsid',
  ]);

  // If binary is neither 'git' nor 'gh' nor 'cd':
  // If it's a known wrapper, check if git or gh appears in command position after wrapper options or arguments.
  // Otherwise, ignore git/gh plain arguments (e.g. grep git notes.md, which gh, brew upgrade gh).
  if (binary !== 'git' && binary !== 'gh' && binary !== 'cd' && binary !== 'pushd') {
    if (KNOWN_WRAPPERS.has(binary)) {
      for (let i = 1; i < tokens.length; i++) {
        const innerCmd = getCommandBasename(tokens[i]);
        if (innerCmd === 'git' || innerCmd === 'gh') {
          result.isPublicSurfaceCommand = true;
          result.hasDynamicInput = true;
          result.commandType = `wrapped command (${binary} ${innerCmd})`;
          return result;
        }
      }
    }
    return result;
  }

  // Check GH_REPO= environment variable: only apply to gh commands, NOT git, and NOT gh api!
  if (leadingEnv['GH_REPO'] && binary === 'gh') {
    const sub1 = tokens.length > 1 ? tokens[1] : '';
    if (sub1 !== 'api') {
      result.targetRepo = leadingEnv['GH_REPO'].toLowerCase();
    }
  }

  // Handle cd and pushd commands for tracking directory state
  if ((binary === 'cd' || binary === 'pushd') && cmdIdx + 1 < tokens.length) {
    result.cdDir = tokens[cmdIdx + 1];
    return result;
  }

  // Find git binary in tokens
  if (binary === 'git') {
    if (leadingEnv['GIT_DIR'] || leadingEnv['GIT_WORK_TREE']) {
      result.hasGitDirOrWorkTree = true;
    }

    let subcmdIndex = -1;
    let gitCwd: string | undefined = result.gitCwd;

    // Parse git global options before the git subcommand
    for (let i = cmdIdx + 1; i < tokens.length; i++) {
      const token = tokens[i];

      // -C <dir> or -C=<dir> (case-sensitive; repeated -Cs compose!)
      if (token === '-C' && i + 1 < tokens.length) {
        gitCwd = gitCwd ? resolvePath(gitCwd, tokens[i + 1]) : tokens[i + 1];
        i++; // skip directory argument
        continue;
      }
      if (token.startsWith('-C=')) {
        const nextDir = token.slice(3);
        gitCwd = gitCwd ? resolvePath(gitCwd, nextDir) : nextDir;
        continue;
      }

      // --git-dir <path>, --git-dir=<path>, --work-tree <path>, --work-tree=<path>
      if (token === '--git-dir' || token === '--work-tree') {
        result.hasGitDirOrWorkTree = true;
        if (i + 1 < tokens.length) {
          i++; // skip path argument
        }
        continue;
      }
      if (token.startsWith('--git-dir=') || token.startsWith('--work-tree=')) {
        result.hasGitDirOrWorkTree = true;
        continue;
      }

      // Skip options that take an argument: -c <name>=<val>, --config-env <name>=<envvar>, etc.
      if (token === '-c' || token === '--config-env') {
        i++; // skip config value
        continue;
      }

      // Skip other flags
      if (token.startsWith('-')) {
        continue;
      }

      // First non-flag token is git subcommand
      subcmdIndex = i;
      break;
    }

    if (gitCwd) {
      result.gitCwd = gitCwd;
    }

    if (subcmdIndex === -1) {
      return result;
    }

    const subcmd = tokens[subcmdIndex];

    // 1. git commit
    if (subcmd === 'commit') {
      result.isPublicSurfaceCommand = true;
      result.commandType = result.hasGitDirOrWorkTree ? 'git commit (with --git-dir/GIT_DIR)' : 'git commit';

      for (let i = subcmdIndex + 1; i < tokens.length; i++) {
        const token = tokens[i];

        // Message reuse options: dynamically reuse text from history -> flag as dynamic input (fail closed)
        if (
          token === '-C' ||
          token === '-c' ||
          /^-[Cc].+/.test(token) ||
          token === '--reuse-message' ||
          token.startsWith('--reuse-message=') ||
          token === '--reedit-message' ||
          token.startsWith('--reedit-message=') ||
          token === '--fixup' ||
          token.startsWith('--fixup=') ||
          token === '--squash' ||
          token.startsWith('--squash=')
        ) {
          result.hasDynamicInput = true;
          if (
            (token === '-C' || token === '-c' || token === '--reuse-message' || token === '--reedit-message' || token === '--fixup' || token === '--squash') &&
            i + 1 < tokens.length &&
            !tokens[i + 1].startsWith('-')
          ) {
            i++;
          }
          continue;
        }

        if (token === '--amend') {
          // If amending without explicit message or file, flag as dynamic reuse
          const hasExplicitMessage = hasMessageOrFileFlag(tokens.slice(subcmdIndex + 1));
          if (!hasExplicitMessage) {
            result.hasDynamicInput = true;
          }
          continue;
        }

        // --trailer <val>, --trailer=<val>
        if (token === '--trailer' && i + 1 < tokens.length) {
          result.extractedTexts.push(tokens[i + 1]);
          i++;
          continue;
        }
        if (token.startsWith('--trailer=')) {
          result.extractedTexts.push(token.slice('--trailer='.length));
          continue;
        }

        const nextIdx = parseMessageAndFileFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }

      return result;
    }

    // 2. git tag
    if (subcmd === 'tag') {
      const isTagListingOrDeleting = tokens.slice(subcmdIndex + 1).some((t) =>
        t === '-d' || t === '-D' || t === '--delete' ||
        t === '-v' || t === '--verify' ||
        t === '-l' || t === '--list'
      );
      if (!isTagListingOrDeleting) {
        let tagFound = false;
        for (let i = subcmdIndex + 1; i < tokens.length; i++) {
          const token = tokens[i];

          const nextIdx = parseMessageAndFileFlags(tokens, i, result);
          if (nextIdx !== i) {
            i = nextIdx;
            continue;
          }

          if (token.startsWith('-')) {
            if (token === '-u' && i + 1 < tokens.length) {
              i++; // skip key-id argument
            }
            continue;
          }

          // First non-flag positional argument is the tag name
          if (!tagFound) {
            result.extractedTexts.push(token);
            tagFound = true;
          }
        }

        if (tagFound || result.extractedTexts.length > 0 || result.referencedFiles.length > 0 || result.hasDynamicInput) {
          result.isPublicSurfaceCommand = true;
          result.commandType = result.hasGitDirOrWorkTree ? 'git tag (with --git-dir/GIT_DIR)' : 'git tag';
          return result;
        }
      }
    }

    // 3. git merge
    if (subcmd === 'merge') {
      const isMergeStateCommand = tokens.slice(subcmdIndex + 1).some((t) =>
        t === '--abort' || t === '--continue' || t === '--quit'
      );
      if (!isMergeStateCommand) {
        let hasBranchRef = false;
        for (let i = subcmdIndex + 1; i < tokens.length; i++) {
          const token = tokens[i];

          const nextIdx = parseMessageAndFileFlags(tokens, i, result);
          if (nextIdx !== i) {
            i = nextIdx;
            continue;
          }

          if (token.startsWith('-')) {
            if ((token === '-s' || token === '--strategy' || token === '-X' || token === '--strategy-option') && i + 1 < tokens.length) {
              i++; // skip strategy argument
            }
            continue;
          }

          // Non-flag arguments are merge source branch/commit refs
          result.extractedTexts.push(token);
          hasBranchRef = true;
        }

        if (hasBranchRef || result.extractedTexts.length > 0 || result.referencedFiles.length > 0 || result.hasDynamicInput) {
          result.isPublicSurfaceCommand = true;
          result.commandType = result.hasGitDirOrWorkTree ? 'git merge (with --git-dir/GIT_DIR)' : 'git merge';
          return result;
        }
      }
    }
  }

  // Find gh binary in tokens
  if (binary === 'gh') {
    if (cmdIdx + 1 >= tokens.length) {
      return result;
    }

    // Extract repository flag (-R owner/repo, --repo owner/repo, -R=..., --repo=...)
    for (let i = cmdIdx + 1; i < tokens.length; i++) {
      const token = tokens[i];
      if ((token === '-R' || token === '--repo') && i + 1 < tokens.length) {
        result.targetRepo = tokens[i + 1].toLowerCase();
        break;
      }
      if (token.startsWith('--repo=')) {
        result.targetRepo = token.slice('--repo='.length).toLowerCase();
        break;
      }
      if (token.startsWith('-R=') || (token.startsWith('-R') && token.length > 2)) {
        result.targetRepo = token.slice(token.startsWith('-R=') ? 3 : 2).toLowerCase();
        break;
      }
    }

    // Check PR/Issue URLs from positional arguments only (https://github.com/owner/repo/pull/123 or issues/123)
    // Never matches URLs embedded inside -b/--body, -t/--title, or other flag arguments
    if (!result.targetRepo) {
      const positionalRepo = extractPositionalUrlRepo(tokens, cmdIdx + 1);
      if (positionalRepo) {
        result.targetRepo = positionalRepo;
      }
    }

    const sub1 = tokens[cmdIdx + 1];
    const sub2 = cmdIdx + 2 < tokens.length ? tokens[cmdIdx + 2] : '';

    // 1. gh pr create
    if (sub1 === 'pr' && sub2 === 'create') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh pr create';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const token = tokens[i];
        if (token === '-f' || token === '--fill' || token.startsWith('--fill-')) {
          result.hasDynamicInput = true;
          continue;
        }
        let nextIdx = parseTitleFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
        nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 2. gh pr edit
    if (sub1 === 'pr' && sub2 === 'edit') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh pr edit';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        let nextIdx = parseTitleFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
        nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 3. gh pr review
    if (sub1 === 'pr' && sub2 === 'review') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh pr review';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 4. gh pr comment
    if (sub1 === 'pr' && sub2 === 'comment') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh pr comment';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 5. gh pr merge
    if (sub1 === 'pr' && sub2 === 'merge') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh pr merge';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const token = tokens[i];
        if (token === '--subject' && i + 1 < tokens.length) {
          result.extractedTexts.push(tokens[i + 1]);
          i++;
          continue;
        }
        if (token.startsWith('--subject=')) {
          result.extractedTexts.push(token.slice('--subject='.length));
          continue;
        }
        const nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 6. gh pr close
    if (sub1 === 'pr' && sub2 === 'close') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh pr close';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const nextIdx = parseCommentFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 7. gh issue create
    if (sub1 === 'issue' && sub2 === 'create') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh issue create';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        let nextIdx = parseTitleFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
        nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 8. gh issue edit
    if (sub1 === 'issue' && sub2 === 'edit') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh issue edit';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        let nextIdx = parseTitleFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
        nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 9. gh issue comment
    if (sub1 === 'issue' && sub2 === 'comment') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh issue comment';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const nextIdx = parseBodyFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 10. gh issue close
    if (sub1 === 'issue' && sub2 === 'close') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh issue close';

      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const nextIdx = parseCommentFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
      }
      return result;
    }

    // 11. gh release create
    if (sub1 === 'release' && sub2 === 'create') {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh release create';

      let tagFound = false;
      for (let i = cmdIdx + 3; i < tokens.length; i++) {
        const token = tokens[i];
        let nextIdx = parseTitleFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
        nextIdx = parseReleaseNotesFlags(tokens, i, result);
        if (nextIdx !== i) {
          i = nextIdx;
          continue;
        }
        if (token.startsWith('-')) {
          if ((token === '--target' || token === '--discussion-category') && i + 1 < tokens.length) {
            i++;
          }
          continue;
        }
        // First positional non-flag argument is the release tag
        if (!tagFound) {
          result.extractedTexts.push(token);
          tagFound = true;
        }
      }
      return result;
    }

    // 6. gh api
    if (sub1 === 'api') {
      const isGraphql = tokens.some((t) => t === 'graphql' || t.includes('/graphql'));

      // Option flags for `gh api` that consume the next token as their value
      const GH_API_VALUE_FLAGS = new Set([
        '--input',
        '-f',
        '-F',
        '--field',
        '--raw-field',
        '-H',
        '--header',
        '-X',
        '--method',
        '-q',
        '--jq',
        '-t',
        '--template',
        '--cache',
        '-p',
        '--preview',
      ]);

      for (let i = cmdIdx + 2; i < tokens.length; i++) {
        const token = tokens[i];

        if (token.startsWith('-')) {
          if (GH_API_VALUE_FLAGS.has(token) && i + 1 < tokens.length) {
            i++; // skip option argument
          }
          continue;
        }

        // First non-flag positional argument is the API endpoint
        let endpoint = token.replace(/^(?:https?:\/\/[^/]+)?\/+/, '');
        // Strip optional v3 or api/v3 prefix
        endpoint = endpoint.replace(/^(?:api\/)?v3\/+/, '');

        if (endpoint.startsWith('repos/')) {
          const parts = endpoint.slice('repos/'.length).split('/');
          if (parts.length >= 2) {
            const rawSlug = `${parts[0]}/${parts[1]}`.toLowerCase();
            // Do NOT treat literal placeholders like repos/{owner}/{repo}/... as an explicit target
            if (!rawSlug.includes('{')) {
              result.targetRepo = rawSlug;
            }
          }
          break;
        }
        const GITHUB_API_NON_REPO_ROUTES = new Set([
          'orgs',
          'users',
          'user',
          'teams',
          'gists',
          'notifications',
          'search',
          'rate_limit',
          'emojis',
          'events',
          'feeds',
          'issues',
          'markdown',
          'meta',
          'app',
          'installations',
        ]);

        const firstSegment = endpoint.split('/')[0].toLowerCase();
        if (!GITHUB_API_NON_REPO_ROUTES.has(firstSegment) && /^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+/.test(endpoint)) {
          const parts = endpoint.split('/');
          result.targetRepo = `${parts[0]}/${parts[1]}`.toLowerCase();
          break;
        }

        // If literal endpoint is not graphql and has no placeholders, mark it so cwd remote does not exempt it
        if (!isGraphql) {
          result.isLiteralUnknownEndpoint = true;
        }
        break;
      }

      for (let i = cmdIdx + 2; i < tokens.length; i++) {
        const token = tokens[i];

        // --input <file>, --input=<file>
        if (token === '--input' && i + 1 < tokens.length) {
          const file = tokens[i + 1];
          if (file === '-') {
            result.hasDynamicInput = true;
          } else {
            result.referencedFiles.push(file);
          }
          i++;
          continue;
        }
        if (token.startsWith('--input=')) {
          const file = token.slice('--input='.length);
          if (file === '-') {
            result.hasDynamicInput = true;
          } else {
            result.referencedFiles.push(file);
          }
          continue;
        }

        // -f <name>=<val>, -F <name>=<val>, --field <name>=<val>, --raw-field <name>=<val>
        if ((token === '-f' || token === '-F' || token === '--field' || token === '--raw-field') && i + 1 < tokens.length) {
          const fieldArg = tokens[i + 1];
          const eqIdx = fieldArg.indexOf('=');
          if (eqIdx !== -1) {
            const val = fieldArg.slice(eqIdx + 1);
            if (val.startsWith('@')) {
              result.referencedFiles.push(val.slice(1));
            } else {
              result.extractedTexts.push(val);
            }
          }
          i++;
          continue;
        }

        // Attached short field forms: -fbody="...", -Fbody=@file, -fquery="...", etc.
        const attachedFieldMatch = token.match(/^-([fF])([a-zA-Z0-9_.-]+)=(.*)$/s);
        if (attachedFieldMatch) {
          const val = attachedFieldMatch[3];
          if (val.startsWith('@')) {
            result.referencedFiles.push(val.slice(1));
          } else {
            result.extractedTexts.push(val);
          }
          continue;
        }

        const fieldMatch = token.match(/^(?:--field|--raw-field)=(.*?)=(.*)$/s);
        if (fieldMatch) {
          const val = fieldMatch[2];
          if (val.startsWith('@')) {
            result.referencedFiles.push(val.slice(1));
          } else {
            result.extractedTexts.push(val);
          }
          continue;
        }

        if (isGraphql && token.includes('mutation')) {
          result.extractedTexts.push(token);
          result.isGraphqlMutation = true;
        }
      }

      // Check if GraphQL query string specifies a mutation
      if (isGraphql) {
        for (const t of result.extractedTexts) {
          if (/\bmutation\b/i.test(t)) {
            result.isGraphqlMutation = true;
            break;
          }
        }
        // If a GraphQL query is loaded from a file (--input or @file),
        // we cannot verify statically without reading the file.
        // Treat as a mutation so it is NEVER exempted from the tracker checkout.
        if (!result.isGraphqlMutation && result.referencedFiles.length > 0) {
          result.isGraphqlMutation = true;
        }
      }

      if (result.extractedTexts.length > 0 || result.referencedFiles.length > 0 || result.hasDynamicInput || result.isGraphqlMutation) {
        result.isPublicSurfaceCommand = true;
        result.commandType = 'gh api';
      }

      return result;
    }
  }

  return result;
}

/**
 * Inspects a directory's .git/config to determine if it points to tracker_repo or upstream_repo.
 * Strict exact owner/repo slug matching is enforced (no substring .includes).
 * If both remotes exist, upstream takes precedence.
 */
export async function inspectDirectoryRemote(
  dir: string | undefined,
  projectConfig: ProjectRepos,
  readFile?: FileReader
): Promise<{ isTracker: boolean; isUpstream: boolean; determined: boolean; detectedUpstreamSlug?: string }> {
  if (!readFile) {
    return { isTracker: false, isUpstream: false, determined: false };
  }

  const gitConfigPath = resolvePath(dir, '.git/config');
  let configContent: string | null = null;
  try {
    const raw = await readFile(gitConfigPath);
    if (raw && typeof raw === 'string') {
      configContent = raw;
    }
  } catch {
    configContent = null;
  }

  // If reading .git/config failed, check if .git is a worktree gitdir file
  if (!configContent) {
    try {
      const gitFilePath = resolvePath(dir, '.git');
      const gitFileContent = await readFile(gitFilePath);
      if (gitFileContent && typeof gitFileContent === 'string') {
        const gitDirMatch = gitFileContent.match(/gitdir:\s*([^\r\n]+)/i);
        if (gitDirMatch) {
          const resolvedGitDir = resolvePath(dir, gitDirMatch[1].trim());
          const commonDir = resolvedGitDir.replace(/[\\/]worktrees[\\/][^\\/]+$/, '');
          const candidateConfigPaths = [
            resolvePath(commonDir, 'config'),
            resolvePath(resolvedGitDir, 'config'),
          ];
          for (const cfgPath of candidateConfigPaths) {
            try {
              const raw = await readFile(cfgPath);
              if (raw && typeof raw === 'string' && /url\s*=/i.test(raw)) {
                configContent = raw;
                break;
              }
              if (!configContent && raw && typeof raw === 'string') {
                configContent = raw;
              }
            } catch {
              // Try next candidate
            }
          }
        }
      }
    } catch {
      configContent = null;
    }
  }

  if (!configContent) {
    return { isTracker: false, isUpstream: false, determined: false };
  }

  try {
    const configLower = configContent.toLowerCase();
    const urlMatches = configLower.matchAll(/url\s*=\s*([^\r\n]+)/g);
    const urls: string[] = [];
    for (const m of urlMatches) {
      urls.push(m[1].trim());
    }

    if (urls.length === 0) {
      return { isTracker: false, isUpstream: false, determined: false };
    }

    const trackerSlug = projectConfig.trackerRepo?.toLowerCase();
    const upstreamSlug = projectConfig.upstreamRepo?.toLowerCase();
    const upstreamRepoName = upstreamSlug?.includes('/') ? upstreamSlug.split('/')[1] : upstreamSlug;
    const trackerRepoName = trackerSlug?.includes('/') ? trackerSlug.split('/')[1] : trackerSlug;

    const extractSlugFromUrl = (url: string): string | undefined => {
      if (!url) return undefined;
      let cleanUrl = url.trim();
      // Strip surrounding quotes
      if (
        (cleanUrl.startsWith('"') && cleanUrl.endsWith('"')) ||
        (cleanUrl.startsWith("'") && cleanUrl.endsWith("'"))
      ) {
        cleanUrl = cleanUrl.slice(1, -1).trim();
      }
      // Strip trailing inline comments (e.g. # comment or ; comment)
      cleanUrl = cleanUrl.replace(/\s+[#;].*$/, '').trim();
      // Strip trailing slashes
      cleanUrl = cleanUrl.replace(/\/+$/, '');
      // Strip trailing .git extension
      cleanUrl = cleanUrl.replace(/\.git$/, '');
      cleanUrl = cleanUrl.toLowerCase();
      const match = cleanUrl.match(/(?:[:/])([a-z0-9_.-]+\/[a-z0-9_.-]+)$/);
      return match ? match[1] : undefined;
    };

    let detectedUpstreamSlug: string | undefined = undefined;
    for (const u of urls) {
      const s = extractSlugFromUrl(u);
      if (s && s !== trackerSlug) {
        detectedUpstreamSlug = s;
        break;
      }
    }

    // Upstream match takes precedence over tracker match
    const isUpstream = upstreamSlug
      ? urls.some((u) => {
          const extracted = extractSlugFromUrl(u);
          return extracted === upstreamSlug || (upstreamRepoName && extracted?.endsWith(`/${upstreamRepoName}`));
        })
      : false;

    const isTracker = !isUpstream && trackerSlug
      ? urls.some((u) => {
          const extracted = extractSlugFromUrl(u);
          return extracted === trackerSlug || (trackerRepoName && extracted?.endsWith(`/${trackerRepoName}`));
        })
      : false;

    const anySlugParsed = urls.some((u) => extractSlugFromUrl(u) !== undefined);

    return {
      isTracker,
      isUpstream,
      determined: anySlugParsed,
      detectedUpstreamSlug,
    };
  } catch {
    return { isTracker: false, isUpstream: false, determined: false };
  }
}

export interface EvaluationOptions {
  cwd?: string;
  isSessionRootFallback?: boolean;
  env?: { [key: string]: string | undefined };
  readFile?: FileReader;
  projectConfig?: ProjectRepos;
}

/**
 * Generates user-facing blocking reason without instructing agent how to bypass.
 */
export function generateBlockingReason(commandType: string, terms: string[]): string {
  const termList = terms.map((t) => `\`${t}\``).join(', ');
  return [
    `⛔ Apache Magpie Security Guard: Blocked public-surface command (${commandType}).`,
    `Found forbidden security disclosure term(s): ${termList}.`,
    '',
    'This hook is an automated guard against accidental public disclosure of embargoed security information,',
    'not a perimeter against deliberate circumvention.',
    '',
    'Confidentiality Rule (AGENTS.md & docs/security/fixing-security-issues.md):',
    'Public commits, tags, PR descriptions, and comments on upstream repositories must describe the change in neutral functional terms without mentioning CVE IDs or vulnerability classes before the coordinated disclosure advisory has shipped.',
    'If this is legitimate post-coordinated-disclosure maintenance, consult an Apache Magpie security-team maintainer to review and set the environment bypass.',
  ].join('\n');
}

/**
 * Commands known to be purely read-only or harmless environment manipulations.
 * If any preceding command on a composite shell line is NOT in this set,
 * subsequent file reads (-F <file>) fail closed as dynamic input.
 */
const SAFE_READONLY_COMMANDS = new Set([
  'cd',
  'pushd',
  'popd',
  'dirs',
  'pwd',
  'test',
  '[',
  'echo',
  'printf',
  'cat',
  'ls',
  'true',
  'false',
  ':',
  'export',
  'set',
  'unset',
  'readonly',
]);

/**
 * Commands that cannot change the shell's environment or the repository's configuration for the
 * commands after them on the line. `cd` changes only the directory, which the evaluation loop
 * tracks itself (`pushd` / `popd` are not tracked, so they are not here). `git` is allowed only
 * with a read-or-stage subcommand ({@link REPOSITORY_PRESERVING_GIT_SUBCOMMANDS}): others, such as
 * `git remote set-url` or `git config`, can repoint a later command at another repository.
 */
const ENVIRONMENT_PRESERVING_COMMANDS = new Set([
  'git',
  'echo',
  'test',
  '[',
  'true',
  'false',
  ':',
  'pwd',
  'ls',
  'cat',
  'cd',
]);

const REPOSITORY_PRESERVING_GIT_SUBCOMMANDS = new Set(['add', 'status', 'diff', 'log', 'show']);

/**
 * Environment variables that choose which repository git or gh acts on. Set in the session's own
 * environment, any of them removes the directory-based exemption for every bare git / gh command.
 */
const REPOSITORY_SELECTING_ENV_VARS = [
  'GH_REPO',
  'GH_HOST',
  'GIT_DIR',
  'GIT_WORK_TREE',
  'GIT_COMMON_DIR',
  'GIT_INDEX_FILE',
  'GIT_OBJECT_DIRECTORY',
  'GIT_ALTERNATE_OBJECT_DIRECTORIES',
  'GIT_NAMESPACE',
  'GIT_CEILING_DIRECTORIES',
  'GIT_CONFIG_GLOBAL',
  'GIT_CONFIG_SYSTEM',
  'GIT_CONFIG_COUNT',
];

/** `gh <noun> <verb>` verbs that only read (`gh issue view`); others, such as `gh repo set-default`, can repoint gh. */
const READ_ONLY_GH_VERBS = new Set(['view', 'list', 'status', 'diff']);

/**
 * True when a subcommand may change which repository a LATER git or gh subcommand on the line acts
 * on, without changing directory. An allow-list, failing closed: the shell has too many ways to
 * change the environment (`export GIT_DIR=...` and its `builtin` / `command` / `declare` / `+=`
 * forms, `export GH_REPO=...`, `eval`, `source`, function and alias definitions, `PATH=...`, ...)
 * for a deny-list to stay complete. So only a segment whose command is on
 * {@link ENVIRONMENT_PRESERVING_COMMANDS}, with no leading variable assignment,
 * keeps a later git or gh command's directory-based exemption. A legitimate tracker commit is run
 * on its own or after one of those.
 */
function mayRedirectLaterCommands(subcommand: string): boolean {
  // Any output redirection, expansion, command substitution or process substitution can run, write
  // or assign something (`printf ... > .git/config`, `echo $(git remote set-url ...)`,
  // `echo ${GH_REPO:=...}`) before the later command runs, while remote inspection already read
  // the old state: fail closed on all of them.
  if (/[>`$]|<\(/.test(subcommand)) {
    return true;
  }
  // A brace group runs in the current shell; its braces change nothing themselves.
  const words = tokenizeShellWords(subcommand.trim()).filter((w) => w !== '{' && w !== '}');
  if (words.length === 0) {
    return false;
  }
  if (words[0] === 'gh') {
    return !READ_ONLY_GH_VERBS.has(words[2] ?? '');
  }
  if (!ENVIRONMENT_PRESERVING_COMMANDS.has(words[0])) {
    return true; // includes a leading `VAR=value`, `export`, `builtin`, `eval`, `if`, `f() {`, ...
  }
  if (words[0] === 'cd') {
    // Only a plain `cd <dir>` is tracked as a directory change; `cd a b` fails (too many operands)
    // and leaves the shell where it was, and options or `cd -` move it somewhere the tracking
    // does not model.
    return words.length !== 2 || words[1].startsWith('-');
  }
  if (words[0] === 'git') {
    // `git diff --output=.git/config` writes a file; any `--output` / `-o` option disqualifies.
    return (
      !REPOSITORY_PRESERVING_GIT_SUBCOMMANDS.has(words[1] ?? '') ||
      words.slice(2).some((w) => w.startsWith('--output') || w === '-o')
    );
  }
  return false;
}


/**
 * Evaluates whether a public-surface command violates embargo terms.
 * Evaluates per subcommand, respects project.md config for tracker/upstream resolution,
 * tracks cd directory transitions across subcommands, fails closed on unreadable files,
 * dynamic pipelines, and indeterminate repositories, and honours only human-set environment escape hatches.
 */
export async function evaluatePublicSurfaceCommand(
  commandLine: string,
  options?: EvaluationOptions
): Promise<{ blocked: boolean; matchedTerms: string[]; reason?: string }> {
  // Deterministic escape hatch: honour ONLY environment variable set by human before session
  if (options?.env?.MAGPIE_ALLOW_EMBARGO_TERMS === '1') {
    return { blocked: false, matchedTerms: [] };
  }

  if (!commandLine || typeof commandLine !== 'string') {
    return { blocked: false, matchedTerms: [] };
  }

  // Split command line into individual subcommands preserving operators
  const subcommands = splitShellSubcommands(commandLine);

  let virtualCwd: string | undefined = options?.cwd;
  const subshellCwdStack: (string | undefined)[] = [];
  const seenRedirectedFiles = new Set<string>();
  let hasPotentiallyMutatingPriorCommand = false;
  // Set once an earlier subcommand on the line may have changed the environment (a GIT_* / GH_*
  // variable, or an opaque builtin), which can point a later bare git or gh command at another
  // repository without changing directory.
  let hasPriorRedirect = REPOSITORY_SELECTING_ENV_VARS.some((name) => Boolean(options?.env?.[name]));

  let hasSeenConditional = false;
  let hasSeenPipeOrBackground = false;
  for (const item of subcommands) {
    if (item.subshellDepthDeltaBefore) {
      for (let d = 0; d < item.subshellDepthDeltaBefore; d++) {
        subshellCwdStack.push(virtualCwd);
      }
    }

    if (item.hasUnclosedQuoteWithBinary) {
      return {
        blocked: true,
        matchedTerms: ['unclosed quote', 'dynamic input'],
        reason:
          '⛔ Apache Magpie Security Guard: Blocked command with unclosed quote containing git/gh binary to prevent quote-blinded bypass.',
      };
    }

    const finishSubcommand = () => {
      if (item.subshellDepthDeltaAfter) {
        for (let d = 0; d < item.subshellDepthDeltaAfter; d++) {
          virtualCwd = subshellCwdStack.pop();
        }
      }
    };

    const rawSub = item.raw;
    const parsed = parseSubcommand(rawSub);
    const isRedirectedByPriorCommand =
      // An own-environment git or gh command (`GIT_COMMON_DIR=... git tag`, `env ... git tag`, after
      // any prefix): parseSubcommand acts only on GIT_DIR / GIT_WORK_TREE, and git reads many more.
      // An expansion or substitution inside the git or gh command itself (`gh issue create -t
      // "$(git remote set-url ...)"`, `"${GH_REPO:=...}"`, `>(...)`) runs before the command
      // resolves its repository; same fail-closed set as mayRedirectLaterCommands.
      (hasPriorRedirect || parsed.setsOwnEnvironment === true || /[`$]|[<>]\(/.test(rawSub)) &&
      (parsed.commandType.startsWith('git ') || parsed.commandType.startsWith('gh '));
    // The directory tracking follows every `cd`, but once an `&&` or `||` has appeared on the line a
    // later `cd` may run only conditionally (`false && cd /tracker`, `cd /upstream || cd /tracker`,
    // `false && { true; cd /tracker; }`), so the tracked directory can disagree with the shell:
    // any such `cd`, or anything followed by `||`, is a redirect.
    const isConditionalCd = Boolean(parsed.cdDir) && hasSeenConditional;
    // With CDPATH set, `cd name` searches the CDPATH entries before the current directory, so the
    // tracked directory can name a different checkout than the one the shell lands in. Bash skips
    // the search only for `/...`, `.`, `..`, `./...` and `../...` (`.hidden` is still searched).
    const isCdPathCd =
      Boolean(parsed.cdDir) && Boolean(options?.env?.CDPATH) && !/^(\/|\.\.?(\/|$))/.test(parsed.cdDir ?? '');
    // A `cd` in a pipeline or a background job runs in a subshell and leaves the shell where it was.
    // `separatorAfter` shows only a `cd` that starts a pipeline; one in a later stage (`echo | cd x;`,
    // `echo | { true; cd x; }`) ends with `;`, so once a `|` or `&` has appeared any `cd` is a redirect,
    // as is one inside a group that is itself piped or backgrounded (`{ cd x; true; } | cat`).
    const isSubshellCd =
      Boolean(parsed.cdDir) &&
      (hasSeenPipeOrBackground ||
        item.inPipedOrBackgroundGroup === true ||
        item.separatorAfter === '|' ||
        item.separatorAfter === '&');
    if (
      mayRedirectLaterCommands(rawSub) ||
      item.separatorAfter === '||' ||
      isConditionalCd ||
      isCdPathCd ||
      isSubshellCd
    ) {
      hasPriorRedirect = true;
    }
    if (item.separatorAfter === '&&' || item.separatorAfter === '||') {
      hasSeenConditional = true;
    }
    if (item.separatorAfter === '|' || item.separatorAfter === '&') {
      hasSeenPipeOrBackground = true;
    }

    // Track cd transitions: update virtualCwd across sequential operators (&&, ;, \n, ||)
    // Only exclude pipeline (|) and background (&) which run in subshells
    if (parsed.cdDir) {
      if (item.separatorAfter !== '|' && item.separatorAfter !== '&') {
        virtualCwd = resolvePath(virtualCwd, parsed.cdDir);
      }
      finishSubcommand();
      continue;
    }

    // Check if any referenced file was redirected into earlier in the same composite command,
    // or if an earlier command in the same line could have modified files (e.g. cp, mv, tee)
    if (parsed.referencedFiles.length > 0) {
      if (hasPotentiallyMutatingPriorCommand) {
        parsed.hasDynamicInput = true;
      }
      for (const ref of parsed.referencedFiles) {
        const resolved = resolvePath(virtualCwd, ref);
        if (seenRedirectedFiles.has(resolved) || seenRedirectedFiles.has(ref)) {
          parsed.hasDynamicInput = true;
        }
      }
    }

    // Record newly redirected files from this subcommand
    for (const red of parsed.redirectedFiles) {
      seenRedirectedFiles.add(resolvePath(virtualCwd, red));
      seenRedirectedFiles.add(red);
    }

    // If this subcommand is not a public surface command, check if it could mutate files
    if (!parsed.isPublicSurfaceCommand) {
      const subWords = tokenizeShellWords(rawSub.trim());
      let priorBinary = '';
      for (const w of subWords) {
        if (/^[a-zA-Z_][a-zA-Z0-9_]*=/.test(w)) continue;
        priorBinary = w.split(/[/\\]/).pop()?.toLowerCase().replace(/\.exe$/, '') ?? w.toLowerCase();
        break;
      }
      if (!priorBinary || !SAFE_READONLY_COMMANDS.has(priorBinary) || parsed.redirectedFiles.length > 0) {
        hasPotentiallyMutatingPriorCommand = true;
      }
      finishSubcommand();
      continue;
    }

    // Resolve git -C relative to virtualCwd, not bare
    const effectiveDir = parsed.gitCwd ? resolvePath(virtualCwd, parsed.gitCwd) : virtualCwd;

    // Resolve project configuration (tracker_repo, upstream_repo, upstream_clone) for this subcommand's scope
    const projectConfig = options?.projectConfig ?? (await resolveProjectConfig(options?.readFile, effectiveDir, options?.env));
    const trackerRepo = projectConfig.trackerRepo?.toLowerCase();
    let upstreamRepo = projectConfig.upstreamRepo?.toLowerCase();
    // Set when the tracker cwd exemption was skipped under the session-root fallback.
    let trackerFallbackHint: string | undefined;

    // 1. Exemption: Subcommand explicitly targets the private security tracker
    // GraphQL mutations address resources by global Node IDs, which the hook cannot resolve;
    // therefore a GraphQL mutation is NEVER exempt, even if targeted at tracker or with GH_REPO=<tracker>
    if (parsed.targetRepo && trackerRepo && parsed.targetRepo === trackerRepo) {
      if (!parsed.isGraphqlMutation) {
        finishSubcommand();
        continue;
      }
    }

    // 2. Check if working directory is inside the configured upstream_clone path
    let isWorkingDirUpstreamClone = false;
    if (projectConfig.upstreamClonePath) {
      const normClone = projectConfig.upstreamClonePath.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();
      const normDir = (effectiveDir || '.').replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();
      if (normDir === normClone || normDir.startsWith(`${normClone}/`)) {
        isWorkingDirUpstreamClone = true;
      }
    }

    // 3. Inspect directory remote from .git/config
    let remoteInfo: { isTracker: boolean; isUpstream: boolean; determined: boolean; detectedUpstreamSlug?: string } = {
      isTracker: false,
      isUpstream: isWorkingDirUpstreamClone,
      determined: isWorkingDirUpstreamClone,
    };

    if (options?.readFile) {
      const inspected = await inspectDirectoryRemote(effectiveDir, projectConfig, options.readFile);
      if (inspected.determined) {
        remoteInfo = inspected;
        if (isWorkingDirUpstreamClone) {
          remoteInfo.isUpstream = true;
        }
      }
      if (!upstreamRepo && isWorkingDirUpstreamClone && remoteInfo.detectedUpstreamSlug) {
        upstreamRepo = remoteInfo.detectedUpstreamSlug.toLowerCase();
      }
    }

    const upstreamRepoName = upstreamRepo?.includes('/') ? upstreamRepo.split('/')[1] : upstreamRepo;

    // 4. Repository scoping: Subcommands targeting upstream or a contributor's fork of upstream must be scrubbed.
    // Subcommands targeting an explicit unrelated repository (e.g. adopter docs, framework) pass unchecked.
    const isTargetUpstreamOrFork =
      parsed.targetRepo &&
      upstreamRepo &&
      (parsed.targetRepo === upstreamRepo ||
        (upstreamRepoName && parsed.targetRepo.endsWith(`/${upstreamRepoName}`)));

    if (parsed.targetRepo && !isTargetUpstreamOrFork) {
      // If the target repository contains shell variables ($VAR, `cmd`), fail closed as dynamic input.
      const isDynamicTarget = /[$`]/.test(parsed.targetRepo);
      if (isDynamicTarget) {
        parsed.hasDynamicInput = true;
      } else if (!upstreamRepo) {
        // Upstream repo is not configured: cannot exempt, fall through to term scan instead of blocking
      } else {
        finishSubcommand();
        continue; // Verified non-upstream target repo
      }
    }

    // 5. For commands without explicit repo flag, determine repository from git context
    if (!parsed.targetRepo) {
      // GraphQL mutations address resources by global Node IDs, which the hook cannot resolve.
      // Therefore, a GraphQL mutation is NEVER exempt, regardless of whether cwd is the tracker.
      if (parsed.isGraphqlMutation) {
        // Proceed directly to inspection
      } else if (
        parsed.commandType.includes('git-dir') ||
        parsed.commandType.includes('work-tree') ||
        parsed.commandType.includes('GIT_DIR') ||
        parsed.commandType.includes('wrapped') ||
        // `bash -c '...'` and `eval '...'` can cd or set GIT_DIR inside the string before git / gh runs
        parsed.commandType.includes('invoking git/gh') ||
        isRedirectedByPriorCommand
      ) {
        // Repository context is redirected or indeterminate — cwd remoteInfo cannot exempt it
        // Proceed directly to inspection and dynamic-input fail-closed check
      } else if (remoteInfo.determined) {
        if (remoteInfo.isTracker && !parsed.isLiteralUnknownEndpoint) {
          if (options?.isSessionRootFallback) {
            // When scope comes from session-root fallback, cwd might not reflect an earlier cd ../<upstream>.
            // Do NOT apply tracker exemption; fall through to term scan!
            trackerFallbackHint = trackerRepo;
          } else {
            finishSubcommand();
            continue; // Safe tracker repository
          }
        } else if (upstreamRepo && !remoteInfo.isUpstream && !parsed.isLiteralUnknownEndpoint) {
          finishSubcommand();
          continue; // Known non-upstream remote (only safe when upstreamRepo is known)
        }
      }
    }

    // If dynamic input (stdin -, heredoc, command substitution, variable, pipe, gh pr create --fill, git commit --amend/reuse) is present
    if (parsed.hasDynamicInput) {
      // First check if the commandLine itself explicitly carries forbidden terms
      const dynamicTerms = findForbiddenTerms(commandLine);
      if (dynamicTerms.length > 0) {
        const uniqueTerms = Array.from(new Set(dynamicTerms));
        return {
          blocked: true,
          matchedTerms: uniqueTerms,
          reason: generateBlockingReason(parsed.commandType, uniqueTerms),
        };
      }

      // If this was a wrapped command (e.g. sudo git, nohup git), provide specific message
      if (parsed.commandType.startsWith('wrapped command')) {
        return {
          blocked: true,
          matchedTerms: ['dynamic input', 'wrapped command'],
          reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Invocations wrapped by sudo, nohup, timeout, xargs, etc. cannot be verified deterministically before publication. Run the git or gh command directly.`,
        };
      }

      // Dynamic input without explicit terms in command line: fail closed
      return {
        blocked: true,
        matchedTerms: ['dynamic input'],
        reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}) with indeterminate dynamic input. Content constructed from variables ($VAR), command substitution ($(..)), stdin (-), or automated reuse (--amend/--fill) cannot be verified deterministically before publication. Provide the text explicitly or via an inspectable file (-F <file>).`,
      };
    }

    const candidateTexts: string[] = [...parsed.extractedTexts];

    // Read and verify referenced message files
    for (const file of parsed.referencedFiles) {
      const resolvedPath = resolvePath(effectiveDir, file);
      if (!options?.readFile) {
        return {
          blocked: true,
          matchedTerms: [],
          reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Referenced message file cannot be read: \`${resolvedPath}\`.`,
        };
      }

      try {
        const content = await options.readFile(resolvedPath);
        if (content === null || content === undefined || typeof content !== 'string') {
          return {
            blocked: true,
            matchedTerms: [],
            reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Referenced message file could not be read: \`${resolvedPath}\`.`,
          };
        }
        candidateTexts.push(content);
      } catch {
        return {
          blocked: true,
          matchedTerms: [],
          reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Referenced message file could not be read: \`${resolvedPath}\`.`,
        };
      }
    }

    // Check for forbidden terms
    const combinedText = candidateTexts.join('\n');
    const matched = findForbiddenTerms(combinedText);

    if (matched.length > 0) {
      const uniqueTerms = Array.from(new Set(matched));
      let reason = generateBlockingReason(parsed.commandType, uniqueTerms);
      if (trackerFallbackHint) {
        // The Bash tool call carries no cwd, so a command run in the tracker checkout cannot be
        // told apart from one run after an earlier `cd ../<upstream>`; an explicit target can.
        if (parsed.commandType.startsWith('git ')) {
          // git commit/tag/merge has no --repo flag; only the directory it runs in identifies the repository.
          reason +=
            '\nThe current directory of this command could not be determined, so the private-tracker exemption ' +
            'was not applied. A git command has no repository flag; the exemption needs a known working directory ' +
            'inside the tracker checkout.';
        } else {
          reason += `\nIf this command targets the private tracker, name it explicitly: \`--repo ${trackerFallbackHint}\`.`;
        }
      }
      return {
        blocked: true,
        matchedTerms: uniqueTerms,
        reason,
      };
    }

    finishSubcommand();
  }

  return { blocked: false, matchedTerms: [] };
}

/**
 * Registers the PreToolUse hook for Claude Code.
 * Intercepts Bash tool calls, parses commands, verifies embargo terms,
 * and returns { deny: reason } when embargo terms are detected.
 */
export function register(on: any): void {
  on('tool.call', { tool: 'Bash' }, async ($: any, e: any, next: any) => {
    const command = e?.command;

    if (typeof command === 'string') {
      let initialCwd: string | undefined = e?.cwd || e?.directory;
      let isSessionRootFallback = false;
      if (!initialCwd) {
        // The Bash tool event carries no directory. $.session.cwd() is the session's current
        // directory: the shell's directory as left by earlier Bash calls (a `cd` that persists
        // across calls moves it), or the calling agent's own directory. $.session.root() is only
        // where the session started, so it is used just when the current directory is unknown.
        try {
          const current = await $.session.cwd();
          if (typeof current === 'string' && current) {
            initialCwd = current;
          }
        } catch {
          // $.session.cwd may be absent in mock harnesses or older engines
        }
      }
      if (!initialCwd) {
        try {
          initialCwd = await $.session.root();
          isSessionRootFallback = true;
        } catch {
          // $.session may be absent in mock harnesses
        }
      }
      let allowBypass: string | undefined;
      try {
        allowBypass = await $.env.get('MAGPIE_ALLOW_EMBARGO_TERMS');
      } catch {
        // $.env may be absent in mock harnesses
      }
      const hookEnv: { [key: string]: string | undefined } = allowBypass
        ? { MAGPIE_ALLOW_EMBARGO_TERMS: allowBypass }
        : {};
      // A repository-selecting variable inherited by the session (Claude launched with GH_REPO or
      // GIT_DIR set) repoints every bare git / gh command, whatever the directory says.
      // The mod API needs a literal name at every $.env.get call, so each variable is spelled out;
      // keep this list in step with REPOSITORY_SELECTING_ENV_VARS.
      const inherited: [string, () => Promise<string | undefined>][] = [
        ['GH_REPO', () => $.env.get('GH_REPO')],
        ['GH_HOST', () => $.env.get('GH_HOST')],
        ['GIT_DIR', () => $.env.get('GIT_DIR')],
        ['GIT_WORK_TREE', () => $.env.get('GIT_WORK_TREE')],
        ['GIT_COMMON_DIR', () => $.env.get('GIT_COMMON_DIR')],
        ['GIT_INDEX_FILE', () => $.env.get('GIT_INDEX_FILE')],
        ['GIT_OBJECT_DIRECTORY', () => $.env.get('GIT_OBJECT_DIRECTORY')],
        ['GIT_ALTERNATE_OBJECT_DIRECTORIES', () => $.env.get('GIT_ALTERNATE_OBJECT_DIRECTORIES')],
        ['GIT_NAMESPACE', () => $.env.get('GIT_NAMESPACE')],
        ['GIT_CEILING_DIRECTORIES', () => $.env.get('GIT_CEILING_DIRECTORIES')],
        ['GIT_CONFIG_GLOBAL', () => $.env.get('GIT_CONFIG_GLOBAL')],
        ['GIT_CONFIG_SYSTEM', () => $.env.get('GIT_CONFIG_SYSTEM')],
        ['GIT_CONFIG_COUNT', () => $.env.get('GIT_CONFIG_COUNT')],
        // Not repository-selecting by itself, but it moves a relative `cd` (see isCdPathCd).
        ['CDPATH', () => $.env.get('CDPATH')],
      ];
      for (const [name, read] of inherited) {
        try {
          const value = await read();
          if (value) hookEnv[name] = value;
        } catch {
          // $.env may be absent in mock harnesses
        }
      }
      const evaluation = await evaluatePublicSurfaceCommand(command, {
        cwd: initialCwd,
        isSessionRootFallback,
        env: hookEnv,
        readFile: async (filePath: string) => {
          try {
            return await $.fs.read(filePath);
          } catch {
            return null;
          }
        },
      });

      if (evaluation.blocked && evaluation.reason) {
        return {
          deny: evaluation.reason,
        };
      }
    }

    if (typeof next === 'function') {
      return next(e);
    }
  });
}

export default register;
