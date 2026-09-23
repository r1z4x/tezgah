// Test harness: drive the omp extension without omp.
//
// One JSON object on stdin:
//   { "extension": "<abs path to the generated .ts>", "dir": "<repo abs path>",
//     "session": "<session id>",
//     "calls": [ { "event": "session_start", "arg": {...} } ] }
// The extension's default factory runs against a stub pi (handlers captured,
// sendMessage/setStatus/setWidget recorded), then every call runs through the
// handler registered for that event. Prints JSON, so a failure is reported rather than
// killing the process. Node strips the extension's type annotations on import.
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
  const sent = []
  const statuses = []
  const widgets = []
  const pi = {
    on(event, handler) {
      handlers[event] = handler
    },
    sendMessage(message, options) {
      sent.push({ message, options })
    },
  }
  const mod = await import(pathToFileURL(spec.extension).href)
  mod.default(pi)
  // spec.noWidget drops setWidget, the way a build without the widget surface
  // looks: the extension must fall back to setStatus instead of going silent.
  const ui = { setStatus: (key, text) => statuses.push([key, text]) }
  if (!spec.noWidget) {
    ui.setWidget = (key, content, options) => widgets.push([key, content, options])
  }
  // spec.widgetThrows is a build whose UI surface refuses the call: the
  // extension must not lose the rest of the event to a cosmetic failure.
  if (spec.widgetThrows) {
    ui.setWidget = () => { throw new Error("widget refused") }
    ui.setStatus = () => { throw new Error("status refused") }
  }
  const ctx = {
    cwd: spec.dir,
    sessionManager: { getSessionId: () => spec.session },
    ui,
    setInterval: () => ({ timer: true }),
    clearTimer: () => {},
  }
  const results = []
  for (const call of spec.calls || []) {
    const fn = handlers[call.event]
    if (typeof fn !== "function") {
      results.push({ event: call.event, error: "no such handler" })
      continue
    }
    try {
      results.push({ event: call.event, out: await fn(call.arg || {}, ctx) })
    } catch (err) {
      results.push({
        event: call.event,
        error: String(err && err.message ? err.message : err),
      })
    }
  }
  out = { handlers: Object.keys(handlers), results, sent, statuses, widgets }
} catch (err) {
  out = { fatal: String(err && err.stack ? err.stack : err) }
}
process.stdout.write(JSON.stringify(out))
