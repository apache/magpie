// SPDX-License-Identifier: Apache-2.0
// https://www.apache.org/licenses/LICENSE-2.0

// Runs the body-field contract's conformance cases through BodyFieldParser and
// prints one JSON object per case, {"id", "result"}, result in the cases'
// `expect` shape. Usage (from the repository root):
//
//   groovy -cp tools/body-field-contract/groovy \
//       tools/body-field-contract/groovy/conformance.groovy \
//       tools/body-field-contract/conformance/cases.jsonl
//
// Needs only the Groovy runtime (groovy-json ships with it).

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

// The parser's errors by class name: a script sees a classpath class's nested classes only at run time.
@groovy.transform.Field
Map<String, String> ERROR_KINDS = [
    FieldNotFoundError: 'not_found', DuplicateFieldError: 'duplicate', AmbiguousFieldError: 'ambiguous',
]

Object runCase(Map c) {
    Map a = c.args as Map
    String body = c.body as String
    switch (c.op) {
        case 'list_fields':
            return [value: BodyFieldParser.listFields(body)]
        case 'extract':
            return [value: BodyFieldParser.extractField(body, a.name as String)]
        case 'replace':
            return [value: BodyFieldParser.replaceField(body, a.name as String, a.value as String)]
        case 'normalise':
            Map<String, Integer> keep = a.keep == null ? null : (a.keep as Map).collectEntries { k, v -> [(k as String): v as Integer] }
            def r = BodyFieldParser.normalise(body, a.known_fields as List<String>, keep)
            return [value: [text: r.text, changes: r.changes, needs_decision: r.needsDecision]]
        case 'escape_text':
            return [value: BodyFieldParser.escapeText(body)]
        case 'escape_body':
            return [value: BodyFieldParser.escapeBody(body)]
        default:
            throw new IllegalArgumentException("unknown op ${c.op}")
    }
}

PrintStream out = new PrintStream(System.out, true, 'UTF-8')
JsonSlurper slurper = new JsonSlurper()
new File(args[0]).eachLine('UTF-8') { String line ->
    if (!line.trim()) { return }
    Map c = slurper.parseText(line) as Map
    Object result
    try {
        result = runCase(c)
    } catch (RuntimeException e) {
        String kind = ERROR_KINDS[e.class.simpleName]
        if (kind == null) { throw e }
        result = [error: kind]
    }
    out.println(JsonOutput.toJson([id: c.id, result: result]))
}
