export const meta = {
  name: 'cbm-review',
  description: 'Review a diff with graph-derived blast radius: scope, dimension fan-out, then adversarial verification of every finding.',
  whenToUse: 'Reviewing uncommitted work, a branch, or a PR when you want findings that survive a skeptic rather than a plausible-sounding list.',
  phases: [
    { title: 'Scope', detail: 'detect_changes: changed symbols + transitive callers' },
    { title: 'Review', detail: 'one reviewer per dimension, in parallel' },
    { title: 'Verify', detail: 'two refuters per finding, distinct lenses' },
  ],
}

const target = (typeof args === 'string' && args) ? args : (args && args.target) || 'uncommitted changes vs HEAD'
const MAX_VERIFIED = 4

const CBM = `Load the graph tools first with ToolSearch("select:mcp__codebase-memory-mcp__detect_changes,mcp__codebase-memory-mcp__search_graph,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__search_code,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__get_architecture,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__check_index_coverage"). detect_changes gives changed
symbols plus their transitive callers - that blast radius is the point, a diff alone hides it. trace_path,
search_graph, search_code, get_code_snippet fill in callers and definitions. Read files for exact lines.`

const SCOPE = {
  type: 'object',
  required: ['changed_files'],
  properties: {
    project: { type: 'string' },
    changed_files: { type: 'array', items: { type: 'string' } },
    changed_symbols: { type: 'array', items: { type: 'string' } },
    impacted_modules: { type: 'array', items: { type: 'string' }, description: 'from detect_changes inbound direction' },
    blast_radius_note: { type: 'string' },
    diff_summary: { type: 'string' },
  },
}

const FINDINGS = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: { type: 'array', items: {
      type: 'object',
      required: ['title', 'file', 'summary', 'failure_scenario', 'severity'],
      properties: {
        title: { type: 'string' },
        file: { type: 'string' },
        line: { type: 'integer' },
        summary: { type: 'string' },
        failure_scenario: { type: 'string', description: 'concrete inputs or state -> wrong output or crash' },
        severity: { type: 'string', enum: ['high', 'medium', 'low'] },
      },
    } },
  },
}

const VERDICT = {
  type: 'object',
  required: ['refuted', 'reasoning'],
  properties: {
    refuted: { type: 'boolean', description: 'true = the finding does not hold' },
    reasoning: { type: 'string' },
    evidence: { type: 'string', description: 'file:line or tool output that settles it' },
  },
}

const DIMENSIONS = [
  { key: 'correctness', ask: 'logic errors, wrong boundary conditions, unhandled nil/empty/error paths, off-by-one, inverted conditions, state mutated under the wrong assumption' },
  { key: 'callers', ask: 'callers this change breaks: signature/contract/return-shape changes, callers in impacted_modules that were not updated, dynamic or reflective call sites text search would miss' },
  { key: 'security', ask: 'injection, missing authz on a newly reachable path, secrets in code or logs, unvalidated external input, unsafe deserialization, TOCTOU' },
  { key: 'tests', ask: 'behavior changed with no test touching it - name the exact untested branch and the test file that should have covered it' },
]

phase('Scope')
const scope = await agent(
  `Establish the review scope for: ${target}.
${CBM}
Run detect_changes (scope=impact, direction=inbound) for this project to get changed symbols and their
transitive callers, plus git diff for the actual lines. Return the changed files, changed symbols, the
impacted modules, and one honest sentence on how far the blast radius reaches. No opinions on quality yet.`,
  { label: 'scope', schema: SCOPE, effort: 'medium' },
)

if (!scope || !scope.changed_files || !scope.changed_files.length) {
  return { target, findings: [], confirmed: [], refuted: [], unverified: [], note: 'no changes detected for this target - nothing to review' }
}
log(`${scope.changed_files.length} changed files, impacted modules: ${(scope.impacted_modules || []).join(', ') || 'none reported'}`)

const CONTEXT = `Target: ${target}
Changed files: ${scope.changed_files.join(', ')}
Changed symbols: ${(scope.changed_symbols || []).join(', ') || 'unknown'}
Impacted modules (transitive callers): ${(scope.impacted_modules || []).join(', ') || 'none'}
Diff summary: ${scope.diff_summary || 'read it yourself with git diff'}`

phase('Review')
const reviews = (await parallel(DIMENSIONS.map(d => () => agent(
  `Review this change through one lens only: ${d.key}.
Look for: ${d.ask}

${CONTEXT}
${CBM}
Report only defects in or newly caused by the changed code. A finding needs a concrete failure scenario -
inputs or state that produce the wrong result. No style notes, no "consider maybe", no praise. Empty list
is the correct answer when the lens finds nothing.`,
  { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS, effort: 'high' },
)))).filter(Boolean)

const rank = { high: 0, medium: 1, low: 2 }
const all = reviews.flatMap(r => r.findings || []).sort((a, b) => rank[a.severity] - rank[b.severity])
if (!all.length) return { target, scope, findings: [], confirmed: [], refuted: [], unverified: [], note: 'all four dimensions came back clean' }

const toVerify = all.slice(0, MAX_VERIFIED)
if (all.length > toVerify.length) {
  log(`${all.length} findings raised; verifying the ${toVerify.length} most severe. NOT verified (reported as unverified): ${all.slice(MAX_VERIFIED).map(f => f.title).join('; ')}`)
}

phase('Verify')
const LENSES = [
  'Re-read the actual code at the cited location. Does the code say what the finding claims it says?',
  'Assume the finding is wrong. Find the guard, caller contract, type constraint, or existing test that already prevents this failure scenario.',
]
const verified = await parallel(toVerify.map(f => () => parallel(LENSES.map((lens, i) => () => agent(
  `Try to REFUTE this review finding. Default to refuted=true when the evidence is not clear.

Finding: ${f.title}
Location: ${f.file}${f.line ? ':' + f.line : ''}
Claim: ${f.summary}
Claimed failure: ${f.failure_scenario}

Your lens: ${lens}
${CBM}
Cite the file:line or tool output that settles it. A finding that cannot be tied to real code is refuted.`,
  { label: `verify:${f.title.slice(0, 28)}#${i + 1}`, phase: 'Verify', schema: VERDICT, effort: 'high' },
))).then(votes => {
  const live = votes.filter(Boolean)
  const kills = live.filter(v => v.refuted)
  // "survived two refuters" means zero refutations; a 1-1 split is a kill
  return { finding: f, survived: live.length > 0 && kills.length === 0, votes: live }
})))

const confirmed = verified.filter(Boolean).filter(v => v.survived)
const killed = verified.filter(Boolean).filter(v => !v.survived)
log(`${confirmed.length} findings survived verification, ${killed.length} refuted`)

return {
  target,
  scope: { changed_files: scope.changed_files, impacted_modules: scope.impacted_modules, blast_radius_note: scope.blast_radius_note },
  confirmed: confirmed.map(v => ({ ...v.finding, verdict: 'CONFIRMED', why_it_held: v.votes.filter(x => !x.refuted).map(x => x.evidence || x.reasoning) })),
  refuted: killed.map(v => ({ title: v.finding.title, refuted_because: v.votes.filter(x => x.refuted).map(x => x.reasoning) })),
  unverified: all.slice(MAX_VERIFIED).map(f => ({ ...f, verdict: 'UNVERIFIED - budget cap' })),
}
