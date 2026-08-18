// SPDX-License-Identifier: Apache-2.0
// https://www.apache.org/licenses/LICENSE-2.0

@Grab('org.apache.groovy:groovy-json:4.0.21')
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import groovy.transform.Field

/**
 * JIRA REST bridge for the issue-* skill family.
 *
 * Read subcommands:
 *   search <JQL>          run a JQL query, emit matching issues as JSON
 *   issue <KEY>           fetch a single issue's full state as JSON
 *   projects              list the JIRA projects at the configured tracker URL
 *
 * Write subcommands:
 *   comment <KEY> --body-file <path>            post a comment
 *   transition <KEY> <transition-name>          move workflow state
 *   label <KEY> --add <n> [--remove <n>]        toggle labels
 *   assign <KEY> <username>                     set assignee
 *   field <KEY> <field-name> --value <v>         edit a field (string value)
 *   field <KEY> <field-name> --value-json <j>   edit a field (structured JSON value)
 *   attach <KEY> <file>                         attach a file
 *
 * Configuration (environment only; the caller — typically a skill —
 * resolves these from <project-config>/issue-tracker-config.md and
 * exports them. The bridge does NOT read that file itself):
 *   ISSUE_TRACKER_URL       e.g. https://issues.apache.org/jira
 *   ISSUE_TRACKER_PROJECT   the project key (e.g. FOO)
 *   JIRA_API_TOKEN          required for write operations
 *   JIRA_AUTH_SCHEME        "Basic" (default) or "Bearer" — ASF JIRA DC PATs use Bearer
 *
 * Output: JSON to stdout. Errors: non-zero exit + message to stderr.
 *
 * Write-path discipline: the bridge executes mutations but does NOT decide
 * whether to mutate. Every write is gated on explicit user confirmation in
 * the calling skill — the bridge only executes confirmed actions.
 */

// These are @Field so the cmd_* methods and the httpGet/httpPost helpers
// can see them. A bare top-level `def` in a Groovy script is a local of the
// generated run() method and is NOT visible inside methods — referencing it
// there throws MissingPropertyException.
@Field Map ENV = System.getenv()
@Field String TRACKER_URL  = ENV['ISSUE_TRACKER_URL'] ?: ''
@Field String PROJECT_KEY  = ENV['ISSUE_TRACKER_PROJECT'] ?: ''
@Field String API_TOKEN    = ENV['JIRA_API_TOKEN'] ?: ''
@Field String AUTH_SCHEME  = ENV['JIRA_AUTH_SCHEME'] ?: 'Basic'

if (!TRACKER_URL) {
    System.err.println('error: ISSUE_TRACKER_URL not set in the environment (the calling skill resolves it from <project-config>/issue-tracker-config.md and exports it)')
    System.exit(2)
}

def httpGet(String urlStr) {
    def url = new URL(urlStr)
    def conn = url.openConnection()
    conn.requestMethod = 'GET'
    conn.setRequestProperty('Accept', 'application/json')
    if (API_TOKEN) {
        conn.setRequestProperty('Authorization', "${AUTH_SCHEME} ${API_TOKEN}")
    }
    conn.connectTimeout = 10000
    conn.readTimeout    = 30000
    def code = conn.responseCode
    if (code < 200 || code >= 300) {
        def err = conn.errorStream ? conn.errorStream.text : conn.responseMessage
        System.err.println("error: HTTP ${code} fetching ${urlStr}\n${err}")
        System.exit(3)
    }
    return new JsonSlurper().parse(conn.inputStream)
}

def httpWrite(String urlStr, String method, String jsonBody) {
    def url = new URL(urlStr)
    def conn = url.openConnection()
    conn.requestMethod = method
    conn.doOutput = true
    conn.setRequestProperty('Content-Type', 'application/json')
    conn.setRequestProperty('Accept', 'application/json')
    if (!API_TOKEN) {
        System.err.println('error: JIRA_API_TOKEN is required for write operations')
        System.exit(2)
    }
    conn.setRequestProperty('Authorization', "${AUTH_SCHEME} ${API_TOKEN}")
    conn.connectTimeout = 10000
    conn.readTimeout    = 30000
    conn.outputStream.withWriter('UTF-8') { it.write(jsonBody) }
    def code = conn.responseCode
    if (code < 200 || code >= 300) {
        def err = conn.errorStream ? conn.errorStream.text : conn.responseMessage
        System.err.println("error: HTTP ${code} ${method} ${urlStr}\n${err}")
        System.exit(3)
    }
    if (code == 204) return [:]
    def text = conn.inputStream?.text
    return text ? new JsonSlurper().parseText(text) : [:]
}

def httpMultipart(String urlStr, File file) {
    def boundary = "----BridgeBoundary${System.currentTimeMillis()}"
    def url = new URL(urlStr)
    def conn = url.openConnection()
    conn.requestMethod = 'POST'
    conn.doOutput = true
    conn.setRequestProperty('Content-Type', "multipart/form-data; boundary=${boundary}")
    conn.setRequestProperty('Accept', 'application/json')
    conn.setRequestProperty('X-Atlassian-Token', 'no-check')
    if (!API_TOKEN) {
        System.err.println('error: JIRA_API_TOKEN is required for write operations')
        System.exit(2)
    }
    conn.setRequestProperty('Authorization', "${AUTH_SCHEME} ${API_TOKEN}")
    conn.connectTimeout = 10000
    conn.readTimeout    = 60000
    def os = conn.outputStream
    os.write("--${boundary}\r\n".getBytes('UTF-8'))
    os.write("Content-Disposition: form-data; name=\"file\"; filename=\"${file.name}\"\r\n".getBytes('UTF-8'))
    os.write("Content-Type: application/octet-stream\r\n\r\n".getBytes('UTF-8'))
    file.withInputStream { is -> os << is }
    os.write("\r\n--${boundary}--\r\n".getBytes('UTF-8'))
    os.flush()
    def code = conn.responseCode
    if (code < 200 || code >= 300) {
        def err = conn.errorStream ? conn.errorStream.text : conn.responseMessage
        System.err.println("error: HTTP ${code} uploading ${file.name} to ${urlStr}\n${err}")
        System.exit(3)
    }
    def text = conn.inputStream?.text
    return text ? new JsonSlurper().parseText(text) : [:]
}

def validateKey(String key) {
    if (!key) {
        System.err.println('error: issue key is required (e.g. FOO-9999)')
        System.exit(2)
    }
    if (!(key ==~ /^[A-Z][A-Z0-9_]*-\d+$/)) {
        System.err.println("error: '${key}' is not a valid tracker key")
        System.exit(2)
    }
}

def emit(Object payload) {
    println JsonOutput.prettyPrint(JsonOutput.toJson(payload))
}

def shape_issue(Map raw) {
    [
        key:          raw.key,
        title:        raw.fields?.summary,
        status:       raw.fields?.status?.name,
        resolution:   raw.fields?.resolution?.name,
        components:   raw.fields?.components?.collect { it.name } ?: [],
        fixVersions:  raw.fields?.fixVersions?.collect { it.name } ?: [],
        priority:     raw.fields?.priority?.name,
        reporter:     raw.fields?.reporter?.displayName,
        assignee:     raw.fields?.assignee?.displayName,
        created:      raw.fields?.created,
        updated:      raw.fields?.updated,
        description:  raw.fields?.description,
        comments:     raw.fields?.comment?.comments?.collect {
            [author: it.author?.displayName, body: it.body, created: it.created]
        } ?: [],
        url:          "${TRACKER_URL}/browse/${raw.key}",
    ]
}

def cmd_search(List args) {
    def jql = args ? args[0] : null
    def limit = 50
    def i = 1
    while (i < args.size()) {
        if (args[i] == '--limit' && i + 1 < args.size()) {
            limit = args[i + 1].toInteger()
            i += 2
        } else {
            i++
        }
    }
    if (!jql) {
        System.err.println('error: search requires a JQL string')
        System.exit(2)
    }
    def encoded = URLEncoder.encode(jql, 'UTF-8')
    def url = "${TRACKER_URL}/rest/api/2/search?jql=${encoded}&maxResults=${limit}&fields=summary,status,resolution,components,fixVersions,priority"
    def result = httpGet(url)
    emit([
        total: result.total,
        returned: result.issues?.size() ?: 0,
        issues: (result.issues ?: []).collect { shape_issue(it) },
    ])
}

def cmd_issue(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}?fields=*all"
    def result = httpGet(url)
    emit(shape_issue(result))
}

def cmd_projects(List args) {
    def url = "${TRACKER_URL}/rest/api/2/project"
    def result = httpGet(url)
    emit([
        count: result.size(),
        projects: result.collect { [key: it.key, name: it.name, id: it.id] },
    ])
}

def cmd_comment(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    String bodyFile = null
    def i = 1
    while (i < args.size()) {
        if (args[i] == '--body-file' && i + 1 < args.size()) {
            bodyFile = args[i + 1]
            i += 2
        } else {
            i++
        }
    }
    if (!bodyFile) {
        System.err.println('error: comment requires --body-file <path>')
        System.exit(2)
    }
    def f = new File(bodyFile)
    if (!f.exists()) {
        System.err.println("error: body file not found: ${bodyFile}")
        System.exit(2)
    }
    def body = f.getText('UTF-8')
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}/comment"
    def payload = JsonOutput.toJson([body: body])
    def result = httpWrite(url, 'POST', payload)
    emit([ok: true, key: key, commentId: result.id])
}

def cmd_transition(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    def transitionName = args.size() > 1 ? args[1] : null
    if (!transitionName) {
        System.err.println('error: transition requires a transition name')
        System.exit(2)
    }
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}/transitions"
    def available = httpGet(url)
    def match = available.transitions?.find {
        it.name.equalsIgnoreCase(transitionName)
    }
    if (!match) {
        def names = available.transitions?.collect { it.name } ?: []
        System.err.println("error: transition '${transitionName}' not found for ${key}; available: ${names}")
        System.exit(3)
    }
    def payload = JsonOutput.toJson([transition: [id: match.id]])
    httpWrite(url, 'POST', payload)
    emit([ok: true, key: key, transition: match.name, transitionId: match.id])
}

def cmd_label(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    List addLabels = []
    List removeLabels = []
    def i = 1
    while (i < args.size()) {
        if (args[i] == '--add' && i + 1 < args.size()) {
            addLabels << args[i + 1]
            i += 2
        } else if (args[i] == '--remove' && i + 1 < args.size()) {
            removeLabels << args[i + 1]
            i += 2
        } else {
            i++
        }
    }
    if (!addLabels && !removeLabels) {
        System.err.println('error: label requires at least one --add or --remove flag')
        System.exit(2)
    }
    def ops = []
    addLabels.each { ops << [add: it] }
    removeLabels.each { ops << [remove: it] }
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}"
    def payload = JsonOutput.toJson([update: [labels: ops]])
    httpWrite(url, 'PUT', payload)
    emit([ok: true, key: key, added: addLabels, removed: removeLabels])
}

def cmd_assign(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    def username = args.size() > 1 ? args[1] : null
    if (!username) {
        System.err.println('error: assign requires a username')
        System.exit(2)
    }
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}/assignee"
    // DC payload — Cloud uses accountId
    def payload = JsonOutput.toJson([name: username])
    httpWrite(url, 'PUT', payload)
    emit([ok: true, key: key, assignee: username])
}

def cmd_field(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    def fieldName = args.size() > 1 ? args[1] : null
    if (!fieldName) {
        System.err.println('error: field requires a field name')
        System.exit(2)
    }
    String valueStr = null
    String valueJson = null
    def i = 2
    while (i < args.size()) {
        if (args[i] == '--value' && i + 1 < args.size()) {
            valueStr = args[i + 1]
            i += 2
        } else if (args[i] == '--value-json' && i + 1 < args.size()) {
            valueJson = args[i + 1]
            i += 2
        } else {
            i++
        }
    }
    if (valueStr == null && valueJson == null) {
        System.err.println('error: field requires --value <string> or --value-json <json>')
        System.exit(2)
    }
    def fieldValue
    if (valueJson != null) {
        fieldValue = new JsonSlurper().parseText(valueJson)
    } else {
        fieldValue = valueStr
    }
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}"
    def payload = JsonOutput.toJson([fields: [(fieldName): fieldValue]])
    httpWrite(url, 'PUT', payload)
    emit([ok: true, key: key, field: fieldName, value: fieldValue])
}

def cmd_attach(List args) {
    def key = args ? args[0] : null
    validateKey(key)
    def filePath = args.size() > 1 ? args[1] : null
    if (!filePath) {
        System.err.println('error: attach requires a file path')
        System.exit(2)
    }
    def f = new File(filePath)
    if (!f.exists()) {
        System.err.println("error: file not found: ${filePath}")
        System.exit(2)
    }
    def url = "${TRACKER_URL}/rest/api/2/issue/${key}/attachments"
    def result = httpMultipart(url, f)
    def attachments = result instanceof List ? result : [result]
    emit([ok: true, key: key, attachments: attachments.collect { [id: it.id, filename: it.filename] }])
}

def args = this.args as List
if (!args) {
    System.err.println('usage: groovy bridge.groovy <subcommand> [args]')
    System.exit(2)
}

def subcmd = args[0]
def rest   = args.size() > 1 ? args[1..-1] : []

switch (subcmd) {
    case 'search':     cmd_search(rest);     break
    case 'issue':      cmd_issue(rest);      break
    case 'projects':   cmd_projects(rest);   break
    case 'comment':    cmd_comment(rest);    break
    case 'transition': cmd_transition(rest); break
    case 'label':      cmd_label(rest);      break
    case 'assign':     cmd_assign(rest);     break
    case 'field':      cmd_field(rest);      break
    case 'attach':     cmd_attach(rest);     break
    default:
        System.err.println("error: unknown subcommand '${subcmd}' (expected: search, issue, projects, comment, transition, label, assign, field, attach)")
        System.exit(2)
}
