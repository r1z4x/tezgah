export const meta = {
  name: 'graph-impact',
  description: 'Blast radius of a change: pull every caller from the codegraph index, plan the edit per module, then have a critic hunt for missed call sites.',
  whenToUse: 'Renaming or changing a shared symbol, migrating an API, deleting suspected dead code - anything where "did I get all the call sites" is the real question.',
  phases: [
    { title: 'Trace', detail: 'codegraph callers of the target, grouped by module' },
    { title: 'Plan', detail: 'one planner per affected module' },
    { title: 'Sweep', detail: 'critic hunts call sites the graph missed' },
  ],
}

const target = (typeof args === 'string' && args) ? args : (args && args.target) || ''
if (!target) return { error: 'graph-impact needs a target: pass a symbol, file, or git ref as args' }
const direction = (args && args.direction) || 'inbound'
const MAX_MODULES = 6

const GRAPH = `On Claude the MCP server exposes one tool by default: load it with
ToolSearch("select:mcp__codegraph__codegraph_explore") before the first query. The rest of the surface is
the CLI: \`codegraph callers <symbol>\` walks inbound call paths, \`codegraph callees <symbol>\` outbound,
\`codegraph impact <symbol>\` gives a symbol's blast radius, \`codegraph affected <ref>\` the same for a git
ref, \`codegraph node <symbol>\` pulls a definition with its body, \`codegraph query <text>\` finds symbols,
\`codegraph files\` dumps what the index holds. The index is the repo's own \`.codegraph/codegraph.db\`.
codegraph ships no coverage report, so what the index does NOT know about is measured by diffing
\`codegraph files\` against \`git ls-files\`.`


const TRACE = {
  type: 'object',
  required: ['resolved_target', 'call_sites'],
  properties: {
    resolved_target: { type: 'string', description: 'the symbol(s) the target actually resolves to, with file:line' },
    kind: { type: 'string', description: 'function, method, type, route, config key, ...' },
    call_sites: { type: 'array', items: {
      type: 'object',
      required: ['module', 'file', 'symbol'],
      properties: {
        module: { type: 'string' },
        file: { type: 'string' },
        line: { type: 'integer' },
        symbol: { type: 'string', description: 'the calling symbol' },
        hops: { type: 'integer', description: 'distance from the target' },
      },
    } },
    unindexed_risk: { type: 'string', description: 'from codegraph files vs git ls-files: what the index cannot see' },
  },
}

const PLAN = {
  type: 'object',
  required: ['module', 'edits'],
  properties: {
    module: { type: 'string' },
    edits: { type: 'array', items: {
      type: 'object',
      required: ['file', 'what', 'why'],
      properties: {
        file: { type: 'string' },
        line: { type: 'integer' },
        what: { type: 'string', description: 'the concrete edit' },
        why: { type: 'string' },
        breaks_if_skipped: { type: 'string' },
      },
    } },
    order_note: { type: 'string', description: 'must this module change before or after others' },
    tests_to_run: { type: 'array', items: { type: 'string' } },
  },
}

phase('Trace')
const trace = await agent(
  `Find every place affected by changing: ${target}
${GRAPH}
Resolve what the target actually is with \`codegraph query\` / \`codegraph node\`, then walk callers with
\`codegraph ${direction === 'outbound' ? 'callees' : 'callers'}\` (and \`codegraph affected\` when the target
is a git ref) until the frontier stops growing. Group call sites by module. Then diff \`codegraph files\`
against \`git ls-files\` and state plainly what the graph cannot see - unindexed files, generated code,
dynamic dispatch, string-keyed lookups, config and templates that reference the symbol by name, and the
extensionless scripts under \`bin/\` that only their \`.py\` twin puts in the graph. Do not plan any edit yet.`,
  { label: 'trace', schema: TRACE, effort: 'high' },
)

if (!trace || !trace.call_sites) return { error: 'trace failed - is the repo indexed? run `codegraph init` first', target, call_sites: [], modules_skipped: [], graph_blind_spots: [] }
if (!trace.call_sites.length) {
  return { target, resolved_target: trace.resolved_target, call_sites: [], modules_skipped: [], graph_blind_spots: [], note: 'no callers in the graph - possible dead code, but confirm against unindexed_risk: ' + (trace.unindexed_risk || 'n/a') }
}

const byModule = {}
for (const cs of trace.call_sites) (byModule[cs.module] = byModule[cs.module] || []).push(cs)
const modules = Object.keys(byModule).sort((a, b) => byModule[b].length - byModule[a].length)
const picked = modules.slice(0, MAX_MODULES)
if (modules.length > picked.length) {
  log(`${trace.call_sites.length} call sites across ${modules.length} modules; planning the ${picked.length} heaviest. NOT planned: ${modules.slice(MAX_MODULES).join(', ')}`)
}
log(`target resolves to: ${trace.resolved_target}`)

phase('Plan')
const plansPending = parallel(picked.map(m => () => agent(
  `Plan the edits inside module "${m}" for this change: ${target}
Target resolves to: ${trace.resolved_target} (${trace.kind || 'unknown kind'})
Call sites in your module: ${JSON.stringify(byModule[m])}
${GRAPH}
Read the actual lines before proposing an edit. For each call site say the concrete edit, why, and what
breaks if it is skipped. Flag ordering constraints against other modules. Name the tests that cover it.
Do not edit anything - plan only.`,
  { label: `plan:${m}`, phase: 'Plan', schema: PLAN, effort: 'high' },
))))

// the sweep prompt reads only the trace, so it starts now instead of waiting
// out the slowest planner
phase('Sweep')
const sweepPending = agent(
  `A graph-based trace found these call sites for "${target}" (resolved: ${trace.resolved_target}):
${JSON.stringify(trace.call_sites)}
The graph itself warned: ${trace.unindexed_risk || 'nothing'}

Your job: find the call sites it MISSED. The graph is blind to string-keyed dispatch, reflection, generated
code, config files, templates, docs, SQL, CI definitions, and anything in unindexed files. Hunt with Grep and
Glob across the repo - including non-source files - for the symbol name and its plausible spellings
(snake_case, kebab-case, quoted string, partial match). Report only hits absent from the list above.`,
  { label: 'sweep', schema: {
    type: 'object',
    required: ['missed'],
    properties: {
      missed: { type: 'array', items: { type: 'object', required: ['file', 'why_it_matters'], properties: {
        file: { type: 'string' }, line: { type: 'integer' }, snippet: { type: 'string' }, why_it_matters: { type: 'string' },
      } } },
      searched: { type: 'string', description: 'the patterns and paths actually searched' },
    },
  }, effort: 'high' },
)

const plans = (await plansPending).filter(Boolean)
const sweep = await sweepPending

return {
  target,
  resolved_target: trace.resolved_target,
  call_site_count: trace.call_sites.length,
  modules_planned: picked,
  modules_skipped: modules.slice(MAX_MODULES),
  plans,
  graph_blind_spots: (sweep && sweep.missed) || [],
  sweep_coverage: sweep && sweep.searched,
  unindexed_risk: trace.unindexed_risk,
}
