// SPDX-License-Identifier: Apache-2.0
// https://www.apache.org/licenses/LICENSE-2.0

import java.util.regex.Matcher
import java.util.regex.Pattern

/**
 * A basic Groovy implementation of the body-field contract
 * (tools/body-field-contract/contract.md): list fields, extract, replace and
 * normalise, with the contract's refusals and whole-body preservation check,
 * and the two writer operations (escapeText, escapeBody).
 *
 * Usable from tools/jira/bridge.groovy or any other Groovy script with
 * `groovy -cp tools/body-field-contract/groovy ...`; conformance.groovy beside
 * it runs the shared conformance cases through it.
 *
 * It mirrors the reference implementation (tools/github-body-field's parser)
 * function for function, so the two can be compared line by line; no
 * dependency beyond the Groovy runtime. Errors are the nested
 * FieldNotFoundError, DuplicateFieldError and AmbiguousFieldError, the last
 * two subclasses of the first, as in the reference.
 */
class BodyFieldParser {

    static class FieldNotFoundError extends RuntimeException {
        FieldNotFoundError(String message) { super(message) }
    }

    static class DuplicateFieldError extends FieldNotFoundError {
        DuplicateFieldError(String message) { super(message) }
    }

    static class AmbiguousFieldError extends FieldNotFoundError {
        AmbiguousFieldError(String message) { super(message) }
    }

    /** One field boundary and the lines up to the next. */
    static class Section {
        String name
        String headingLine
        List<String> bodyLines = []
        int lineNo
        boolean inBlock

        String value() { pyStrip(bodyLines.join('')) }
    }

    /** What normalise produced. */
    static class NormaliseResult {
        String text
        List<Map<String, Object>> changes = []
        List<Map<String, Object>> needsDecision = []
    }

    // A CommonMark line: content plus its ending, or a last unterminated line (BF-LINE-1).
    private static final Pattern LINE = Pattern.compile('[^\\r\\n]*(?:\\r\\n|\\r|\\n)|[^\\r\\n]+\\z')
    // A fence line: up to three spaces, a run of 3+ backticks or tildes, the rest.
    private static final Pattern FENCE = Pattern.compile('( {0,3})(`{3,}|~{3,})(.*)', Pattern.DOTALL)
    // A Jira block opener at the start of a line (after spaces or tabs).
    private static final Pattern JIRA_OPEN = Pattern.compile('[ \\t]*\\{(code|noformat)(?::[^}]*)?\\}')
    // A Jira block macro anywhere in a line.
    private static final Pattern JIRA_MACRO = Pattern.compile('\\{(code|noformat)(?::[^}]*)?\\}')
    private static final Pattern ANY_EOL = Pattern.compile('\\r\\n|\\r|\\n')
    private static final List<String> EOLS = ['\r\n', '\r', '\n']

    // ------------------------------------------------------------ text helpers

    /** Python's str.isspace for one character. */
    static boolean pySpace(char c) {
        return Character.isWhitespace(c) || c == '\u00a0' as char || c == '\u2007' as char ||
            c == '\u202f' as char || c == '\u0085' as char
    }

    /** Python's str.strip(). */
    static String pyStrip(String s) {
        int start = 0
        int end = s.length()
        while (start < end && pySpace(s.charAt(start))) { start++ }
        while (end > start && pySpace(s.charAt(end - 1))) { end-- }
        return s.substring(start, end)
    }

    /** Python's str.strip(chars) / rstrip(chars). */
    static String stripChars(String s, String chars, boolean left = true) {
        int start = 0
        int end = s.length()
        if (left) {
            while (start < end && chars.indexOf((int) s.charAt(start)) >= 0) { start++ }
        }
        while (end > start && chars.indexOf((int) s.charAt(end - 1)) >= 0) { end-- }
        return s.substring(start, end)
    }

    /** Python's " ".join(name.split()). */
    static String collapseName(String name) {
        List<String> words = []
        StringBuilder word = new StringBuilder()
        for (char c : name.toCharArray()) {
            if (pySpace(c)) {
                if (word.length() > 0) { words << word.toString(); word.setLength(0) }
            } else {
                word.append(c)
            }
        }
        if (word.length() > 0) { words << word.toString() }
        return words.join(' ')
    }

    static List<String> splitLines(String body) {
        List<String> lines = []
        Matcher m = LINE.matcher(body)
        while (m.find()) {
            if (m.group().length() > 0) { lines << m.group() }
        }
        return lines
    }

    /** The line without its line ending (Python's rstrip("\r\n")). */
    static String content(String line) { stripChars(line, '\r\n', false) }

    static boolean isBoundary(String line) {
        String c = content(line)
        return c.startsWith('###') && (c.length() == 3 || c.charAt(3) == ' ' as char || c.charAt(3) == '\t' as char)
    }

    // ------------------------------------------------------------ blocks

    private static boolean opensFence(Matcher m) {
        return !(m.group(2).charAt(0) == '`' as char && m.group(3).contains('`'))
    }

    private static int count(String haystack, String needle) {
        int n = 0
        int at = haystack.indexOf(needle)
        while (at >= 0) { n++; at = haystack.indexOf(needle, at + needle.length()) }
        return n
    }

    /** [opener, closer] line indices of every code block, closer null for one left open. */
    static List<List<Integer>> blocks(List<String> lines, boolean jira, int maxIndent = 3) {
        List<List<Integer>> spans = []
        String fenceChar = null
        int fenceLen = 0
        String macro = null
        int start = 0
        for (int index = 0; index < lines.size(); index++) {
            String c = content(lines[index])
            if (fenceChar != null) {
                Matcher m = FENCE.matcher(c)
                if (m.matches() && m.group(2).substring(0, 1) == fenceChar && m.group(2).length() >= fenceLen &&
                        stripChars(m.group(3), ' \t').isEmpty()) {
                    spans << [start, index]
                    fenceChar = null
                }
                continue
            }
            if (macro != null) {
                if (c.contains('{' + macro + '}')) {
                    spans << [start, index]
                    macro = null
                }
                continue
            }
            Matcher m = FENCE.matcher(c)
            if (m.matches() && opensFence(m) && m.group(1).length() <= maxIndent) {
                fenceChar = m.group(2).substring(0, 1)
                fenceLen = m.group(2).length()
                start = index
                continue
            }
            if (jira) {
                Matcher opened = JIRA_OPEN.matcher(c)
                if (opened.lookingAt() && count(c, '{' + opened.group(1)) == 1) {
                    macro = opened.group(1)
                    start = index
                }
            }
        }
        if (fenceChar != null || macro != null) { spans << [start, null] }
        return spans
    }

    private static List<String> roles(List<List<Integer>> spans, int n) {
        List<String> out = (0..<n).collect { 'text' }
        for (List<Integer> span : spans) {
            int start = span[0]
            Integer end = span[1]
            out[start] = 'open'
            for (int i = start + 1; i < (end == null ? n : end); i++) { out[i] = 'code' }
            if (end != null) { out[end] = 'close' }
        }
        return out
    }

    static List<String> fenceRoles(List<String> lines) { roles(blocks(lines, false), lines.size()) }

    static List<Boolean> closedBlockLines(List<String> lines) {
        List<Boolean> inside = (0..<lines.size()).collect { false }
        for (List<Integer> span : blocks(lines, true)) {
            if (span[1] != null) {
                for (int i = span[0]; i <= span[1]; i++) { inside[i] = true }
            }
        }
        return inside
    }

    // ------------------------------------------------------------ Jira macros (BF-MACRO-1)

    private static String leftOpen(String c) {
        String open = null
        Matcher m = JIRA_MACRO.matcher(c)
        while (m.find()) {
            if (open == null) {
                open = m.group(1)
            } else if (m.group() == '{' + open + '}') {
                open = null
            }
        }
        return open
    }

    static List<List<Object>> macroSpans(List<String> lines) {
        List<Boolean> inside = closedBlockLines(lines)
        List<List<Object>> spans = []
        int index = 0
        while (index < lines.size()) {
            String macro = inside[index] ? null : leftOpen(content(lines[index]))
            if (macro == null) { index++; continue }
            String closer = '{' + macro + '}'
            Integer end = null
            for (int j = index + 1; j < lines.size(); j++) {
                if (content(lines[j]).contains(closer)) { end = j; break }
            }
            if (end == null) { index++; continue }
            List<Integer> boundaries = []
            for (int j = index + 1; j < end; j++) {
                if (isBoundary(lines[j])) { boundaries << j }
            }
            if (!boundaries.isEmpty()) { spans << [index, boundaries] }
            index = end + 1
        }
        return spans
    }

    private static Set<String> macroFields(List<String> lines) {
        List<String> names = boundaryNames(lines)
        Set<String> touched = new LinkedHashSet<>()
        for (List<Object> span : macroSpans(lines)) {
            int opener = span[0] as int
            for (int i = opener; i >= 0; i--) {
                if (names[i] != null) { touched << names[i]; break }
            }
            for (Object b : (span[1] as List)) { touched << names[b as int] }
        }
        return touched
    }

    // ------------------------------------------------------------ names

    static String stripClosing(String text) {
        int end = text.length()
        while (end > 0 && text.charAt(end - 1) == '#' as char) { end-- }
        if (end == text.length()) { return text }
        if (end == 0) { return '' }
        if (text.charAt(end - 1) == ' ' as char || text.charAt(end - 1) == '\t' as char) {
            return stripChars(text.substring(0, end), ' \t', false)
        }
        return text
    }

    static String headingName(String line) {
        String c = content(line)
        int start = 0
        while (start < 3 && start < c.length() && c.charAt(start) == ' ' as char) { start++ }
        if (!c.startsWith('###', start)) { return null }
        String rest = c.substring(start + 3)
        if (!(rest.isEmpty() || rest.charAt(0) == ' ' as char || rest.charAt(0) == '\t' as char)) { return null }
        return stripClosing(stripChars(rest, ' \t'))
    }

    static List<String> boundaryNames(List<String> lines) {
        return lines.collect { isBoundary(it) ? headingName(it) : null }
    }

    static String looseHeadingName(String line) {
        String c = content(line)
        if (!c.contains('###')) { return null }
        int i = 0
        int n = c.length()
        while (true) {
            while (i < n && (c.charAt(i) == ' ' as char || c.charAt(i) == '\t' as char)) { i++ }
            if (i < n && c.charAt(i) == '>' as char) { i++; continue }
            if (i + 1 < n && '-*+'.indexOf((int) c.charAt(i)) >= 0 && (c.charAt(i + 1) == ' ' as char || c.charAt(i + 1) == '\t' as char)) {
                i += 2
                continue
            }
            int j = i
            while (j < n && j - i < 9 && c.charAt(j) >= ('0' as char) && c.charAt(j) <= ('9' as char)) { j++ }
            if (i < j && j < n - 1 && (c.charAt(j) == '.' as char || c.charAt(j) == ')' as char) &&
                    (c.charAt(j + 1) == ' ' as char || c.charAt(j + 1) == '\t' as char)) {
                i = j + 2
                continue
            }
            break
        }
        String rest = c.substring(i)
        if (!rest.startsWith('###')) { return null }
        if (!(rest.length() == 3 || rest.charAt(3) == ' ' as char || rest.charAt(3) == '\t' as char)) { return null }
        return stripClosing(stripChars(rest.substring(3), ' \t'))
    }

    // ------------------------------------------------------------ parsing (BF-SEL-*)

    /** [preamble lines, sections]. */
    static List<Object> parse(String body) {
        List<String> lines = splitLines(body)
        List<Boolean> inside = closedBlockLines(lines)
        List<String> names = boundaryNames(lines)
        List<String> preamble = []
        List<Section> sections = []
        for (int i = 0; i < lines.size(); i++) {
            if (names[i] != null) {
                sections << new Section(name: names[i], headingLine: lines[i], lineNo: i + 1, inBlock: inside[i])
            } else if (sections) {
                sections[-1].bodyLines << lines[i]
            } else {
                preamble << lines[i]
            }
        }
        return [preamble, sections]
    }

    static int locate(List<Section> sections, String field) {
        List<Integer> outside = []
        sections.eachWithIndex { Section s, int i -> if (s.name == field && !s.inBlock) { outside << i } }
        if (outside.isEmpty()) { throw new FieldNotFoundError("field not found: ${field}") }
        if (outside.size() > 1) { throw new DuplicateFieldError("field ${field} appears ${outside.size()} times") }
        return outside[0]
    }

    static List<String> listFields(String body) {
        List<Section> sections = parse(body)[1] as List<Section>
        return sections.findAll { !it.inBlock }.collect { it.name }
    }

    // ------------------------------------------------------------ normalise (BF-NORM-*)

    private static List<Boolean> selection(List<String> lines) {
        List<Boolean> inside = closedBlockLines(lines)
        List<Boolean> out = []
        lines.eachWithIndex { String line, int i -> if (isBoundary(line)) { out << inside[i] } }
        return out
    }

    private static void closeUnclosedFences(List<String> lines, List<Integer> origin, List<Map<String, Object>> changes) {
        for (int round = 0; round <= lines.size(); round++) {
            List<List<Integer>> spans = blocks(lines, false)
            if (spans.isEmpty() || spans[-1][1] != null) { return }
            int start = spans[-1][0]
            int at = lines.size()
            for (int i = start + 1; i < lines.size(); i++) {
                if (isBoundary(lines[i])) { at = i; break }
            }
            while (at > start + 1 && stripChars(content(lines[at - 1]), ' \t').isEmpty()) { at-- }
            Matcher opener = FENCE.matcher(content(lines[start]))
            opener.matches()
            List<String> candidate = new ArrayList<>(lines)
            if (at == candidate.size() && !(candidate[-1].endsWith('\n') || candidate[-1].endsWith('\r'))) {
                candidate[-1] = candidate[-1] + '\n'
            }
            candidate.add(at, opener.group(1) + opener.group(2) + '\n')
            if (selection(candidate) != selection(lines)) { return }
            lines.clear()
            lines.addAll(candidate)
            origin.add(at, 0)
            changes << ([line: origin[start], kind: 'unclosed_fence'] as Map<String, Object>)
        }
    }

    private static Map<String, List<Integer>> disputes(List<String> lines, List<Integer> origin, Map<String, String> canonical) {
        Map<String, List<Integer>> disputed = new LinkedHashMap<>()
        if (canonical.isEmpty()) { return disputed }
        List<String> lenient = fenceRoles(lines)
        List<String> strict = roles(blocks(lines, false, 0), lines.size())
        for (int i = 0; i < lines.size(); i++) {
            if (isBoundary(lines[i]) || (lenient[i] != 'text' && strict[i] != 'text')) { continue }
            String name = looseHeadingName(lines[i])
            if (name && canonical.containsKey(collapseName(name))) {
                disputed.computeIfAbsent(canonical[collapseName(name)]) { [] } << origin[i]
            }
        }
        return disputed
    }

    private static List<List<Object>> comparable(List<Section> sections) {
        return sections.collect { [it.name, it.inBlock] }
    }

    static NormaliseResult normalise(String body, List<String> knownFields = null, Map<String, Integer> keep = null) {
        List<Map<String, Object>> changes = []
        Map<String, String> canonical = new LinkedHashMap<>()
        (knownFields ?: []).each { canonical[collapseName(it)] = it }

        List<String> lines = []
        List<Integer> origin = []
        Integer firstCr = null
        splitLines(body).eachWithIndex { String raw, int i ->
            String c = content(raw)
            String ending = raw.substring(c.length())
            if (!(ending == '' || ending == '\n')) {
                if (firstCr == null) { firstCr = i + 1 }
                raw = c + '\n'
            }
            lines << raw
            origin << i + 1
        }
        if (firstCr != null) { changes << ([line: firstCr, kind: 'line_endings'] as Map<String, Object>) }

        closeUnclosedFences(lines, origin, changes)
        List<Boolean> inside = closedBlockLines(lines)
        for (int i = 0; i < lines.size(); i++) {
            if (inside[i] || !isBoundary(lines[i])) { continue }
            String c = content(lines[i])
            String name = headingName(c)
            if (!name) { continue }
            String spelled = canonical.getOrDefault(collapseName(name), name)
            String wanted = '### ' + spelled
            if (wanted != c) {
                lines[i] = wanted + lines[i].substring(c.length())
                changes << ([line: origin[i], kind: spelled == name ? 'heading' : 'heading_name'] as Map<String, Object>)
            }
        }

        List<Map<String, Object>> needs = []
        disputes(lines, origin, canonical).each { String name, List<Integer> nos ->
            needs << ([field: name, kind: 'container-heading', lines: (nos as Set).sort()] as Map<String, Object>)
        }
        List<String> names = boundaryNames(lines)
        for (List<Object> span : macroSpans(lines)) {
            List<Integer> bounds = span[1] as List<Integer>
            List<Integer> nos = [origin[span[0] as int]] + bounds.collect { origin[it] }
            needs << ([field: names[bounds[0]], kind: 'macro-ambiguous', lines: nos] as Map<String, Object>)
        }

        String text = lines.join('')
        List<Object> parsed = parse(text)
        List<String> preamble = parsed[0] as List<String>
        List<Section> sections = parsed[1] as List<Section>
        Map<String, List<Section>> copiesOf = new LinkedHashMap<>()
        sections.each { Section s -> if (s.name && !s.inBlock) { copiesOf.computeIfAbsent(s.name) { [] } << s } }
        Map<Integer, String> drop = new LinkedHashMap<>()
        copiesOf.each { String name, List<Section> copies ->
            if (copies.size() < 2) { return }
            List<Integer> nos = copies.collect { origin[it.lineNo - 1] }
            List<Integer> dropped
            String kind
            if ((copies.collect { it.value() } as Set).size() == 1) {
                dropped = nos.subList(1, nos.size())
                kind = 'duplicate_dropped'
            } else if (keep != null && keep.containsKey(name) && nos.contains(keep[name] as Integer)) {
                dropped = nos.findAll { it != (keep[name] as Integer) }
                kind = 'duplicate_resolved'
            } else {
                needs << ([field: name, kind: 'duplicate', lines: nos] as Map<String, Object>)
                return
            }
            dropped.each { drop[it] = kind }
        }
        if (!drop.isEmpty()) {
            List<Section> kept = sections.findAll { !drop.containsKey(origin[it.lineNo - 1]) }
            List<String> rebuilt = new ArrayList<>(preamble)
            kept.each { rebuilt << it.headingLine; rebuilt.addAll(it.bodyLines) }
            boolean trailingBlank = text.endsWith('\n\n')
            String candidate = rebuilt.join('')
            if (!trailingBlank && candidate.endsWith('\n\n')) {
                candidate = stripChars(candidate, '\n', false) + '\n'
            }
            if (comparable(parse(candidate)[1] as List<Section>) == comparable(kept)) {
                text = candidate
                drop.each { Integer n, String kind -> changes << ([line: n, kind: kind] as Map<String, Object>) }
            } else {
                Set<String> dropNames = new TreeSet<>()
                sections.each { if (drop.containsKey(origin[it.lineNo - 1])) { dropNames << it.name } }
                dropNames.each { String name ->
                    needs << ([field: name, kind: 'duplicate', lines: copiesOf[name].collect { origin[it.lineNo - 1] }] as Map<String, Object>)
                }
            }
        }
        changes.sort { a, b -> (a.line as Integer) <=> (b.line as Integer) ?: (a.kind as String) <=> (b.kind as String) }
        return new NormaliseResult(text: text, changes: changes, needsDecision: needs)
    }

    // ------------------------------------------------------------ extract and replace (BF-EXT-1, BF-REP-*)

    private static boolean isBlankEol(String line) { EOLS.contains(line) }

    private static String eolOf(String body, String line) {
        String ending = line.substring(content(line).length())
        if (ending) { return ending }
        Matcher m = ANY_EOL.matcher(body)
        return m.find() ? m.group() : '\n'
    }

    /** [hadLeading, stripped lines, hadTrailing]. */
    private static List<Object> stripSpacerBlanks(List<String> bodyLines) {
        List<String> lines = new ArrayList<>(bodyLines)
        boolean hadLeading = !lines.isEmpty() && isBlankEol(lines[0])
        if (hadLeading) { lines = lines.subList(1, lines.size()) }
        boolean hadTrailing = !lines.isEmpty() && isBlankEol(lines[-1]) && lines.size() > 1
        if (hadTrailing) { lines = lines.subList(0, lines.size() - 1) }
        return [hadLeading, lines, hadTrailing]
    }

    private static void refuseAmbiguous(String body, String field) {
        if (macroFields(splitLines(body)).contains(field)) {
            throw new AmbiguousFieldError("field ${field}: a Jira macro opened mid-line hides field headings")
        }
        if (normalise(body, [field]).needsDecision.any { it.kind == 'container-heading' }) {
            throw new AmbiguousFieldError("field ${field}: readers could disagree on this body's fields")
        }
    }

    // ------------------------------------------------------------ writer operations

    /** Untrusted text with a leading backslash on every line that would end a field,
     *  fenced or not, and on heading-shaped lines behind containers (BF-WRITE-1, BF-WRITE-3). */
    static String escapeText(String text) {
        return splitLines(text).collect { looseHeadingName(it) != null ? '\\' + it : it }.join('')
    }

    /** A whole body with a leading backslash on every field boundary inside a closed block (BF-WRITE-2). */
    static String escapeBody(String body) {
        List<String> lines = splitLines(body)
        List<Boolean> inside = closedBlockLines(lines)
        List<String> out = []
        lines.eachWithIndex { String line, int i -> out << (inside[i] && isBoundary(line) ? '\\' + line : line) }
        return out.join('')
    }

    static String extractField(String body, String field) {
        refuseAmbiguous(body, field)
        List<Section> sections = parse(body)[1] as List<Section>
        List<String> stripped = stripSpacerBlanks(sections[locate(sections, field)].bodyLines)[1] as List<String>
        return stripped.join('')
    }

    static String replaceField(String body, String field, String newValue) {
        refuseAmbiguous(body, field)
        if (splitLines(newValue).any { isBoundary(it) }) {
            throw new AmbiguousFieldError("field ${field}: the new value holds a line that would end the field")
        }
        List<Object> parsed = parse(body)
        List<String> preamble = parsed[0] as List<String>
        List<Section> sections = parsed[1] as List<Section>
        int targetIdx = locate(sections, field)
        Section target = sections[targetIdx]
        List<Object> spacer = stripSpacerBlanks(target.bodyLines)
        boolean hadLeading = spacer[0] as boolean
        boolean hadTrailing = spacer[2] as boolean
        boolean isLast = targetIdx == sections.size() - 1

        String eol = eolOf(body, target.headingLine)
        String normalised = ANY_EOL.matcher(newValue).replaceAll(Matcher.quoteReplacement(eol))
        while (normalised.endsWith(eol * 2)) { normalised = normalised.substring(0, normalised.length() - eol.length()) }
        if (normalised && !normalised.endsWith(eol)) { normalised += eol }

        List<String> rebuilt = []
        if (normalised) {
            if (hadLeading) { rebuilt << eol }
            rebuilt.addAll(splitLines(normalised))
            if (hadTrailing && !isLast) { rebuilt << eol }
        } else if (!isLast && (hadLeading || hadTrailing)) {
            rebuilt << eol
        }

        List<String> out = new ArrayList<>(preamble)
        sections.eachWithIndex { Section s, int i ->
            out << s.headingLine
            out.addAll(i == targetIdx ? rebuilt : s.bodyLines)
        }
        String newBody = out.join('')
        refuseUnsafeRewrite(body, newBody, field, targetIdx, target.bodyLines, rebuilt)
        return newBody
    }

    private static boolean headingShaped(List<String> span) {
        List<String> r = fenceRoles(span)
        for (int i = 0; i < span.size(); i++) {
            if (r[i] == 'text' && looseHeadingName(span[i]) != null) { return true }
        }
        return false
    }

    private static void refuseUnsafeRewrite(String oldBody, String newBody, String field, int targetIdx,
                                            List<String> oldSpan, List<String> newSpan) {
        if (headingShaped(oldSpan) || headingShaped(newSpan)) {
            throw new AmbiguousFieldError("field ${field}: a value holds a heading-shaped line")
        }
        List<Section> before = parse(oldBody)[1] as List<Section>
        List<Section> after = parse(newBody)[1] as List<Section>
        List<String> known = before.findAll { it.name }.collect { it.name }
        if (normalise(newBody, known).needsDecision.any { it.kind in ['container-heading', 'macro-ambiguous'] }) {
            throw new AmbiguousFieldError("field ${field}: after the rewrite, readers would disagree on the fields")
        }
        if (comparable(before) != comparable(after)) {
            throw new AmbiguousFieldError("field ${field}: the rewrite would change another field")
        }
        for (int i = 0; i < before.size(); i++) {
            if (i != targetIdx && (before[i].headingLine != after[i].headingLine || before[i].bodyLines != after[i].bodyLines)) {
                throw new AmbiguousFieldError("field ${field}: the rewrite would change another field")
            }
        }
    }
}
