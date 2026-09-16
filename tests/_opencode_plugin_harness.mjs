// Test harness: drive the opencode plugin's hooks without opencode.
//
// One JSON object on stdin:
//   { "plugin": "<abs path>", "dir": "<repo abs path>",
//     "calls": [ { "hook": "tool.execute.before", "input": {...}, "output": {...} } ] }
// The plugin is instantiated once, then every call runs through the named hook.
// Prints { "hooks": [...], "results": [ {ok, error?, output?} ] } as JSON, so a
// throwing hook (a denial) is reported rather than killing the process.
import { pathToFileURL } from "node:url"

const raw = await new Promise((resolve) => {
  let s = ""
  process.stdin.setEncoding("utf8")
  process.stdin.on("data", (d) => (s += d))
  process.stdin.on("end", () => resolve(s))
})

let out
try {
  const spec = JSON.parse(raw)
  const mod = await import(pathToFileURL(spec.plugin).href)
  const hooks = await mod.Tezgah({ directory: spec.dir })
  const results = []
  for (const call of spec.calls || []) {
    const fn = hooks[call.hook]
    if (typeof fn !== "function") {
      results.push({ ok: false, error: "no such hook: " + call.hook })
      continue
    }
    const output = call.output && typeof call.output === "object" ? call.output : {}
    try {
      await fn(call.input || {}, output)
      results.push({ ok: true, output })
    } catch (err) {
      results.push({
        ok: false,
        error: String(err && err.message ? err.message : err),
      })
    }
  }
  out = { hooks: Object.keys(hooks), results }
} catch (err) {
  out = { fatal: String(err && err.stack ? err.stack : err) }
}
process.stdout.write(JSON.stringify(out))
