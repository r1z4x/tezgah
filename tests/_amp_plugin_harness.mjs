// Test harness: drive tezgah's Amp plugin without Amp.
//
// One JSON object on stdin:
//   { "plugin": "<abs path to the rendered .ts>", "dir": "<workspace abs path>",
//     "thread": "<thread id>", "parent": "<parent thread id>" | null,
//     "active": bool, "noHelpers": bool,
//     "calls": [ { "event": "tool.call", "arg": {...} } ] }
// The plugin's default export runs against a stub PluginAPI (handlers captured,
// the status item and notifications recorded), then every call runs through the
// handler registered for that event with a thread context. Each event gets the
// thread unless it names its own. Prints JSON, so a failure is reported rather
// than killing the process. Node strips the plugin's type annotations on import.
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
  const handlers = {}
  const status = []
  const notified = []
  const amp = {
    on(event, handler) {
      handlers[event] = handler
    },
    system: { workspaceRoot: "file://" + spec.dir },
    helpers: spec.noHelpers ? {} : {
      filePathFromURI: (uri) => String(uri).replace(/^file:\/\//, ""),
      // Amp's own reader of a shell call: `Bash` or `shell_command` only
      shellCommandFromToolCall: (e) => (["Bash", "shell_command"].includes(e.tool)
        ? { command: e.input.cmd ?? e.input.command, dir: e.input.cwd } : null),
    },
    activeThread: { current: spec.active ? { id: spec.thread } : null },
    experimental: { createStatusItem: () => ({ update: (v) => status.push(v.text) }) },
  }
  const mod = await import(pathToFileURL(spec.plugin).href)
  mod.default(amp)
  const ctx = {
    thread: { id: spec.thread, parentThreadID: async () => spec.parent ?? null },
    ui: { notify: async (m) => { notified.push(m) } },
  }
  const results = []
  for (const call of spec.calls || []) {
    const fn = handlers[call.event]
    if (typeof fn !== "function") {
      results.push({ event: call.event, error: "no such handler" })
      continue
    }
    try {
      const arg = Object.assign({ thread: { id: spec.thread } }, call.arg || {})
      results.push({ event: call.event, out: (await fn(arg, ctx)) ?? null })
    } catch (err) {
      results.push({ event: call.event, error: String(err && err.message ? err.message : err) })
    }
  }
  out = { handlers: Object.keys(handlers), results, status, notified,
          tezgahSession: process.env.TEZGAH_SESSION ?? null }
} catch (err) {
  out = { fatal: String(err && err.stack ? err.stack : err) }
}
process.stdout.write(JSON.stringify(out))
