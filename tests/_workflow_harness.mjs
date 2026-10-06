// Test harness: run a `workflows/*.js` script without Claude's Workflow runtime.
//
// One JSON object on stdin:
//   { "workflow": "<abs path to the .js>", "args": <args>,
//     "agents": { "<label prefix>": <result or null> } }
// A workflow is a script body with top-level `await` and `return` over the
// runtime globals `args`, `agent`, `parallel`, `phase` and `log`, so it runs
// here as an async function body. The stub `agent` answers with the result of
// the longest label prefix in `agents`; null, or no matching prefix, is a
// failed agent (the runtime's null). Prints JSON {result, labels, logs}, so a
// throw is reported rather than killing the process.
import { readFileSync } from "node:fs"

const raw = await new Promise((resolve) => {
  let s = ""
  process.stdin.setEncoding("utf8")
  process.stdin.on("data", (d) => (s += d))
  process.stdin.on("end", () => resolve(s))
})

let out
try {
  const spec = JSON.parse(raw)
  const labels = []
  const logs = []
  const agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ""
    labels.push(label)
    const keys = Object.keys(spec.agents || {}).filter((k) => label.startsWith(k))
    keys.sort((a, b) => b.length - a.length)
    return keys.length ? spec.agents[keys[0]] : null
  }
  const parallel = (fns) => Promise.all(fns.map((f) => f()))
  const body = readFileSync(spec.workflow, "utf8").replace(/^export const meta/m, "const meta")
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
  const run = new AsyncFunction("args", "agent", "parallel", "phase", "log", body)
  const result = await run(spec.args, agent, parallel, () => {}, (m) => logs.push(m))
  out = { result, labels, logs }
} catch (err) {
  out = { error: String((err && err.stack) || err) }
}
process.stdout.write(JSON.stringify(out))
