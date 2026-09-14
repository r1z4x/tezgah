export const meta = {
  name: 'cbm-map',
  description: 'Map a subsystem off the codebase-memory graph: survey, one reader per module, synthesize, then gap-check.',
  whenToUse: 'Before changing unfamiliar code, or when asked how a subsystem works / where things live / for an architecture map.',
  phases: [
    { title: 'Survey', detail: 'get_architecture + module inventory from the graph' },
    { title: 'Read', detail: 'one reader agent per module, in parallel' },
    { title: 'Synthesize', detail: 'merge into one map' },
    { title: 'Gap check', detail: 'critic names what the map still misses' },
  ],
}

const focus = (typeof args === 'string' && args) ? args : (args && args.focus) || 'the whole repository'
const MAX_MODULES = 8

const CBM = `Use the codebase-memory-mcp tools, not grep, for structure. Load them first with
ToolSearch("select:mcp__codebase-memory-mcp__search_graph,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__search_code,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__get_architecture,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__check_index_coverage"). Useful ones: get_architecture, search_graph, search_code,
trace_path, get_code_snippet, check_index_coverage, list_projects. Fall back to Read/Grep only
for something the graph genuinely cannot answer, and say so when you do.`

const SURVEY = {
  type: 'object',
  required: ['modules'],
  properties: {
    modules: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'path', 'why'],
        properties: {
          name: { type: 'string' },
          path: { type: 'string' },
          why: { type: 'string', description: 'why this module matters to the focus' },
          rank: { type: 'integer', description: '1 = most central to the focus' },
        },
      },
    },
    entrypoints: { type: 'array', items: { type: 'string' } },
    stack: { type: 'string', description: 'languages, frameworks, storage, transport' },
  },
}

const READING = {
  type: 'object',
  required: ['module', 'responsibility', 'key_symbols'],
  properties: {
    module: { type: 'string' },
    responsibility: { type: 'string' },
    key_symbols: {
      type: 'array',
      items: {
        type: 'object',
        required: ['symbol', 'file', 'role'],
        properties: {
          symbol: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          role: { type: 'string' },
        },
      },
    },
    collaborators: { type: 'array', items: { type: 'string' }, description: 'modules it calls or is called by, from trace_path' },
    data_flow: { type: 'string' },
    risks: { type: 'array', items: { type: 'string' }, description: 'coupling, dead code, missing tests - graph-evidenced only' },
  },
}

phase('Survey')
const survey = await agent(
  `Survey this repository so other agents can split it up. Focus: ${focus}.
${CBM}
Start with list_projects and get_architecture(aspects=['all']). Return the modules that matter for the
focus, ranked, with the real directory path for each. Do not read file bodies - stay at graph level.`,
  { label: 'survey', schema: SURVEY, effort: 'medium' },
)

if (!survey || !survey.modules || !survey.modules.length) {
  return { error: 'survey returned no modules - is the repo indexed? run index_repository first' }
}

const ranked = survey.modules.slice().sort((a, b) => (a.rank || 99) - (b.rank || 99))
const picked = ranked.slice(0, MAX_MODULES)
if (ranked.length > picked.length) {
  log(`${ranked.length} modules found, reading top ${picked.length}: dropped ${ranked.slice(MAX_MODULES).map(m => m.name).join(', ')}`)
}

phase('Read')
const readings = (await parallel(picked.map(m => () => agent(
  `Read module "${m.name}" at ${m.path}. It matters because: ${m.why}. Overall focus: ${focus}.
${CBM}
Answer: what it is responsible for, its key symbols with file and line, which other modules call it or
it calls (use trace_path both directions), how data moves through it, and any graph-evidenced risk
(dead code, a symbol with many inbound callers, missing test coverage). Cite file:line for every claim.`,
  { label: `read:${m.name}`, phase: 'Read', schema: READING },
)))).filter(Boolean)

log(`${readings.length}/${picked.length} modules read`)

phase('Synthesize')
const map = await agent(
  `Write one coherent map of this codebase for focus "${focus}".
Stack: ${survey.stack || 'unknown'}. Entrypoints: ${(survey.entrypoints || []).join(', ') || 'unknown'}.
Per-module readings (JSON):
${JSON.stringify(readings)}

Produce markdown: a one-paragraph orientation, a module table (module - responsibility - key entry symbol as
\`file:line\`), the request/data path end to end naming the symbol at each hop as \`file:line\`, then "Sharp
edges" where every bullet ends in the \`file:line\` it refers to. Every file:line comes from the readings -
copy them, never reconstruct or guess one. Do not invent anything absent from the readings. If the readings
carry no code symbols (a docs-only or config-only repo), say so in one line at the top instead of dressing
document headings up as code.`,
  { label: 'synthesize', effort: 'high' },
)

if (!map) {
  return { focus, modules_read: readings.map(r => r.module),
           modules_dropped: ranked.slice(MAX_MODULES).map(m => m.name),
           map: null, gaps: [], error: 'the synthesize agent returned nothing' }
}

phase('Gap check')
const gaps = await agent(
  `Here is a codebase map produced from graph-derived module readings. Focus was "${focus}".

${map}

Your job is to find what it MISSES, not to praise it. Verify against the graph yourself.
${CBM}
Name concretely: a module in the repo absent from the map, a claimed call path that trace_path does not
support, an entrypoint never traced, a file:line citation that does not resolve. Use check_index_coverage
to see whether unindexed files hide part of the answer. Return a short list; empty list if genuinely clean.`,
  { label: 'gap-check', schema: {
    type: 'object',
    required: ['gaps'],
    properties: {
      gaps: { type: 'array', items: { type: 'object', required: ['gap', 'evidence'], properties: {
        gap: { type: 'string' }, evidence: { type: 'string' }, severity: { type: 'string' },
      } } },
      coverage_note: { type: 'string' },
    },
  }, effort: 'high' },
)

return {
  focus,
  modules_read: readings.map(r => r.module),
  modules_dropped: ranked.slice(MAX_MODULES).map(m => m.name),
  map,
  gaps: (gaps && gaps.gaps) || [],
  coverage_note: gaps && gaps.coverage_note,
}
